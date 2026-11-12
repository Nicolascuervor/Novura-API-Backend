"""
Capa de Aplicación y Servicios de Casos de Uso (Pricing Module).
Conecta los modelos de persistencia y caché con el Núcleo de Dominio Puro (`core_domain`),
resolviendo las tensiones arquitectónicas:
- EC-01 (<=15s en góndola) vs. EC-03 (Validación antifraude en memoria).
- EC-02 (Actualidad del dato al cambiar precio) vs. EC-04 (Caché de lectura para 500 usuarios concurrentes).
- EC-05 (Extensibilidad mediante PriceSourcePort para el Módulo Comercial sin rediseñar el núcleo).
"""

import hashlib
from datetime import timedelta
from decimal import Decimal
from typing import BinaryIO

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from catalog.models import Establishment, Product, ProductPresentation
from catalog.services import ImageSecurityService
from core_domain.anomaly_detector import AnomalyDetector, HistoricalPriceContext
from core_domain.entities import (
    ComparablePriceEntry,
    ProductCategory,
    ReliabilityStatus,
    SourceType,
    UnitOfMeasure,
)
from core_domain.neutral_comparator import (
    ComparisonOutput,
    NeutralComparator,
    SortCriterion,
)
from core_domain.ports import PriceSourcePort
from core_domain.unit_normalizer import UnitNormalizer
from core_domain.validity_policy import ValidityPolicy
from pricing.models import PriceReport


def build_anonymous_reporter_hash(raw_identifier: str) -> str:
    """
    Genera un hash SHA-256 con salt a partir de un identificador de sesión/token,
    cumpliendo con Ley 1581 de 2012 y M-06 = 1.00 (cero almacenamiento de identidad o GPS).
    """
    salted = f"{settings.SECRET_KEY}:{raw_identifier.strip() or 'anon'}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


def get_product_comparison_cache_version_key(product_id: int) -> str:
    return f"pricecol:product:{product_id}:cache_ver"


def invalidate_product_comparison_cache(product_id: int) -> None:
    """
    Resuelve la tensión ATAM entre EC-02 (Actualidad del dato) y EC-04 (Caché de alta concurrencia):
    Incrementa la versión de caché del producto inmediatamente cuando entra un nuevo precio válido
    y programa en Celery (`transaction.on_commit`) el pre-calentamiento proactivo de los 3 rankings.
    """
    ver_key = get_product_comparison_cache_version_key(product_id)
    current_ver = cache.get(ver_key, 1)
    cache.set(ver_key, int(current_ver) + 1, timeout=86400)
    cache.delete("pricecol:moderation:dashboard_summary")

    from pricing.tasks import schedule_prewarm_product_comparison_cache

    schedule_prewarm_product_comparison_cache(product_id)


class ReportPriceUseCase:
    """Caso de uso para registrar un precio colaborativo u oficial en segundos (EC-01, EC-02, EC-03)."""

    def __init__(self, detector: AnomalyDetector | None = None) -> None:
        self.detector = detector or AnomalyDetector()

    def execute(
        self,
        *,
        presentation: ProductPresentation,
        establishment: Establishment,
        raw_price: Decimal,
        reporter_token: str = "anonymous",
        source_type: SourceType = SourceType.COMMUNITY_OCCASIONAL,
        is_promotional: bool = False,
        promotion_description: str = "",
        evidence_image_file: BinaryIO | None = None,
    ) -> PriceReport:
        sanitized_evidence = None
        if evidence_image_file is not None:
            sanitized_evidence = ImageSecurityService.validate_and_sanitize(
                file_obj=evidence_image_file,
                filename=getattr(evidence_image_file, "name", ""),
            )

        now = timezone.now()
        reporter_hash = build_anonymous_reporter_hash(reporter_token)

        # 1. Normalización exacta por unidad de medida (M-01)
        norm_result = UnitNormalizer.normalize(
            raw_price=raw_price,
            quantity=presentation.quantity,
            unit=UnitOfMeasure(presentation.unit),
        )

        # 2. Construcción ligera de contexto histórico para detección antifraude en < 5 ms (EC-03 / EC-01)
        recent_verified_prices = tuple(
            PriceReport.objects.filter(
                presentation=presentation,
                reliability_status=ReliabilityStatus.VERIFIED.value,
            )
            .order_by("-reported_at")
            .values_list("raw_price", flat=True)[:25]
        )

        ten_min_ago = now - timedelta(minutes=10)
        fifteen_min_ago = now - timedelta(minutes=15)

        user_burst_count = PriceReport.objects.filter(
            reporter_hash=reporter_hash,
            reported_at__gte=ten_min_ago,
        ).count()

        # Cuentas distintas reportando precios similares en ventana corta para el mismo local
        price_lower = raw_price * Decimal("0.95")
        price_upper = raw_price * Decimal("1.05")
        coordinated_count = (
            PriceReport.objects.filter(
                presentation=presentation,
                establishment=establishment,
                reported_at__gte=fifteen_min_ago,
                raw_price__gte=price_lower,
                raw_price__lte=price_upper,
            )
            .values("reporter_hash")
            .distinct()
            .count()
        )

        context = HistoricalPriceContext(
            historical_prices=recent_verified_prices,
            recent_reports_by_same_user_last_10m=user_burst_count,
            distinct_users_reporting_same_outlier_last_15m=coordinated_count,
        )

        anomaly_assessment = self.detector.evaluate(
            reported_price=raw_price,
            context=context,
            source_type=source_type,
        )

        report = PriceReport.objects.create(
            presentation=presentation,
            establishment=establishment,
            raw_price=norm_result.raw_price,
            normalized_ref_price=norm_result.price_per_ref_unit,
            price_per_base_unit=norm_result.price_per_base_unit,
            reference_unit_label=norm_result.reference_unit_label,
            source_type=source_type.value,
            reliability_status=anomaly_assessment.status.value,
            confidence_score=anomaly_assessment.confidence_score,
            anomaly_notes="; ".join(anomaly_assessment.reasons),
            is_promotional=is_promotional,
            promotion_description=promotion_description,
            evidence_image=sanitized_evidence,
            reporter_hash=reporter_hash,
        )

        # Invalidar caché inmediatamente para que EC-02 refleje el cambio sin esperar TTL largo
        invalidate_product_comparison_cache(presentation.product_id)

        return report


class CommunityPriceSourceAdapter(PriceSourcePort):
    """
    Adaptador del Núcleo que obtiene los reportes desde la base de datos y evalúa su vigencia (EC-02).
    Implementa `PriceSourcePort` para permitir que en el Corte 3 se agreguen adaptadores comerciales
    sin modificar `ComparePricesQueryService` (cumpliendo M-09 <= 0.15).
    """

    def __init__(self, validity_policy: ValidityPolicy | None = None) -> None:
        self.validity_policy = validity_policy or ValidityPolicy()

    def fetch_entries_for_product(self, product_id: int) -> list[ComparablePriceEntry]:
        now = timezone.now()
        try:
            product = Product.objects.get(pk=product_id, is_active=True)
        except Product.DoesNotExist:
            return []

        reports = (
            PriceReport.objects.filter(
                presentation__product_id=product_id,
                presentation__is_active=True,
                establishment__is_active=True,
            )
            .select_related("presentation", "establishment")
            .order_by("-reported_at")[:200]
        )

        # Identificar el reporte verificado más reciente por (presentación, establecimiento) para EC-02
        latest_verified_map: dict[tuple[int, int], timezone.datetime] = {}
        for rep in reports:
            if rep.reliability_status == ReliabilityStatus.VERIFIED.value:
                key = (rep.presentation_id, rep.establishment_id)
                if key not in latest_verified_map or rep.reported_at > latest_verified_map[key]:
                    latest_verified_map[key] = rep.reported_at

        entries: list[ComparablePriceEntry] = []
        for rep in reports:
            key = (rep.presentation_id, rep.establishment_id)
            latest_for_pair = latest_verified_map.get(key)

            validity = self.validity_policy.evaluate(
                reported_at=rep.reported_at,
                evaluated_at=now,
                category=ProductCategory(product.category),
                latest_verified_at_for_establishment=latest_for_pair,
            )

            entries.append(
                ComparablePriceEntry(
                    report_id=rep.id,
                    establishment_id=rep.establishment_id,
                    establishment_name=rep.establishment.name,
                    presentation_id=rep.presentation_id,
                    presentation_name=f"{rep.presentation.brand} {rep.presentation.presentation_name}",
                    raw_price=rep.raw_price,
                    normalized_ref_price=rep.normalized_ref_price,
                    reference_unit_label=rep.reference_unit_label,
                    reported_at=rep.reported_at,
                    validity_status=validity.status,
                    reliability_status=ReliabilityStatus(rep.reliability_status),
                    freshness_score=validity.freshness_score,
                    confidence_score=rep.confidence_score,
                    source_type=SourceType(rep.source_type),
                    is_promotional=rep.is_promotional,
                    promotion_description=rep.promotion_description or None,
                )
            )

        return entries


class ComparePricesQueryService:
    """
    Servicio de consulta y comparación neutral de precios (EC-04 y EC-06).
    Integra múltiples `PriceSourcePort` y aplica caché de lectura de baja latencia (P95 <= 2000ms).
    """

    CACHE_TTL_SECONDS = 120

    def __init__(self, sources: list[PriceSourcePort] | None = None) -> None:
        self.sources: list[PriceSourcePort] = sources or [CommunityPriceSourceAdapter()]

    def compare_product(
        self,
        product_id: int,
        criterion: SortCriterion = SortCriterion.UNIT_PRICE_ASC,
        municipality: str | None = None,
        include_low_confidence: bool = True,
    ) -> ComparisonOutput:
        ver_key = get_product_comparison_cache_version_key(product_id)
        cache_ver = cache.get(ver_key, 1)
        muni_slug = (municipality or "all").lower().strip()
        sources_sig = "-".join(sorted(type(s).__name__ for s in self.sources))
        cache_key = (
            f"pricecol:cmp:p{product_id}:v{cache_ver}:{criterion.value}:"
            f"{muni_slug}:{int(include_low_confidence)}:{sources_sig}"
        )

        cached_output: ComparisonOutput | None = cache.get(cache_key)
        if cached_output is not None:
            return cached_output

        all_entries: list[ComparablePriceEntry] = []
        for source in self.sources:
            all_entries.extend(source.fetch_entries_for_product(product_id))

        if municipality:
            allowed_est_ids = set(
                Establishment.objects.filter(
                    municipality__iexact=municipality.strip(),
                    is_active=True,
                ).values_list("id", flat=True)
            )
            all_entries = [e for e in all_entries if e.establishment_id in allowed_est_ids]

        output = NeutralComparator.compare(
            entries=all_entries,
            criterion=criterion,
            include_low_confidence_with_warning=include_low_confidence,
        )

        cache.set(cache_key, output, timeout=self.CACHE_TTL_SECONDS)
        return output

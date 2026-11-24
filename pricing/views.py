"""
Vistas de Registro Colaborativo y Comparación Neutral de Precios (EC-01 a EC-06).
Cumple estrictamente con `django-architecture-enforcer` y `django-security-auditor`.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, views, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from accounts.models import AuditEventLog
from accounts.permissions import CanReportPricesPermission
from accounts.selectors import get_or_create_actor_profile
from accounts.services import (
    record_audit_event,
    resolve_verified_source_type_for_actor,
    sanitize_plain_text,
    update_actor_reputation_after_report,
)
from catalog.models import Product
from catalog.services import InvalidImageError
from core_domain.neutral_comparator import SortCriterion
from core_domain.price_history import InvalidPriceHistoryWindowError
from pricing.models import PriceReport
from pricing.serializers import (
    ProductComparisonResponseSerializer,
    ProductPriceHistoryResponseSerializer,
    PublicPriceReportReceiptSerializer,
    QuickPriceReportCreateSerializer,
)
from pricing.services import (
    ComparePricesQueryService,
    PriceHistoryQueryService,
    ReportPriceUseCase,
)


class PriceReportViewSet(viewsets.ModelViewSet):
    """
    Endpoint de registro ágil de precios en góndola (EC-01 <= 15s) y consulta de reportes públicos
    protegiendo la privacidad del reportante (Ley 1581 / M-06 = 1.00).
    Exige sesión iniciada para registrar (POST) según Tabla 4.1 (Reportante / Comercio),
    valida propiedad sobre el establecimiento (Anti-BOLA) y sanitiza textos e imágenes (EXIF).
    """

    permission_classes = [CanReportPricesPermission]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "price_report"
    queryset = (
        PriceReport.objects.select_related(
            "presentation",
            "presentation__product",
            "establishment",
        )
        .exclude(reliability_status="ANOMALOUS")
        .order_by("-reported_at")
    )
    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return QuickPriceReportCreateSerializer
        return PublicPriceReportReceiptSerializer

    @extend_schema(
        summary="Registrar un precio en góndola en un solo paso (Requiere JWT de Reportante o Comercio - EC-01, EC-03)",
        request=QuickPriceReportCreateSerializer,
        responses={201: PublicPriceReportReceiptSerializer},
    )
    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = QuickPriceReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        profile = get_or_create_actor_profile(user=request.user)
        resolved_source = resolve_verified_source_type_for_actor(
            profile=profile,
            target_establishment=data["establishment"],
            requested_source_type=data.get("source_type"),
        )
        clean_promo_desc = sanitize_plain_text(data.get("promotion_description", ""))
        reporter_token = f"user-{request.user.pk}"

        use_case = ReportPriceUseCase()
        try:
            report = use_case.execute(
                presentation=data["presentation"],
                establishment=data["establishment"],
                raw_price=data["raw_price"],
                reporter_token=reporter_token,
                source_type=resolved_source,
                is_promotional=data.get("is_promotional", False),
                promotion_description=clean_promo_desc,
                evidence_image_file=data.get("evidence_image"),
            )
        except InvalidImageError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        update_actor_reputation_after_report(
            profile=profile,
            report=report,
            presentation=data["presentation"],
            establishment=data["establishment"],
        )

        record_audit_event(
            actor_user=request.user,
            module=AuditEventLog.AuditModule.PRICING,
            action_type="PRICE_REPORT_CREATED",
            target_model="PriceReport",
            target_id=report.id,
            target_repr=f"{data['presentation']} @ {data['establishment'].name}",
            summary=(
                f"Reporte de precio #{report.id} (${report.raw_price} COP) en '{data['establishment'].name}' "
                f"clasificado como {report.reliability_status} ({report.source_type})."
            ),
            severity=(
                AuditEventLog.AuditSeverity.WARNING
                if report.reliability_status in ("LOW_CONFIDENCE", "ANOMALOUS")
                else AuditEventLog.AuditSeverity.INFO
            ),
            new_state={
                "report_id": report.id,
                "presentation_id": report.presentation_id,
                "establishment_id": report.establishment_id,
                "raw_price": str(report.raw_price),
                "normalized_ref_price": str(report.normalized_ref_price),
                "reference_unit_label": report.reference_unit_label,
                "reliability_status": report.reliability_status,
                "confidence_score": str(report.confidence_score),
                "source_type": report.source_type,
                "is_promotional": report.is_promotional,
            },
        )

        receipt = PublicPriceReportReceiptSerializer(report, context={"request": request})
        return Response(receipt.data, status=status.HTTP_201_CREATED)


class ProductPriceComparisonAPIView(views.APIView):
    """
    Endpoint de comparación neutral de precios por producto entre establecimientos (EC-02, EC-04, EC-06).
    Soporta normalización por unidad de medida (100g/100ml/1und), vigencia automática y caché de alta concurrencia.
    """

    @extend_schema(
        summary="Comparar precios de un producto entre establecimientos (Normalizado y Neutral - EC-04, EC-06)",
        parameters=[
            OpenApiParameter(
                "sort_by",
                str,
                enum=[c.value for c in SortCriterion],
                default=SortCriterion.UNIT_PRICE_ASC.value,
                description="Criterio explícito de ordenamiento: UNIT_PRICE_ASC (por 100g/100ml/1und), RAW_PRICE_ASC, FRESHNESS_DESC.",
            ),
            OpenApiParameter(
                "municipality",
                str,
                required=False,
                description="Filtrar establecimientos por municipio (ej. Armenia).",
            ),
            OpenApiParameter(
                "include_low_confidence",
                bool,
                required=False,
                default=True,
                description="Incluir reportes con variación atípica moderada acompañados de etiqueta de advertencia (EC-03).",
            ),
        ],
        responses={200: ProductComparisonResponseSerializer},
    )
    def get(self, request: Request, product_id: int) -> Response:
        product = get_object_or_404(Product, pk=product_id, is_active=True)

        raw_sort = request.query_params.get("sort_by", SortCriterion.UNIT_PRICE_ASC.value).upper()
        try:
            criterion = SortCriterion(raw_sort)
        except ValueError:
            return Response(
                {
                    "detail": f"Criterio de ordenamiento inválido '{raw_sort}'. Valores permitidos: {[c.value for c in SortCriterion]}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        municipality = request.query_params.get("municipality")
        include_low_conf = request.query_params.get("include_low_confidence", "true").lower() != "false"

        query_service = ComparePricesQueryService()
        comparison = query_service.compare_product(
            product_id=product.id,
            criterion=criterion,
            municipality=municipality,
            include_low_confidence=include_low_conf,
        )

        payload = {
            "product_id": product.id,
            "product_name": product.name,
            "declared_sort_criterion": comparison.declared_criterion.value,
            "neutrality_statement": (
                "Orden estricto por el criterio seleccionado por el consumidor. "
                "Ninguna relación comercial altera esta posición (Ley 1480 / EC-06)."
            ),
            "total_valid_results": len(comparison.ranked_results),
            "excluded_non_valid_or_anomalous_count": comparison.excluded_count,
            "ranked_results": comparison.ranked_results,
            "promotional_highlights_separated": comparison.promotional_highlights,
        }

        response_serializer = ProductComparisonResponseSerializer(payload)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class ProductPriceHistoryAPIView(views.APIView):
    """
    Endpoint de historial y tendencia de precios de hasta 90 días por producto y establecimiento(s)
    (Opción A2 del Anexo 1 — Escenario EC-08 y ADR-13).
    Conserva los cambios de precio sin sobrescribir valores anteriores (Append-Only), distingue el origen
    (`source_type`) y estado de confiabilidad (`reliability_status`) de cada punto, soporta comparar dos o más
    establecimientos en la misma gráfica y protege la identidad del reportante (Ley 1581 / M-06 = 1.00).
    """

    @extend_schema(
        summary="Consultar historial y tendencia de precios de los últimos 90 días (A2 / EC-08 / ADR-13)",
        parameters=[
            OpenApiParameter(
                "days",
                int,
                required=False,
                default=90,
                description="Ventana histórica en días (1 a 90 días; por defecto 90 días según EC-08).",
            ),
            OpenApiParameter(
                "establishment_id",
                int,
                required=False,
                description="ID de un establecimiento específico para consultar su serie histórica.",
            ),
            OpenApiParameter(
                "establishment_ids",
                str,
                required=False,
                description="Lista de IDs de establecimientos separados por coma (ej. '1,2') para comparar tendencias en la misma gráfica.",
            ),
            OpenApiParameter(
                "include_low_confidence",
                bool,
                required=False,
                default=True,
                description="Incluir puntos con estado LOW_CONFIDENCE marcados con `requires_warning=true`.",
            ),
        ],
        responses={200: ProductPriceHistoryResponseSerializer},
    )
    def get(self, request: Request, product_id: int) -> Response:
        product = get_object_or_404(Product, pk=product_id, is_active=True)

        raw_days = request.query_params.get("days", "90")
        try:
            window_days = int(raw_days)
        except (TypeError, ValueError):
            return Response(
                {"detail": "El parámetro 'days' debe ser un número entero entre 1 y 90."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        selected_establishments: set[int] = set()
        single_est = request.query_params.get("establishment_id")
        multi_est = request.query_params.get("establishment_ids")

        try:
            if single_est:
                selected_establishments.add(int(single_est))
            if multi_est:
                for token in multi_est.split(","):
                    cleaned = token.strip()
                    if cleaned:
                        selected_establishments.add(int(cleaned))
        except ValueError:
            return Response(
                {"detail": "Los identificadores de establecimiento deben ser enteros válidos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        include_low_conf = request.query_params.get("include_low_confidence", "true").lower() != "false"

        history_service = PriceHistoryQueryService()
        try:
            history_output = history_service.get_product_history(
                product_id=product.id,
                window_days=window_days,
                establishment_ids=selected_establishments or None,
                include_low_confidence=include_low_conf,
            )
        except InvalidPriceHistoryWindowError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = {
            "product_id": product.id,
            "product_name": product.name,
            "window_days": history_output.window_days,
            "cutoff_start_at": history_output.cutoff_start_at,
            "evaluated_at": history_output.evaluated_at,
            "privacy_statement": (
                "Serie histórica anonimizada conforme a la Ley 1581 de 2012 (M-06 = 1.00): "
                "ningún punto permite identificar qué reportante registró cada precio."
            ),
            "total_points": history_output.total_points,
            "excluded_out_of_window_count": history_output.excluded_out_of_window_count,
            "excluded_anomalous_count": history_output.excluded_anomalous_count,
            "establishment_series": history_output.establishment_series,
        }

        serializer = ProductPriceHistoryResponseSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)

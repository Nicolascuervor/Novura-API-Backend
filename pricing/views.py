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

from accounts.permissions import CanReportPricesPermission
from accounts.selectors import get_or_create_actor_profile
from accounts.services import (
    resolve_verified_source_type_for_actor,
    sanitize_plain_text,
    update_actor_reputation_after_report,
)
from catalog.models import Product
from catalog.services import InvalidImageError
from core_domain.neutral_comparator import SortCriterion
from pricing.models import PriceReport
from pricing.serializers import (
    ProductComparisonResponseSerializer,
    PublicPriceReportReceiptSerializer,
    QuickPriceReportCreateSerializer,
)
from pricing.services import ComparePricesQueryService, ReportPriceUseCase


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

"""
Serializers del Módulo de Precios y Comparación Neutral.
Cumple estrictamente con:
- M-06 = 1.00 (Ley 1581 de 2012): Ningún serializer público incluye `reporter_hash`, identidad del reportante
  ni coordenadas GPS personales del reportante.
- EC-01 (M-03): Payload de creación mínimo de 3 campos esenciales (`presentation_id`, `establishment_id`, `raw_price`)
  para permitir el registro en góndola en <= 15 segundos con red móvil limitada.
- EC-06 (M-02 = 1.00): Expone explícitamente el criterio de ordenamiento declarado, las advertencias de vigencia/confiabilidad
  y la separación de contenido promocional.
"""

from decimal import Decimal

from rest_framework import serializers

from catalog.models import Establishment, ProductPresentation
from core_domain.entities import SourceType
from pricing.models import PriceReport


class QuickPriceReportCreateSerializer(serializers.Serializer):
    """
    Contrato optimizado para el registro ágil en góndola (EC-01 <= 15s).
    Protección contra errores de usuario (ISO/IEC 25010 - Capacidad de Interacción):
    valida precios mal digitados antes de impactar el dominio.
    """

    presentation_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductPresentation.objects.filter(is_active=True),
        source="presentation",
        help_text="ID de la presentación observada en el estante.",
    )
    establishment_id = serializers.PrimaryKeyRelatedField(
        queryset=Establishment.objects.filter(is_active=True),
        source="establishment",
        help_text="ID del establecimiento (tienda, minimercado o supermercado).",
    )
    raw_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("50.00"),
        max_value=Decimal("10000000.00"),
        help_text="Precio total observado en pesos colombianos (COP).",
    )
    source_type = serializers.ChoiceField(
        choices=[(s.value, s.value) for s in SourceType],
        default=SourceType.COMMUNITY_OCCASIONAL.value,
        required=False,
    )
    is_promotional = serializers.BooleanField(default=False, required=False)
    promotion_description = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
        default="",
    )


class PublicPriceReportReceiptSerializer(serializers.ModelSerializer):
    """
    Respuesta pública del registro de un precio.
    Cumple M-06 = 1.00: Excluye explícitamente `reporter_hash`, GPS e identidad del usuario.
    Incluye autodescriptividad para que el reportante vea que su aporte fue procesado (ISO/IEC 25010).
    """

    establishment_name = serializers.CharField(source="establishment.name", read_only=True)
    presentation_label = serializers.SerializerMethodField()
    user_feedback_message = serializers.SerializerMethodField()

    class Meta:
        model = PriceReport
        fields = (
            "id",
            "presentation",
            "presentation_label",
            "establishment",
            "establishment_name",
            "raw_price",
            "normalized_ref_price",
            "reference_unit_label",
            "reliability_status",
            "confidence_score",
            "is_promotional",
            "promotion_description",
            "reported_at",
            "user_feedback_message",
        )

    def get_presentation_label(self, obj: PriceReport) -> str:
        return f"{obj.presentation.product.name} - {obj.presentation.brand} ({obj.presentation.presentation_name})"

    def get_user_feedback_message(self, obj: PriceReport) -> str:
        if obj.reliability_status == "VERIFIED":
            return (
                f"¡Gracias! Tu reporte de ${obj.raw_price} COP "
                f"(${obj.normalized_ref_price}/{obj.reference_unit_label}) está activo para ayudar a tu comunidad."
            )
        if obj.reliability_status == "LOW_CONFIDENCE":
            return (
                "Tu reporte fue registrado con etiqueta de verificación pendiente debido a una variación respecto al promedio."
            )
        return (
            "El precio ingresado presenta una desviación atípica frente al histórico y pasó a revisión de moderación."
        )


class ComparablePriceItemSerializer(serializers.Serializer):
    """Ítem individual dentro del resultado de comparación neutral (EC-06, M-02, M-06)."""

    report_id = serializers.IntegerField()
    establishment_id = serializers.IntegerField()
    establishment_name = serializers.CharField()
    presentation_id = serializers.IntegerField()
    presentation_name = serializers.CharField()
    raw_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    normalized_ref_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    reference_unit_label = serializers.CharField()
    reported_at = serializers.DateTimeField()
    validity_status = serializers.CharField()
    reliability_status = serializers.CharField()
    freshness_score = serializers.DecimalField(max_digits=4, decimal_places=2)
    confidence_score = serializers.DecimalField(max_digits=4, decimal_places=2)
    source_type = serializers.CharField()
    is_promotional = serializers.BooleanField()
    promotion_description = serializers.CharField(allow_null=True)
    requires_warning_label = serializers.BooleanField()
    warning_messages = serializers.ListField(child=serializers.CharField())


class ProductComparisonResponseSerializer(serializers.Serializer):
    """Respuesta completa y transparente de la comparación de un producto entre establecimientos."""

    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    declared_sort_criterion = serializers.CharField()
    neutrality_statement = serializers.CharField()
    total_valid_results = serializers.IntegerField()
    excluded_non_valid_or_anomalous_count = serializers.IntegerField()
    ranked_results = ComparablePriceItemSerializer(many=True)
    promotional_highlights_separated = ComparablePriceItemSerializer(many=True)

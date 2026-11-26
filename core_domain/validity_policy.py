"""
Política de vigencia y actualidad del dato (ISO/IEC 25012 - Escenario EC-02 y Medida M-01).
Determina cuándo un precio reportado u oficial sigue vigente, requiere advertencia de antigüedad
o ha expirado / sido reemplazado por una actualización posterior.
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from core_domain.entities import ProductCategory, ValidityAssessment, ValidityStatus

# Ventanas de vigencia en horas según los regímenes de volatilidad de ADR-04 (EC-02):
# - Alta volatilidad (verduras, frutas, huevos, carnes y perecederos): vigente hasta 2 días (48h), con advertencia hasta día 5 (120h), excluido después.
# - Baja volatilidad (granos, abarrotes, enlatados, bebidas, aseo personal y limpieza): vigente hasta 7 días (168h), con advertencia hasta día 15 (360h), excluido después.
_CATEGORY_TTL_HOURS: dict[ProductCategory, tuple[Decimal, Decimal]] = {
    # (umbral_advertencia_horas, umbral_expiracion_maxima_horas)
    ProductCategory.FRUITS_VEGGIES: (Decimal(48), Decimal(120)),      # Alta volatilidad: advertencia a las 48h (2 días), expira a las 120h (5 días)
    ProductCategory.PERISHABLE: (Decimal(48), Decimal(120)),         # Alta volatilidad: advertencia a las 48h (2 días), expira a las 120h (5 días)
    ProductCategory.GROCERY: (Decimal(168), Decimal(360)),            # Baja volatilidad: advertencia a las 168h (7 días), expira a las 360h (15 días)
    ProductCategory.BEVERAGES: (Decimal(168), Decimal(360)),          # Baja volatilidad: advertencia a las 168h (7 días), expira a las 360h (15 días)
    ProductCategory.PERSONAL_CARE: (Decimal(168), Decimal(360)),      # Baja volatilidad: advertencia a las 168h (7 días), expira a las 360h (15 días)
    ProductCategory.CLEANING: (Decimal(168), Decimal(360)),           # Baja volatilidad: advertencia a las 168h (7 días), expira a las 360h (15 días)
}


class ValidityPolicy:
    """Evalúa la actualidad (freshness) y estado de vigencia de un precio."""

    def evaluate(
        self,
        reported_at: datetime,
        evaluated_at: datetime,
        category: ProductCategory | str = ProductCategory.GROCERY,
        latest_verified_at_for_establishment: datetime | None = None,
    ) -> ValidityAssessment:
        try:
            cat_enum = (
                ProductCategory(category)
                if not isinstance(category, ProductCategory)
                else category
            )
        except ValueError:
            cat_enum = ProductCategory.GROCERY

        # EC-02: Si existe una modificación oficial o un reporte verificado más reciente
        # en el mismo establecimiento para la misma presentación, el precio anterior queda SUPERSEDED de inmediato.
        if (
            latest_verified_at_for_establishment is not None
            and latest_verified_at_for_establishment > reported_at
        ):
            elapsed_seconds = max(0.0, (evaluated_at - reported_at).total_seconds())
            age_hours = Decimal(str(elapsed_seconds / 3600.0)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            return ValidityAssessment(
                status=ValidityStatus.SUPERSEDED,
                is_currently_valid=False,
                freshness_score=Decimal("0.00"),
                age_hours=age_hours,
                reason="Reemplazado por un precio más reciente en el mismo establecimiento (EC-02).",
            )

        elapsed_seconds = max(0.0, (evaluated_at - reported_at).total_seconds())
        age_hours = Decimal(str(elapsed_seconds / 3600.0)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        warn_hours, max_hours = _CATEGORY_TTL_HOURS[cat_enum]

        if age_hours > max_hours:
            return ValidityAssessment(
                status=ValidityStatus.EXPIRED,
                is_currently_valid=False,
                freshness_score=Decimal("0.00"),
                age_hours=age_hours,
                reason=f"Precio vencido: supera la ventana máxima de {int(max_hours // 24)} días para {cat_enum.value}.",
            )

        # Puntaje lineal de frescura entre 1.00 (recién reportado) y 0.05 (al borde del vencimiento)
        raw_score = Decimal("1.00") - (age_hours / max_hours)
        freshness_score = max(
            Decimal("0.05"),
            raw_score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        )

        if age_hours >= warn_hours:
            return ValidityAssessment(
                status=ValidityStatus.STALE_WARNING,
                is_currently_valid=True,
                freshness_score=freshness_score,
                age_hours=age_hours,
                reason="Precio próximo a vencer; se recomienda confirmar en góndola.",
            )

        return ValidityAssessment(
            status=ValidityStatus.VALID,
            is_currently_valid=True,
            freshness_score=freshness_score,
            age_hours=age_hours,
            reason="Precio vigente dentro del umbral de actualidad.",
        )

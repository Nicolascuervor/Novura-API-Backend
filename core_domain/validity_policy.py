"""
Política de vigencia y actualidad del dato (ISO/IEC 25012 - Escenario EC-02 y Medida M-01).
Determina cuándo un precio reportado u oficial sigue vigente, requiere advertencia de antigüedad
o ha expirado / sido reemplazado por una actualización posterior.
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from core_domain.entities import ProductCategory, ValidityAssessment, ValidityStatus

# Ventanas máximas de vigencia en horas según la rotación de la categoría en Armenia/Quindío
_CATEGORY_TTL_HOURS: dict[ProductCategory, tuple[Decimal, Decimal]] = {
    # (umbral_advertencia_horas, umbral_expiracion_maxima_horas)
    ProductCategory.PERISHABLE: (Decimal(120), Decimal(168)),      # Advertencia a los 5 días, expira a los 7 días
    ProductCategory.GROCERY: (Decimal(240), Decimal(360)),         # Advertencia a los 10 días, expira a los 15 días
    ProductCategory.PERSONAL_CARE: (Decimal(360), Decimal(504)),   # Advertencia a los 15 días, expira a los 21 días
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
        cat_enum = (
            ProductCategory(category)
            if not isinstance(category, ProductCategory)
            else category
        )

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

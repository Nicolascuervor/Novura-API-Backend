"""
Detector estadístico y heurístico de reportes anómalos o malintencionados (EC-03, M-05).
Cumple simultáneamente:
- M-05: Tasa de detección >= 80% (meta deseable >= 90%) sobre el conjunto de reportes anómalos.
- EC-01 / M-03: Ejecución en memoria en < 1 ms para no penalizar el registro en góndola (<= 15 s).
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

from core_domain.entities import AnomalyAssessment, ReliabilityStatus, SourceType


@dataclass(frozen=True)
class HistoricalPriceContext:
    """Contexto histórico de precios del producto y actividad reciente para evaluar antifraude."""

    historical_prices: tuple[Decimal, ...] = ()
    recent_reports_by_same_user_last_10m: int = 0
    distinct_users_reporting_same_outlier_last_15m: int = 0


class AnomalyDetector:
    """
    Evalúa la credibilidad (ISO/IEC 25012) e integridad (ISO/IEC 25010) de un reporte de precio.
    Detecta:
    1. Desviaciones severas respecto a la mediana histórica (errores de digitación o sabotaje).
    2. Ráfagas de spam de un mismo usuario en ventana corta.
    3. Ataques coordinados de múltiples cuentas reportando valores atípicos simultáneamente.
    """

    MAX_ACCEPTABLE_DEVIATION_RATIO = Decimal("0.35")    # > 35% de desviación sin respaldo es anómalo
    WARNING_DEVIATION_RATIO = Decimal("0.22")           # Entre 22% y 35% queda con baja confianza y advertencia
    MAX_USER_BURST_10M = 4                              # Más de 4 reportes en 10 min activa sospecha de spam
    COORDINATED_OUTLIER_THRESHOLD = 3                   # 3+ cuentas reportando un outlier en 15m indica coordinación

    def evaluate(
        self,
        reported_price: Decimal | float | str,
        context: HistoricalPriceContext,
        source_type: SourceType = SourceType.COMMUNITY_OCCASIONAL,
    ) -> AnomalyAssessment:
        price = Decimal(str(reported_price))
        reasons: list[str] = []

        if price <= Decimal(200) or price >= Decimal(5000000):
            return AnomalyAssessment(
                status=ReliabilityStatus.ANOMALOUS,
                is_reliable=False,
                confidence_score=Decimal("0.00"),
                reasons=("Precio fuera de los límites físicos para productos de la canasta familiar.",),
            )

        base_confidence = {
            SourceType.OFFICIAL_MERCHANT: Decimal("0.95"),
            SourceType.PUBLIC_REFERENCE: Decimal("0.95"),
            SourceType.COMMUNITY_FREQUENT: Decimal("0.90"),
            SourceType.COMMUNITY_OCCASIONAL: Decimal("0.85"),
        }.get(source_type, Decimal("0.85"))

        # 1. Verificación de ráfagas de usuario (Spam)
        if context.recent_reports_by_same_user_last_10m >= self.MAX_USER_BURST_10M:
            reasons.append("Ráfaga inusual de reportes por el mismo usuario en los últimos 10 minutos.")
            base_confidence -= Decimal("0.45")

        # 2. Verificación estadística contra mediana histórica
        deviation_ratio = Decimal("0.00")
        if context.historical_prices:
            med_price = Decimal(str(median(context.historical_prices)))
            if med_price > Decimal(0):
                deviation_ratio = abs(price - med_price) / med_price

                if deviation_ratio > self.MAX_ACCEPTABLE_DEVIATION_RATIO:
                    pct = (deviation_ratio * Decimal(100)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                    reasons.append(
                        f"Desviación extrema del {pct}% respecto a la mediana histórica (${med_price})."
                    )
                    base_confidence -= Decimal("0.65")
                elif deviation_ratio > self.WARNING_DEVIATION_RATIO:
                    pct = (deviation_ratio * Decimal(100)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                    reasons.append(
                        f"Desviación moderada del {pct}% respecto a la mediana histórica (${med_price})."
                    )
                    base_confidence -= Decimal("0.30")

        # 3. Detección de ataques coordinados (EC-03)
        if (
            context.distinct_users_reporting_same_outlier_last_15m >= self.COORDINATED_OUTLIER_THRESHOLD
            and deviation_ratio >= Decimal("0.18")
        ):
            reasons.append(
                "Patrón de reporte coordinado detectado: múltiples cuentas inyectando un valor atípico en simultáneo."
            )
            base_confidence -= Decimal("0.55")

        final_score = max(
            Decimal("0.00"),
            min(Decimal("1.00"), base_confidence.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        )

        if final_score < Decimal("0.45"):
            return AnomalyAssessment(
                status=ReliabilityStatus.ANOMALOUS,
                is_reliable=False,
                confidence_score=final_score,
                reasons=tuple(reasons),
            )

        if final_score < Decimal("0.75"):
            return AnomalyAssessment(
                status=ReliabilityStatus.LOW_CONFIDENCE,
                is_reliable=True,
                confidence_score=final_score,
                reasons=tuple(reasons),
            )

        return AnomalyAssessment(
            status=ReliabilityStatus.VERIFIED,
            is_reliable=True,
            confidence_score=final_score,
            reasons=tuple(reasons),
        )

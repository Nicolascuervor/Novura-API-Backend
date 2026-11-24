"""
Motor de Historial y Tendencia de Precios de 90 Días en el Núcleo Puro (`core_domain/price_history.py`).
Implementa la Opción A2 del Anexo 1 del Corte 3 (Escenario EC-08 y ADR-13) mediante TDD:
- Conserva y procesa series de solo inserción (Append-Only) sin sobrescribir valores anteriores.
- Filtra estrictamente la ventana de hasta 90 días (1 a 90 días).
- Distingue en cada punto el origen (`source_type`) y el estado de confiabilidad (`reliability_status`).
- Excluye el 100 % de reportes `ANOMALOUS` y señala explícitamente `LOW_CONFIDENCE` con `requires_warning=True`.
- Soporta comparar la tendencia de uno, dos o más establecimientos en la misma gráfica (Extensión opcional A2).
- Calcula con aritmética exacta (`Decimal`) el precio inicial, final, mínimo, máximo, promedio, variación y dirección.
- Cero exposición de `reporter_hash` o identidad del reportante (Ley 1581 de 2012 / M-06 = 1.00).
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from core_domain.entities import (
    ComparablePriceEntry,
    ReliabilityStatus,
    SourceType,
    ValidityStatus,
)


class InvalidPriceHistoryWindowError(ValueError):
    """Error lanzado cuando la ventana solicitada está fuera del rango permitido de 1 a 90 días (EC-08)."""


class TrendDirection(StrEnum):
    """Dirección de la tendencia del precio normalizado en el periodo consultado."""

    UP = "UP"
    DOWN = "DOWN"
    STABLE = "STABLE"


@dataclass(frozen=True)
class PriceHistoryPoint:
    """
    Punto individual e inmutable dentro de la serie temporal de un establecimiento (EC-08, M-06 = 1.00).
    Distingue origen (`source_type`) y estado de confiabilidad (`reliability_status`) sin exponer al reportante.
    """

    report_id: int
    establishment_id: int
    establishment_name: str
    presentation_id: int
    presentation_name: str
    reported_at: datetime
    raw_price: Decimal
    normalized_ref_price: Decimal
    reference_unit_label: str
    source_type: SourceType
    reliability_status: ReliabilityStatus
    validity_status: ValidityStatus
    confidence_score: Decimal
    is_promotional: bool
    promotion_description: str | None
    requires_warning: bool


@dataclass(frozen=True)
class EstablishmentPriceTrendSeries:
    """
    Serie temporal de 90 días y métricas de tendencia de un producto para un establecimiento específico.
    Permite graficar uno o comparar múltiples establecimientos simultáneamente (Extensión opcional A2).
    """

    establishment_id: int
    establishment_name: str
    reference_unit_label: str
    points_count: int
    first_normalized_price: Decimal
    latest_normalized_price: Decimal
    min_normalized_price: Decimal
    max_normalized_price: Decimal
    avg_normalized_price: Decimal
    variation_amount: Decimal
    variation_percentage: Decimal
    trend_direction: TrendDirection
    points: tuple[PriceHistoryPoint, ...]


@dataclass(frozen=True)
class ProductPriceHistoryOutput:
    """Resultado completo e inmutable de la consulta de historial y tendencia de precios (A2 / EC-08)."""

    product_id: int
    window_days: int
    cutoff_start_at: datetime
    evaluated_at: datetime
    total_points: int
    excluded_out_of_window_count: int
    excluded_anomalous_count: int
    establishment_series: tuple[EstablishmentPriceTrendSeries, ...]


class PriceHistoryService:
    """
    Servicio puro de dominio que construye la serie histórica y tendencia de precios de un producto
    en uno o varios establecimientos durante los últimos N días (máximo 90 días — EC-08).
    """

    MIN_WINDOW_DAYS: int = 1
    MAX_WINDOW_DAYS: int = 90
    TWO_DECIMALS: Decimal = Decimal("0.01")

    @classmethod
    def build_history(
        cls,
        *,
        product_id: int,
        entries: list[ComparablePriceEntry],
        evaluated_at: datetime,
        window_days: int = 90,
        establishment_ids: set[int] | None = None,
        include_low_confidence: bool = True,
    ) -> ProductPriceHistoryOutput:
        if not (cls.MIN_WINDOW_DAYS <= window_days <= cls.MAX_WINDOW_DAYS):
            raise InvalidPriceHistoryWindowError(
                f"La ventana de historial debe estar entre {cls.MIN_WINDOW_DAYS} y {cls.MAX_WINDOW_DAYS} días."
            )

        cutoff_start = evaluated_at - timedelta(days=window_days)
        excluded_out_of_window = 0
        excluded_anomalous = 0

        grouped_points: dict[int, list[PriceHistoryPoint]] = defaultdict(list)
        establishment_names: dict[int, str] = {}

        for entry in entries:
            if establishment_ids is not None and entry.establishment_id not in establishment_ids:
                continue

            # 1. Regla ADR-13: Excluir siempre reportes ANOMALOUS del historial público
            if entry.reliability_status == ReliabilityStatus.ANOMALOUS:
                excluded_anomalous += 1
                continue

            # 2. Filtrar LOW_CONFIDENCE si el consumidor solicitó solo verificados
            if not include_low_confidence and entry.reliability_status == ReliabilityStatus.LOW_CONFIDENCE:
                continue

            # 3. Ventana temporal de los últimos N días (por defecto 90 días — EC-08)
            if entry.reported_at < cutoff_start or entry.reported_at > evaluated_at:
                excluded_out_of_window += 1
                continue

            requires_warning = entry.reliability_status == ReliabilityStatus.LOW_CONFIDENCE
            point = PriceHistoryPoint(
                report_id=entry.report_id,
                establishment_id=entry.establishment_id,
                establishment_name=entry.establishment_name,
                presentation_id=entry.presentation_id,
                presentation_name=entry.presentation_name,
                reported_at=entry.reported_at,
                raw_price=entry.raw_price,
                normalized_ref_price=entry.normalized_ref_price,
                reference_unit_label=entry.reference_unit_label,
                source_type=entry.source_type,
                reliability_status=entry.reliability_status,
                validity_status=entry.validity_status,
                confidence_score=entry.confidence_score,
                is_promotional=entry.is_promotional,
                promotion_description=entry.promotion_description,
                requires_warning=requires_warning,
            )
            grouped_points[entry.establishment_id].append(point)
            establishment_names[entry.establishment_id] = entry.establishment_name

        series_list: list[EstablishmentPriceTrendSeries] = []
        total_points = 0

        for est_id in sorted(grouped_points.keys()):
            raw_pts = grouped_points[est_id]
            # Orden cronológico ascendente (del más antiguo dentro de los 90 días al más reciente)
            sorted_pts = tuple(sorted(raw_pts, key=lambda p: (p.reported_at, p.report_id)))
            total_points += len(sorted_pts)

            norm_prices = [p.normalized_ref_price for p in sorted_pts]
            first_price = norm_prices[0]
            latest_price = norm_prices[-1]
            min_price = min(norm_prices)
            max_price = max(norm_prices)
            avg_price = (sum(norm_prices, Decimal("0.00")) / Decimal(len(norm_prices))).quantize(
                cls.TWO_DECIMALS, rounding=ROUND_HALF_UP
            )

            variation_amount = (latest_price - first_price).quantize(
                cls.TWO_DECIMALS, rounding=ROUND_HALF_UP
            )
            if first_price > Decimal("0.00"):
                variation_pct = ((variation_amount / first_price) * Decimal(100)).quantize(
                    cls.TWO_DECIMALS, rounding=ROUND_HALF_UP
                )
            else:
                variation_pct = Decimal("0.00")

            if variation_amount > Decimal("0.00"):
                direction = TrendDirection.UP
            elif variation_amount < Decimal("0.00"):
                direction = TrendDirection.DOWN
            else:
                direction = TrendDirection.STABLE

            series_list.append(
                EstablishmentPriceTrendSeries(
                    establishment_id=est_id,
                    establishment_name=establishment_names[est_id],
                    reference_unit_label=sorted_pts[-1].reference_unit_label,
                    points_count=len(sorted_pts),
                    first_normalized_price=first_price,
                    latest_normalized_price=latest_price,
                    min_normalized_price=min_price,
                    max_normalized_price=max_price,
                    avg_normalized_price=avg_price,
                    variation_amount=variation_amount,
                    variation_percentage=variation_pct,
                    trend_direction=direction,
                    points=sorted_pts,
                )
            )

        return ProductPriceHistoryOutput(
            product_id=product_id,
            window_days=window_days,
            cutoff_start_at=cutoff_start,
            evaluated_at=evaluated_at,
            total_points=total_points,
            excluded_out_of_window_count=excluded_out_of_window,
            excluded_anomalous_count=excluded_anomalous,
            establishment_series=tuple(series_list),
        )

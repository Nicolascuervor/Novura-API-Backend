"""
Suite TDD Unitaria para A2: Historial y Tendencia de Precios de 90 Días (`core_domain/price_history.py`).
Verifica el escenario de calidad EC-08 (ISO/IEC 25012: Trazabilidad y actualidad del dato) y ADR-13:
1. Ventana estricta de los últimos 90 días sin sobrescribir valores históricos (Append-Only).
2. Distinción obligatoria del origen (`source_type`) y estado de confiabilidad (`reliability_status`) en cada punto.
3. Exclusión del 100 % de precios `ANOMALOUS` y marcación preventiva de `LOW_CONFIDENCE`.
4. Comparación de tendencia entre dos o más establecimientos en la misma gráfica (Extensión opcional A2).
5. Cálculo exacto con `Decimal` de la variación porcentual y dirección de tendencia (`UP`, `DOWN`, `STABLE`).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from core_domain.entities import (
    ComparablePriceEntry,
    ReliabilityStatus,
    SourceType,
    ValidityStatus,
)
from core_domain.price_history import (
    InvalidPriceHistoryWindowError,
    PriceHistoryService,
    TrendDirection,
)


def _make_entry(
    *,
    report_id: int,
    establishment_id: int = 1,
    establishment_name: str = "Supermercado Ara Centro",
    presentation_id: int = 10,
    presentation_name: str = "Diana Bolsa 1000g",
    raw_price: str = "4200.00",
    normalized_ref_price: str = "420.00",
    reference_unit_label: str = "100g",
    reported_at: datetime,
    validity_status: ValidityStatus = ValidityStatus.VALID,
    reliability_status: ReliabilityStatus = ReliabilityStatus.VERIFIED,
    confidence_score: str = "0.95",
    source_type: SourceType = SourceType.COMMUNITY_FREQUENT,
    is_promotional: bool = False,
) -> ComparablePriceEntry:
    return ComparablePriceEntry(
        report_id=report_id,
        establishment_id=establishment_id,
        establishment_name=establishment_name,
        presentation_id=presentation_id,
        presentation_name=presentation_name,
        raw_price=Decimal(raw_price),
        normalized_ref_price=Decimal(normalized_ref_price),
        reference_unit_label=reference_unit_label,
        reported_at=reported_at,
        validity_status=validity_status,
        reliability_status=reliability_status,
        freshness_score=Decimal("0.90"),
        confidence_score=Decimal(confidence_score),
        source_type=source_type,
        is_promotional=is_promotional,
    )


class TestPriceHistoryServiceTDD:
    """Pruebas unitarias TDD para la construcción de series históricas de 90 días (A2 / EC-08)."""

    def test_builds_90_day_chronological_series_preserving_superseded_and_expired_history(self) -> None:
        """
        Regla A2.1 y A2.2: El historial conserva cambios de precio anteriores (incluso aquellos que hoy
        están SUPERSEDED o EXPIRED para comparación inmediata) dentro de los últimos 90 días,
        y excluye registros con más de 90 días de antigüedad.
        """
        now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
        entries = [
            # Hace 105 días -> Fuera de la ventana de 90 días (debe excluirse)
            _make_entry(
                report_id=1,
                raw_price="3800.00",
                normalized_ref_price="380.00",
                reported_at=now - timedelta(days=105),
                validity_status=ValidityStatus.EXPIRED,
            ),
            # Hace 60 días -> Dentro de los 90 días (aunque hoy esté SUPERSEDED, entra al historial!)
            _make_entry(
                report_id=2,
                raw_price="4000.00",
                normalized_ref_price="400.00",
                reported_at=now - timedelta(days=60),
                validity_status=ValidityStatus.SUPERSEDED,
                source_type=SourceType.COMMUNITY_OCCASIONAL,
            ),
            # Hace 15 días -> Precio oficial de comercio
            _make_entry(
                report_id=3,
                raw_price="4200.00",
                normalized_ref_price="420.00",
                reported_at=now - timedelta(days=15),
                validity_status=ValidityStatus.SUPERSEDED,
                source_type=SourceType.OFFICIAL_MERCHANT,
            ),
            # Hoy -> Precio vigente actual
            _make_entry(
                report_id=4,
                raw_price="4500.00",
                normalized_ref_price="450.00",
                reported_at=now - timedelta(hours=2),
                validity_status=ValidityStatus.VALID,
                source_type=SourceType.COMMUNITY_FREQUENT,
            ),
        ]

        output = PriceHistoryService.build_history(
            product_id=100,
            entries=entries,
            evaluated_at=now,
            window_days=90,
        )

        assert output.window_days == 90
        assert output.total_points == 3
        assert output.excluded_out_of_window_count == 1
        assert output.excluded_anomalous_count == 0
        assert len(output.establishment_series) == 1

        series = output.establishment_series[0]
        assert series.establishment_id == 1
        assert [p.report_id for p in series.points] == [2, 3, 4]
        assert [p.source_type for p in series.points] == [
            SourceType.COMMUNITY_OCCASIONAL,
            SourceType.OFFICIAL_MERCHANT,
            SourceType.COMMUNITY_FREQUENT,
        ]
        # Variación de 400.00 a 450.00 = +50.00 (+12.50%) -> UP
        assert series.first_normalized_price == Decimal("400.00")
        assert series.latest_normalized_price == Decimal("450.00")
        assert series.min_normalized_price == Decimal("400.00")
        assert series.max_normalized_price == Decimal("450.00")
        assert series.variation_amount == Decimal("50.00")
        assert series.variation_percentage == Decimal("12.50")
        assert series.trend_direction == TrendDirection.UP

    def test_excludes_anomalous_prices_and_flags_low_confidence_points(self) -> None:
        """
        Regla ADR-13 (Pregunta 2 de A2):
        - Los precios ANOMALOUS se excluyen siempre para no distorsionar la tendencia con sabotajes.
        - Los precios LOW_CONFIDENCE se incluyen por defecto con `requires_warning=True`, o se filtran
          si el consumidor solicita `include_low_confidence=False`.
        """
        now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
        entries = [
            _make_entry(
                report_id=10,
                normalized_ref_price="500.00",
                reported_at=now - timedelta(days=20),
                reliability_status=ReliabilityStatus.VERIFIED,
            ),
            _make_entry(
                report_id=11,
                normalized_ref_price="360.00",
                reported_at=now - timedelta(days=10),
                reliability_status=ReliabilityStatus.LOW_CONFIDENCE,
                confidence_score="0.55",
            ),
            _make_entry(
                report_id=12,
                normalized_ref_price="9999.00",
                reported_at=now - timedelta(days=5),
                reliability_status=ReliabilityStatus.ANOMALOUS,
                confidence_score="0.10",
            ),
        ]

        with_low_conf = PriceHistoryService.build_history(
            product_id=100,
            entries=entries,
            evaluated_at=now,
            window_days=90,
            include_low_confidence=True,
        )
        assert with_low_conf.total_points == 2
        assert with_low_conf.excluded_anomalous_count == 1
        pts = with_low_conf.establishment_series[0].points
        assert pts[0].report_id == 10 and pts[0].requires_warning is False
        assert pts[1].report_id == 11 and pts[1].requires_warning is True
        assert pts[1].reliability_status == ReliabilityStatus.LOW_CONFIDENCE

        without_low_conf = PriceHistoryService.build_history(
            product_id=100,
            entries=entries,
            evaluated_at=now,
            window_days=90,
            include_low_confidence=False,
        )
        assert without_low_conf.total_points == 1
        assert [p.report_id for p in without_low_conf.establishment_series[0].points] == [10]

    def test_compares_trend_between_two_establishments_in_same_chart_output(self) -> None:
        """
        Extensión opcional A2: Comparar la tendencia de un producto entre dos establecimientos
        en la misma respuesta estructurada, filtrando por `establishment_ids`.
        """
        now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
        entries = [
            # Establecimiento 1 (Tiendas Ara): bajó de 500 a 450 (-10.00% -> DOWN)
            _make_entry(
                report_id=21,
                establishment_id=1,
                establishment_name="Tiendas Ara",
                normalized_ref_price="500.00",
                reported_at=now - timedelta(days=30),
            ),
            _make_entry(
                report_id=22,
                establishment_id=1,
                establishment_name="Tiendas Ara",
                normalized_ref_price="450.00",
                reported_at=now - timedelta(days=2),
            ),
            # Establecimiento 2 (Tiendas D1): se mantuvo estable en 460 (0.00% -> STABLE)
            _make_entry(
                report_id=23,
                establishment_id=2,
                establishment_name="Tiendas D1",
                normalized_ref_price="460.00",
                reported_at=now - timedelta(days=25),
                source_type=SourceType.OFFICIAL_MERCHANT,
            ),
            _make_entry(
                report_id=24,
                establishment_id=2,
                establishment_name="Tiendas D1",
                normalized_ref_price="460.00",
                reported_at=now - timedelta(days=1),
                source_type=SourceType.OFFICIAL_MERCHANT,
            ),
            # Establecimiento 3 (Carulla): no solicitado en el filtro de 2 comercios
            _make_entry(
                report_id=25,
                establishment_id=3,
                establishment_name="Carulla",
                normalized_ref_price="620.00",
                reported_at=now - timedelta(days=5),
            ),
        ]

        output = PriceHistoryService.build_history(
            product_id=100,
            entries=entries,
            evaluated_at=now,
            window_days=90,
            establishment_ids={1, 2},
        )

        assert len(output.establishment_series) == 2
        series_ara, series_d1 = output.establishment_series[0], output.establishment_series[1]

        assert series_ara.establishment_id == 1
        assert series_ara.trend_direction == TrendDirection.DOWN
        assert series_ara.variation_percentage == Decimal("-10.00")

        assert series_d1.establishment_id == 2
        assert series_d1.trend_direction == TrendDirection.STABLE
        assert series_d1.variation_percentage == Decimal("0.00")

    def test_rejects_invalid_window_days_outside_1_to_90_range(self) -> None:
        """Valida que la ventana consultada esté entre 1 y 90 días (EC-08 / ADR-13)."""
        now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
        with pytest.raises(InvalidPriceHistoryWindowError):
            PriceHistoryService.build_history(
                product_id=100,
                entries=[],
                evaluated_at=now,
                window_days=0,
            )
        with pytest.raises(InvalidPriceHistoryWindowError):
            PriceHistoryService.build_history(
                product_id=100,
                entries=[],
                evaluated_at=now,
                window_days=91,
            )

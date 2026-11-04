"""
Pruebas TDD para M-02 (Neutralidad de comparación EC-06) y M-05 (Detección de reportes anómalos EC-03).
Metas:
- M-02: X = 1.00 (100% neutralidad y distinción explícita de pautas/promociones).
- M-05: X >= 0.80 (Deseable >= 0.90 en detección de reportes anómalos sobre el set de prueba).
"""

import unittest
from datetime import UTC, datetime
from decimal import Decimal

from core_domain.anomaly_detector import AnomalyDetector, HistoricalPriceContext
from core_domain.entities import (
    ComparablePriceEntry,
    ReliabilityStatus,
    SourceType,
    ValidityStatus,
)
from core_domain.neutral_comparator import NeutralComparator, SortCriterion


class TestNeutralComparatorTDD(unittest.TestCase):
    """Casos de prueba TDD para la neutralidad de la comparación (EC-06, M-02)."""

    def setUp(self) -> None:
        self.now = datetime(2026, 11, 2, 14, 0, 0, tzinfo=UTC)

    def _entry(
        self,
        report_id: int,
        establishment_id: int,
        name: str,
        raw_price: str,
        norm_price: str,
        is_promotional: bool = False,
        promo_desc: str | None = None,
        validity: ValidityStatus = ValidityStatus.VALID,
        reliability: ReliabilityStatus = ReliabilityStatus.VERIFIED,
        source: SourceType = SourceType.COMMUNITY_OCCASIONAL,
    ) -> ComparablePriceEntry:
        return ComparablePriceEntry(
            report_id=report_id,
            establishment_id=establishment_id,
            establishment_name=name,
            presentation_id=1,
            presentation_name="Arroz 1kg",
            raw_price=Decimal(raw_price),
            normalized_ref_price=Decimal(norm_price),
            reference_unit_label="100g",
            reported_at=self.now,
            validity_status=validity,
            reliability_status=reliability,
            freshness_score=Decimal("0.95"),
            confidence_score=Decimal("0.90") if reliability == ReliabilityStatus.VERIFIED else Decimal("0.30"),
            source_type=source,
            is_promotional=is_promotional,
            promotion_description=promo_desc,
        )

    def test_strict_order_by_normalized_unit_price_ignoring_commercial_relationship(self) -> None:
        # Un supermercado con perfil oficial y promoción tiene precio mayor por 100g que una tienda de barrio
        entries = [
            self._entry(
                1, 10, "Supermercado Cadena X", "4800", "480.00",
                is_promotional=True, promo_desc="Oferta patrocinada",
                source=SourceType.OFFICIAL_MERCHANT,
            ),
            self._entry(
                2, 20, "Tienda de Barrio El Paisa", "4200", "420.00",
                is_promotional=False,
                source=SourceType.COMMUNITY_OCCASIONAL,
            ),
            self._entry(
                3, 30, "Minimercado La 14", "4500", "450.00",
                is_promotional=False,
                source=SourceType.COMMUNITY_FREQUENT,
            ),
        ]

        result = NeutralComparator.compare(
            entries=entries,
            criterion=SortCriterion.UNIT_PRICE_ASC,
        )

        # El orden del ranking principal debe ser estrictamente 420.00 -> 450.00 -> 480.00
        ordered_ids = [item.report_id for item in result.ranked_results]
        self.assertEqual(ordered_ids, [2, 3, 1])

        # Todo contenido promocional se distingue explícitamente en el 100% de los casos (EC-06)
        promo_item = result.ranked_results[2]
        self.assertTrue(promo_item.is_promotional)
        self.assertIn("CONTENIDO PROMOCIONAL", " ".join(promo_item.warning_messages))
        self.assertEqual(len(result.promotional_highlights), 1)
        self.assertEqual(result.promotional_highlights[0].report_id, 1)

    def test_expired_and_anomalous_entries_excluded_from_valid_ranking_or_warned(self) -> None:
        # EC-02 y EC-03: Los precios vencidos no se muestran como vigentes;
        # los datos no confiables no se presentan como vigentes sin advertencia.
        entries = [
            self._entry(1, 10, "Tienda A", "4000", "400.00", validity=ValidityStatus.VALID),
            self._entry(2, 20, "Tienda B", "3500", "350.00", validity=ValidityStatus.EXPIRED),
            self._entry(3, 30, "Tienda C", "2000", "200.00", reliability=ReliabilityStatus.ANOMALOUS),
            self._entry(4, 40, "Tienda D", "3900", "390.00", reliability=ReliabilityStatus.LOW_CONFIDENCE),
        ]

        result = NeutralComparator.compare(
            entries=entries,
            criterion=SortCriterion.UNIT_PRICE_ASC,
            include_low_confidence_with_warning=True,
        )

        # El vencido (id=2) y el anómalo (id=3) no aparecen como vigentes en el ranking principal
        ranked_ids = [item.report_id for item in result.ranked_results]
        self.assertNotIn(2, ranked_ids)
        self.assertNotIn(3, ranked_ids)
        self.assertEqual(ranked_ids, [4, 1])

        # El de baja confianza (id=4) lleva etiqueta de advertencia obligatoria
        low_conf_item = result.ranked_results[0]
        self.assertTrue(low_conf_item.requires_warning_label)
        self.assertTrue(any("confiabilidad" in msg.lower() for msg in low_conf_item.warning_messages))

        # Si el usuario pide excluir baja confianza, solo queda id=1
        strict_result = NeutralComparator.compare(
            entries=entries,
            criterion=SortCriterion.UNIT_PRICE_ASC,
            include_low_confidence_with_warning=False,
        )
        self.assertEqual([item.report_id for item in strict_result.ranked_results], [1])
        self.assertEqual(strict_result.excluded_count, 3)

    def test_sort_by_raw_price_and_freshness_and_stale_warning(self) -> None:
        e_stale = self._entry(
            1, 10, "Tienda A", "3800", "420.00", validity=ValidityStatus.STALE_WARNING
        )
        e_fresh = self._entry(
            2, 20, "Tienda B", "4100", "410.00", validity=ValidityStatus.VALID
        )
        res_raw = NeutralComparator.compare([e_fresh, e_stale], criterion=SortCriterion.RAW_PRICE_ASC)
        self.assertEqual([i.report_id for i in res_raw.ranked_results], [1, 2])
        self.assertTrue(any("vigencia" in m.lower() for m in res_raw.ranked_results[0].warning_messages))

        res_fresh = NeutralComparator.compare([e_stale, e_fresh], criterion=SortCriterion.FRESHNESS_DESC)
        self.assertEqual(res_fresh.declared_criterion, SortCriterion.FRESHNESS_DESC)


class TestAnomalyDetectorTDD(unittest.TestCase):
    """
    Casos de prueba TDD para detección de reportes falsos o coordinados (EC-03, M-05).
    Evalúa tanto casos individuales como el conjunto de prueba de reportes anómalos (E4).
    """

    def setUp(self) -> None:
        self.detector = AnomalyDetector()
        # Contexto histórico para una bolsa de leche de 1L en Armenia: mediana $4,400 COP
        self.context = HistoricalPriceContext(
            historical_prices=(
                Decimal(4200),
                Decimal(4300),
                Decimal(4400),
                Decimal(4400),
                Decimal(4500),
                Decimal(4600),
            ),
            recent_reports_by_same_user_last_10m=0,
            distinct_users_reporting_same_outlier_last_15m=0,
        )

    def test_legitimate_price_within_normal_range_is_verified(self) -> None:
        assessment = self.detector.evaluate(
            reported_price=Decimal(4350),
            context=self.context,
            source_type=SourceType.COMMUNITY_OCCASIONAL,
        )
        self.assertEqual(assessment.status, ReliabilityStatus.VERIFIED)
        self.assertTrue(assessment.is_reliable)
        self.assertGreaterEqual(assessment.confidence_score, Decimal("0.80"))

    def test_extreme_low_or_high_price_is_flagged_as_anomalous(self) -> None:
        # Sabotaje o error de digitación: $500 COP o $44,000 COP cuando la mediana es $4,400 COP
        low_sabotage = self.detector.evaluate(
            reported_price=Decimal(500),
            context=self.context,
        )
        high_sabotage = self.detector.evaluate(
            reported_price=Decimal(44000),
            context=self.context,
        )
        self.assertEqual(low_sabotage.status, ReliabilityStatus.ANOMALOUS)
        self.assertFalse(low_sabotage.is_reliable)
        self.assertEqual(high_sabotage.status, ReliabilityStatus.ANOMALOUS)
        self.assertFalse(high_sabotage.is_reliable)

    def test_coordinated_group_attack_or_user_spam_burst_is_flagged(self) -> None:
        # EC-03: "Un usuario, o un grupo coordinado, registra precios falsos de un establecimiento"
        coordinated_context = HistoricalPriceContext(
            historical_prices=self.context.historical_prices,
            recent_reports_by_same_user_last_10m=6,
            distinct_users_reporting_same_outlier_last_15m=4,
        )
        assessment = self.detector.evaluate(
            reported_price=Decimal(3100),  # ~30% abajo en ataque coordinado
            context=coordinated_context,
        )
        self.assertEqual(assessment.status, ReliabilityStatus.ANOMALOUS)
        self.assertFalse(assessment.is_reliable)

    def test_m05_anomalous_dataset_detection_rate_exceeds_threshold(self) -> None:
        """
        Medida M-05 (ISO/IEC 25023 - Evidencia E4):
        X = A / B (A = reportes anómalos del set de prueba marcados como no confiables; B = total inyectados).
        Umbral aceptable >= 0.80, Meta deseable >= 0.90.
        """
        anomalous_dataset = [
            # (precio_inyectado, reportes_usuario_10m, usuarios_coordinados_15m, descripción)
            (Decimal(100), 0, 0, "Precio absurdo casi cero"),
            (Decimal(1200), 0, 0, "Precio dumping falso -72%"),
            (Decimal(2500), 0, 0, "Precio falso competidor -43%"),
            (Decimal(7500), 0, 0, "Inflación falsa contra competidor +70%"),
            (Decimal(44000), 0, 0, "Error de digitación un cero de más"),
            (Decimal(3200), 5, 0, "Ráfaga de spam de un mismo usuario"),
            (Decimal(3300), 0, 4, "Ataque coordinado de cuentas nuevas"),
            (Decimal(2900), 2, 3, "Brigada coordinada bajando precio artificialmente"),
            (Decimal(6200), 0, 3, "Brigada coordinada subiendo precio de tienda vecina"),
            (Decimal(1900), 1, 0, "Desviación severa bajo el piso histórico"),
        ]

        detected = 0
        for price, user_burst, coord_count, _desc in anomalous_dataset:
            ctx = HistoricalPriceContext(
                historical_prices=self.context.historical_prices,
                recent_reports_by_same_user_last_10m=user_burst,
                distinct_users_reporting_same_outlier_last_15m=coord_count,
            )
            res = self.detector.evaluate(reported_price=price, context=ctx)
            if not res.is_reliable:
                detected += 1

        detection_rate = Decimal(detected) / Decimal(len(anomalous_dataset))
        self.assertGreaterEqual(
            detection_rate,
            Decimal("0.90"),
            f"M-05 no alcanzó la meta deseable de 0.90: obtuvo {detection_rate}",
        )


if __name__ == "__main__":
    unittest.main()

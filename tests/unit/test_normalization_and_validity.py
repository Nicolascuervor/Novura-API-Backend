"""
Pruebas TDD para M-01: Normalización de precios por unidad de medida y política de vigencia (EC-02).
Meta mínima y deseable: X = 1.00 (100% de los casos aprobados).
"""

import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from core_domain.entities import (
    BaseDimension,
    ProductCategory,
    UnitOfMeasure,
    ValidityStatus,
)
from core_domain.unit_normalizer import InvalidNormalizationInputError, UnitNormalizer
from core_domain.validity_policy import ValidityPolicy


class TestUnitNormalizerTDD(unittest.TestCase):
    """Casos de prueba TDD para la normalización de precios por unidad de medida (M-01)."""

    def test_normalize_grams_to_reference_100g(self) -> None:
        # Ej. Café 500g a $18,500 COP -> $3,700 COP por 100g ($37/g)
        result = UnitNormalizer.normalize(
            raw_price=Decimal(18500),
            quantity=Decimal(500),
            unit=UnitOfMeasure.GRAM,
        )
        self.assertEqual(result.dimension, BaseDimension.MASS)
        self.assertEqual(result.reference_unit_label, "100g")
        self.assertEqual(result.price_per_base_unit, Decimal("37.0000"))
        self.assertEqual(result.price_per_ref_unit, Decimal("3700.00"))

    def test_normalize_kilograms_to_reference_100g(self) -> None:
        # Ej. Arroz 2.5 kg (2500g) a $11,250 COP -> $450 COP por 100g ($4.50/g)
        result = UnitNormalizer.normalize(
            raw_price=Decimal(11250),
            quantity=Decimal("2.5"),
            unit=UnitOfMeasure.KILOGRAM,
        )
        self.assertEqual(result.dimension, BaseDimension.MASS)
        self.assertEqual(result.reference_unit_label, "100g")
        self.assertEqual(result.price_per_base_unit, Decimal("4.5000"))
        self.assertEqual(result.price_per_ref_unit, Decimal("450.00"))

    def test_normalize_colombian_pound_500g_to_reference_100g(self) -> None:
        # En Colombia 1 libra comercial de abarrotes equivale a 500g
        # Ej. Panela 1 lb (500g) a $3,200 COP -> $640 COP por 100g
        result = UnitNormalizer.normalize(
            raw_price=Decimal(3200),
            quantity=Decimal(1),
            unit=UnitOfMeasure.POUND,
        )
        self.assertEqual(result.dimension, BaseDimension.MASS)
        self.assertEqual(result.price_per_ref_unit, Decimal("640.00"))

    def test_normalize_liters_and_milliliters_to_reference_100ml(self) -> None:
        # Leche 900 ml a $4,500 COP -> $500 por 100ml
        res_ml = UnitNormalizer.normalize(
            raw_price=Decimal(4500),
            quantity=Decimal(900),
            unit=UnitOfMeasure.MILLILITER,
        )
        # Leche 1.1 L (1100 ml) a $5,280 COP -> $480 por 100ml (más económico por unidad de medida)
        res_l = UnitNormalizer.normalize(
            raw_price=Decimal(5280),
            quantity=Decimal("1.1"),
            unit=UnitOfMeasure.LITER,
        )
        self.assertEqual(res_ml.dimension, BaseDimension.VOLUME)
        self.assertEqual(res_ml.price_per_ref_unit, Decimal("500.00"))
        self.assertEqual(res_l.price_per_ref_unit, Decimal("480.00"))
        self.assertLess(res_l.price_per_ref_unit, res_ml.price_per_ref_unit)

    def test_normalize_cubic_centimeters_equals_milliliters(self) -> None:
        result = UnitNormalizer.normalize(
            raw_price=Decimal(3000),
            quantity=Decimal(250),
            unit=UnitOfMeasure.CUBIC_CENTIMETER,
        )
        self.assertEqual(result.dimension, BaseDimension.VOLUME)
        self.assertEqual(result.reference_unit_label, "100ml")
        self.assertEqual(result.price_per_ref_unit, Decimal("1200.00"))

    def test_normalize_units_count_dimension(self) -> None:
        # Cubeta de 30 huevos a $16,500 COP -> $550 por 1 und
        result = UnitNormalizer.normalize(
            raw_price=Decimal(16500),
            quantity=Decimal(30),
            unit=UnitOfMeasure.UNIT,
        )
        self.assertEqual(result.dimension, BaseDimension.COUNT)
        self.assertEqual(result.reference_unit_label, "1 und")
        self.assertEqual(result.price_per_ref_unit, Decimal("550.00"))

    def test_reject_non_positive_price_or_quantity(self) -> None:
        with self.assertRaises(InvalidNormalizationInputError):
            UnitNormalizer.normalize(Decimal(0), Decimal(500), UnitOfMeasure.GRAM)
        with self.assertRaises(InvalidNormalizationInputError):
            UnitNormalizer.normalize(Decimal(-1500), Decimal(500), UnitOfMeasure.GRAM)
        with self.assertRaises(InvalidNormalizationInputError):
            UnitNormalizer.normalize(Decimal(5000), Decimal(0), UnitOfMeasure.GRAM)

    def test_verify_compatible_dimensions_for_comparison(self) -> None:
        self.assertTrue(
            UnitNormalizer.are_compatible(UnitOfMeasure.GRAM, UnitOfMeasure.KILOGRAM)
        )
        self.assertTrue(
            UnitNormalizer.are_compatible(UnitOfMeasure.MILLILITER, UnitOfMeasure.LITER)
        )
        self.assertFalse(
            UnitNormalizer.are_compatible(UnitOfMeasure.GRAM, UnitOfMeasure.LITER)
        )


class TestValidityPolicyTDD(unittest.TestCase):
    """Casos de prueba TDD para la regla de vigencia y actualidad del dato (EC-02, M-01)."""

    def setUp(self) -> None:
        self.now = datetime(2026, 11, 2, 12, 0, 0, tzinfo=UTC)
        self.policy = ValidityPolicy()

    def test_recent_report_is_valid_with_high_freshness(self) -> None:
        reported_at = self.now - timedelta(hours=6)
        assessment = self.policy.evaluate(
            reported_at=reported_at,
            evaluated_at=self.now,
            category=ProductCategory.GROCERY,
        )
        self.assertEqual(assessment.status, ValidityStatus.VALID)
        self.assertTrue(assessment.is_currently_valid)
        self.assertGreaterEqual(assessment.freshness_score, Decimal("0.90"))

    def test_perishable_product_expires_after_5_days_per_adr04(self) -> None:
        reported_at = self.now - timedelta(days=6)
        assessment = self.policy.evaluate(
            reported_at=reported_at,
            evaluated_at=self.now,
            category=ProductCategory.PERISHABLE,
        )
        self.assertEqual(assessment.status, ValidityStatus.EXPIRED)
        self.assertFalse(assessment.is_currently_valid)
        self.assertEqual(assessment.freshness_score, Decimal("0.00"))

    def test_fruits_veggies_product_expires_after_5_days_per_adr04(self) -> None:
        reported_at = self.now - timedelta(days=6)
        assessment = self.policy.evaluate(
            reported_at=reported_at,
            evaluated_at=self.now,
            category=ProductCategory.FRUITS_VEGGIES,
        )
        self.assertEqual(assessment.status, ValidityStatus.EXPIRED)
        self.assertFalse(assessment.is_currently_valid)
        self.assertEqual(assessment.freshness_score, Decimal("0.00"))

    def test_cleaning_product_warns_between_day_7_and_15_per_adr04(self) -> None:
        reported_at = self.now - timedelta(days=10)
        assessment = self.policy.evaluate(
            reported_at=reported_at,
            evaluated_at=self.now,
            category=ProductCategory.CLEANING,
        )
        self.assertEqual(assessment.status, ValidityStatus.STALE_WARNING)
        self.assertTrue(assessment.is_currently_valid)

    def test_cleaning_product_expires_after_15_days_per_adr04(self) -> None:
        reported_at = self.now - timedelta(days=16)
        assessment = self.policy.evaluate(
            reported_at=reported_at,
            evaluated_at=self.now,
            category=ProductCategory.CLEANING,
        )
        self.assertEqual(assessment.status, ValidityStatus.EXPIRED)
        self.assertFalse(assessment.is_currently_valid)

    def test_high_volatility_exact_hour_boundaries_adr04(self) -> None:
        # ADR-04: Alta volatilidad vigente hasta 48h, advertencia hasta 120h, excluido después.
        for cat in (ProductCategory.FRUITS_VEGGIES, ProductCategory.PERISHABLE):
            # 47 horas -> VIGENTE (VALID)
            v_47 = self.policy.evaluate(self.now - timedelta(hours=47), self.now, category=cat)
            self.assertEqual(v_47.status, ValidityStatus.VALID, f"Falla en 47h para {cat}")
            self.assertTrue(v_47.is_currently_valid)

            # 49 horas -> ADVERTENCIA (STALE_WARNING)
            v_49 = self.policy.evaluate(self.now - timedelta(hours=49), self.now, category=cat)
            self.assertEqual(v_49.status, ValidityStatus.STALE_WARNING, f"Falla en 49h para {cat}")
            self.assertTrue(v_49.is_currently_valid)

            # 121 horas -> EXPIRADO (EXPIRED)
            v_121 = self.policy.evaluate(self.now - timedelta(hours=121), self.now, category=cat)
            self.assertEqual(v_121.status, ValidityStatus.EXPIRED, f"Falla en 121h para {cat}")
            self.assertFalse(v_121.is_currently_valid)

    def test_low_volatility_exact_hour_boundaries_adr04(self) -> None:
        # ADR-04: Baja volatilidad vigente hasta 168h (7d), advertencia hasta 360h (15d), excluido después.
        for cat in (ProductCategory.GROCERY, ProductCategory.BEVERAGES, ProductCategory.PERSONAL_CARE, ProductCategory.CLEANING):
            # 167 horas -> VIGENTE (VALID)
            v_167 = self.policy.evaluate(self.now - timedelta(hours=167), self.now, category=cat)
            self.assertEqual(v_167.status, ValidityStatus.VALID, f"Falla en 167h para {cat}")
            self.assertTrue(v_167.is_currently_valid)

            # 169 horas -> ADVERTENCIA (STALE_WARNING)
            v_169 = self.policy.evaluate(self.now - timedelta(hours=169), self.now, category=cat)
            self.assertEqual(v_169.status, ValidityStatus.STALE_WARNING, f"Falla en 169h para {cat}")
            self.assertTrue(v_169.is_currently_valid)

            # 361 horas -> EXPIRADO (EXPIRED)
            v_361 = self.policy.evaluate(self.now - timedelta(hours=361), self.now, category=cat)
            self.assertEqual(v_361.status, ValidityStatus.EXPIRED, f"Falla en 361h para {cat}")
            self.assertFalse(v_361.is_currently_valid)

    def test_exact_sub_minute_threshold_boundaries_48_120_168_360_hours(self) -> None:
        """
        Verifica con precisión de centésimas de hora los umbrales exactos de ADR-04:
        - 48.00h (advertencia alta volatilidad)
        - 120.00h (expiración alta volatilidad)
        - 168.00h (advertencia baja volatilidad)
        - 360.00h (expiración baja volatilidad)
        evaluando los instantes inmediatamente anteriores y posteriores.
        """
        # --- ALTA VOLATILIDAD (FRUITS_VEGGIES y PERISHABLE) ---
        for cat in (ProductCategory.FRUITS_VEGGIES, ProductCategory.PERISHABLE):
            # 1. Frontera de 48 horas (2 días)
            t_47_99 = self.now - timedelta(seconds=47 * 3600 + 3564)  # 47.99 horas
            res_47_99 = self.policy.evaluate(t_47_99, self.now, category=cat)
            self.assertEqual(res_47_99.status, ValidityStatus.VALID, "47.99h debe ser VALID")
            self.assertTrue(res_47_99.is_currently_valid)

            t_48_00 = self.now - timedelta(hours=48)                   # 48.00 horas exactas
            res_48_00 = self.policy.evaluate(t_48_00, self.now, category=cat)
            self.assertEqual(res_48_00.status, ValidityStatus.STALE_WARNING, "48.00h exactas debe ser STALE_WARNING")
            self.assertTrue(res_48_00.is_currently_valid)

            t_48_01 = self.now - timedelta(seconds=48 * 3600 + 36)    # 48.01 horas
            res_48_01 = self.policy.evaluate(t_48_01, self.now, category=cat)
            self.assertEqual(res_48_01.status, ValidityStatus.STALE_WARNING, "48.01h debe ser STALE_WARNING")
            self.assertTrue(res_48_01.is_currently_valid)

            # 2. Frontera de 120 horas (5 días)
            t_119_99 = self.now - timedelta(seconds=120 * 3600 - 36)  # 119.99 horas
            res_119_99 = self.policy.evaluate(t_119_99, self.now, category=cat)
            self.assertEqual(res_119_99.status, ValidityStatus.STALE_WARNING, "119.99h debe ser STALE_WARNING")
            self.assertTrue(res_119_99.is_currently_valid)

            t_120_00 = self.now - timedelta(hours=120)                # 120.00 horas exactas
            res_120_00 = self.policy.evaluate(t_120_00, self.now, category=cat)
            self.assertEqual(res_120_00.status, ValidityStatus.STALE_WARNING, "120.00h exactas no ha expirado aún")
            self.assertTrue(res_120_00.is_currently_valid)

            t_120_01 = self.now - timedelta(seconds=120 * 3600 + 36)  # 120.01 horas
            res_120_01 = self.policy.evaluate(t_120_01, self.now, category=cat)
            self.assertEqual(res_120_01.status, ValidityStatus.EXPIRED, "120.01h debe ser EXPIRED")
            self.assertFalse(res_120_01.is_currently_valid)

        # --- BAJA VOLATILIDAD (GROCERY, BEVERAGES, PERSONAL_CARE, CLEANING) ---
        for cat in (ProductCategory.GROCERY, ProductCategory.BEVERAGES, ProductCategory.PERSONAL_CARE, ProductCategory.CLEANING):
            # 1. Frontera de 168 horas (7 días)
            t_167_99 = self.now - timedelta(seconds=168 * 3600 - 36)  # 167.99 horas
            res_167_99 = self.policy.evaluate(t_167_99, self.now, category=cat)
            self.assertEqual(res_167_99.status, ValidityStatus.VALID, "167.99h debe ser VALID")
            self.assertTrue(res_167_99.is_currently_valid)

            t_168_00 = self.now - timedelta(hours=168)                # 168.00 horas exactas
            res_168_00 = self.policy.evaluate(t_168_00, self.now, category=cat)
            self.assertEqual(res_168_00.status, ValidityStatus.STALE_WARNING, "168.00h exactas debe ser STALE_WARNING")
            self.assertTrue(res_168_00.is_currently_valid)

            t_168_01 = self.now - timedelta(seconds=168 * 3600 + 36)  # 168.01 horas
            res_168_01 = self.policy.evaluate(t_168_01, self.now, category=cat)
            self.assertEqual(res_168_01.status, ValidityStatus.STALE_WARNING, "168.01h debe ser STALE_WARNING")
            self.assertTrue(res_168_01.is_currently_valid)

            # 2. Frontera de 360 horas (15 días)
            t_359_99 = self.now - timedelta(seconds=360 * 3600 - 36)  # 359.99 horas
            res_359_99 = self.policy.evaluate(t_359_99, self.now, category=cat)
            self.assertEqual(res_359_99.status, ValidityStatus.STALE_WARNING, "359.99h debe ser STALE_WARNING")
            self.assertTrue(res_359_99.is_currently_valid)

            t_360_00 = self.now - timedelta(hours=360)                # 360.00 horas exactas
            res_360_00 = self.policy.evaluate(t_360_00, self.now, category=cat)
            self.assertEqual(res_360_00.status, ValidityStatus.STALE_WARNING, "360.00h exactas no ha expirado aún")
            self.assertTrue(res_360_00.is_currently_valid)

            t_360_01 = self.now - timedelta(seconds=360 * 3600 + 36)  # 360.01 horas
            res_360_01 = self.policy.evaluate(t_360_01, self.now, category=cat)
            self.assertEqual(res_360_01.status, ValidityStatus.EXPIRED, "360.01h debe ser EXPIRED")
            self.assertFalse(res_360_01.is_currently_valid)

    def test_grocery_product_warns_when_approaching_expiration(self) -> None:
        # Abarrotes: vigente hasta 15 días; entre día 11 y 15 muestra advertencia de antigüedad
        reported_at = self.now - timedelta(days=12)
        assessment = self.policy.evaluate(
            reported_at=reported_at,
            evaluated_at=self.now,
            category=ProductCategory.GROCERY,
        )
        self.assertEqual(assessment.status, ValidityStatus.STALE_WARNING)
        self.assertTrue(assessment.is_currently_valid)
        self.assertGreater(assessment.freshness_score, Decimal("0.00"))
        self.assertLess(assessment.freshness_score, Decimal("0.40"))

    def test_superseded_when_newer_official_or_verified_price_exists(self) -> None:
        # EC-02: Un comercio o nuevo reporte verificado modifica el precio; el anterior deja de ser vigente
        reported_at = self.now - timedelta(hours=4)
        newer_update_at = self.now - timedelta(hours=1)
        assessment = self.policy.evaluate(
            reported_at=reported_at,
            evaluated_at=self.now,
            category=ProductCategory.GROCERY,
            latest_verified_at_for_establishment=newer_update_at,
        )
        self.assertEqual(assessment.status, ValidityStatus.SUPERSEDED)
        self.assertFalse(assessment.is_currently_valid)
        self.assertEqual(assessment.freshness_score, Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()

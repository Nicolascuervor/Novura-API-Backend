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

    def test_perishable_product_expires_after_7_days(self) -> None:
        reported_at = self.now - timedelta(days=8)
        assessment = self.policy.evaluate(
            reported_at=reported_at,
            evaluated_at=self.now,
            category=ProductCategory.PERISHABLE,
        )
        self.assertEqual(assessment.status, ValidityStatus.EXPIRED)
        self.assertFalse(assessment.is_currently_valid)
        self.assertEqual(assessment.freshness_score, Decimal("0.00"))

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

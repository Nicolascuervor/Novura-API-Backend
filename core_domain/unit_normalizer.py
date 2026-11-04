"""
Regla de negocio de normalización de precios por unidad de medida (M-01).
Permite comparar justamente distintas presentaciones de un mismo producto
(p. ej. bolsa de 900 ml vs. caja de 1.1 L, o paquete de 500 g vs. bulto de 2.5 kg).
"""

from decimal import ROUND_HALF_UP, Decimal

from core_domain.entities import BaseDimension, NormalizedPriceResult, UnitOfMeasure


class InvalidNormalizationInputError(ValueError):
    """Error de dominio cuando el precio o la cantidad no son positivos o las unidades son incompatibles."""


# Mapa de conversión a la unidad base física:
# - Masa -> gramos (g), unidad de referencia comercial = 100g
# - Volumen -> mililitros (ml), unidad de referencia comercial = 100ml
# - Conteo -> unidad (und), unidad de referencia comercial = 1 und
_UNIT_SPEC: dict[UnitOfMeasure, tuple[BaseDimension, Decimal, str, str, Decimal]] = {
    UnitOfMeasure.GRAM: (
        BaseDimension.MASS,
        Decimal(1),
        "g",
        "100g",
        Decimal(100),
    ),
    UnitOfMeasure.KILOGRAM: (
        BaseDimension.MASS,
        Decimal(1000),
        "g",
        "100g",
        Decimal(100),
    ),
    UnitOfMeasure.POUND: (
        # Libra comercial colombiana estándar (500 g)
        BaseDimension.MASS,
        Decimal(500),
        "g",
        "100g",
        Decimal(100),
    ),
    UnitOfMeasure.MILLILITER: (
        BaseDimension.VOLUME,
        Decimal(1),
        "ml",
        "100ml",
        Decimal(100),
    ),
    UnitOfMeasure.CUBIC_CENTIMETER: (
        BaseDimension.VOLUME,
        Decimal(1),
        "ml",
        "100ml",
        Decimal(100),
    ),
    UnitOfMeasure.LITER: (
        BaseDimension.VOLUME,
        Decimal(1000),
        "ml",
        "100ml",
        Decimal(100),
    ),
    UnitOfMeasure.UNIT: (
        BaseDimension.COUNT,
        Decimal(1),
        "und",
        "1 und",
        Decimal(1),
    ),
}


class UnitNormalizer:
    """Servicio de dominio puro para normalización matemática de precios por unidad de medida."""

    @staticmethod
    def normalize(
        raw_price: Decimal | float | str,
        quantity: Decimal | float | str,
        unit: UnitOfMeasure | str,
    ) -> NormalizedPriceResult:
        price_dec = Decimal(str(raw_price))
        qty_dec = Decimal(str(quantity))

        if price_dec <= Decimal(0):
            raise InvalidNormalizationInputError("El precio reportado debe ser estrictamente mayor a 0.")
        if qty_dec <= Decimal(0):
            raise InvalidNormalizationInputError("La cantidad de la presentación debe ser estrictamente mayor a 0.")

        unit_enum = UnitOfMeasure(unit) if not isinstance(unit, UnitOfMeasure) else unit
        dimension, factor_to_base, base_label, ref_label, ref_multiplier = _UNIT_SPEC[unit_enum]

        total_base_units = qty_dec * factor_to_base
        price_per_base = (price_dec / total_base_units).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        price_per_ref = ((price_dec / total_base_units) * ref_multiplier).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        return NormalizedPriceResult(
            raw_price=price_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            quantity=qty_dec,
            unit=unit_enum,
            dimension=dimension,
            base_unit_label=base_label,
            reference_unit_label=ref_label,
            price_per_base_unit=price_per_base,
            price_per_ref_unit=price_per_ref,
        )

    @staticmethod
    def get_dimension(unit: UnitOfMeasure | str) -> BaseDimension:
        unit_enum = UnitOfMeasure(unit) if not isinstance(unit, UnitOfMeasure) else unit
        return _UNIT_SPEC[unit_enum][0]

    @classmethod
    def are_compatible(cls, unit_a: UnitOfMeasure | str, unit_b: UnitOfMeasure | str) -> bool:
        return cls.get_dimension(unit_a) == cls.get_dimension(unit_b)

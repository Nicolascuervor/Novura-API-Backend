"""
Entidades y Objetos de Valor (Value Objects) del Núcleo de Dominio.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class UnitOfMeasure(StrEnum):
    """Unidades de medida soportadas por el catálogo."""

    GRAM = "g"
    KILOGRAM = "kg"
    POUND = "lb"
    MILLILITER = "ml"
    LITER = "l"
    CUBIC_CENTIMETER = "cm3"
    UNIT = "und"


class BaseDimension(StrEnum):
    """Dimensión física estándar para comparación neutral por unidad de medida."""

    MASS = "MASS"          # Normalizado a 100g (y precio por 1g)
    VOLUME = "VOLUME"      # Normalizado a 100ml (y precio por 1ml)
    COUNT = "COUNT"        # Normalizado a 1 unidad


class ProductCategory(StrEnum):
    """Categorías con reglas diferenciadas de vigencia (EC-02)."""

    PERISHABLE = "PERISHABLE"        # Perecederos (frutas, verduras, carnes, lácteos frescos)
    GROCERY = "GROCERY"              # Abarrotes y consumo masivo no perecedero
    PERSONAL_CARE = "PERSONAL_CARE"  # Aseo personal y del hogar


class SourceType(StrEnum):
    """Fuentes de precios con distinta confiabilidad (EC-03, EC-05, EC-06)."""

    COMMUNITY_OCCASIONAL = "COMMUNITY_OCCASIONAL"
    COMMUNITY_FREQUENT = "COMMUNITY_FREQUENT"
    OFFICIAL_MERCHANT = "OFFICIAL_MERCHANT"
    PUBLIC_REFERENCE = "PUBLIC_REFERENCE"  # Ej. DANE SIPSA


class ValidityStatus(StrEnum):
    """Estado de vigencia de un precio (EC-02)."""

    VALID = "VALID"
    STALE_WARNING = "STALE_WARNING"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class ReliabilityStatus(StrEnum):
    """Estado de credibilidad e integridad de un reporte (EC-03)."""

    VERIFIED = "VERIFIED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    ANOMALOUS = "ANOMALOUS"


@dataclass(frozen=True)
class NormalizedPriceResult:
    """Resultado inmutable de la normalización de precios por unidad de medida (M-01)."""

    raw_price: Decimal
    quantity: Decimal
    unit: UnitOfMeasure
    dimension: BaseDimension
    base_unit_label: str          # Ej. "g", "ml", "und"
    reference_unit_label: str     # Ej. "100g", "100ml", "1 und"
    price_per_base_unit: Decimal  # Precio por 1g, 1ml o 1 und
    price_per_ref_unit: Decimal   # Precio por 100g, 100ml o 1 und (para lectura humana clara)


@dataclass(frozen=True)
class ValidityAssessment:
    """Evaluación de actualidad/vigencia de un reporte de precio (EC-02, M-01)."""

    status: ValidityStatus
    is_currently_valid: bool
    freshness_score: Decimal      # Escala 0.00 a 1.00
    age_hours: Decimal
    reason: str


@dataclass(frozen=True)
class AnomalyAssessment:
    """Evaluación antifraude y de credibilidad de un reporte (EC-03, M-05)."""

    status: ReliabilityStatus
    is_reliable: bool
    confidence_score: Decimal     # Escala 0.00 a 1.00
    reasons: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ComparablePriceEntry:
    """Entrada candidata para el comparador neutral de precios (EC-06, M-02)."""

    report_id: int | str
    establishment_id: int | str
    establishment_name: str
    presentation_id: int | str
    presentation_name: str
    raw_price: Decimal
    normalized_ref_price: Decimal
    reference_unit_label: str
    reported_at: datetime
    validity_status: ValidityStatus
    reliability_status: ReliabilityStatus
    freshness_score: Decimal
    confidence_score: Decimal
    source_type: SourceType = SourceType.COMMUNITY_OCCASIONAL
    is_promotional: bool = False
    promotion_description: str | None = None
    requires_warning_label: bool = False
    warning_messages: tuple[str, ...] = field(default_factory=tuple)

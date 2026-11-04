"""
Comparador neutral de precios (EC-06, M-02).
Garantiza por diseño:
1. Tolerancia cero al sesgo comercial: el orden responde exclusivamente al criterio declarado al usuario.
2. Separación y etiquetado explícito en el 100% de los casos de cualquier contenido promocional.
3. Exclusión de precios vencidos (EC-02) o anómalos (EC-03) del listado de precios vigentes confiables.
"""

from dataclasses import dataclass, replace
from enum import StrEnum

from core_domain.entities import (
    ComparablePriceEntry,
    ReliabilityStatus,
    ValidityStatus,
)


class SortCriterion(StrEnum):
    """Criterios explícitos de ordenamiento declarados al consumidor (EC-06)."""

    UNIT_PRICE_ASC = "UNIT_PRICE_ASC"    # Más económico por unidad de medida estándar (100g/100ml/1und)
    RAW_PRICE_ASC = "RAW_PRICE_ASC"      # Menor desembolso total por empaque
    FRESHNESS_DESC = "FRESHNESS_DESC"    # Más reciente primero


@dataclass(frozen=True)
class ComparisonOutput:
    """Resultado estructurado y auditable de una comparación neutral de precios."""

    declared_criterion: SortCriterion
    ranked_results: tuple[ComparablePriceEntry, ...]
    promotional_highlights: tuple[ComparablePriceEntry, ...]
    excluded_count: int


class NeutralComparator:
    """Servicio de dominio puro que ejecuta la comparación neutral (Ley 1480 / EC-06)."""

    @staticmethod
    def compare(
        entries: list[ComparablePriceEntry] | tuple[ComparablePriceEntry, ...],
        criterion: SortCriterion | str = SortCriterion.UNIT_PRICE_ASC,
        include_low_confidence_with_warning: bool = True,
    ) -> ComparisonOutput:
        sort_crit = (
            SortCriterion(criterion)
            if not isinstance(criterion, SortCriterion)
            else criterion
        )

        valid_candidates: list[ComparablePriceEntry] = []
        promotional_items: list[ComparablePriceEntry] = []
        excluded = 0

        for item in entries:
            # 1. Regla EC-02: No presentar precios vencidos ni reemplazados como vigentes
            if item.validity_status in (ValidityStatus.EXPIRED, ValidityStatus.SUPERSEDED):
                excluded += 1
                continue

            # 2. Regla EC-03: No presentar reportes anómalos/falsos como vigentes
            if item.reliability_status == ReliabilityStatus.ANOMALOUS:
                excluded += 1
                continue

            if (
                item.reliability_status == ReliabilityStatus.LOW_CONFIDENCE
                and not include_low_confidence_with_warning
            ):
                excluded += 1
                continue

            warnings: list[str] = list(item.warning_messages)
            needs_warning = item.requires_warning_label

            if item.validity_status == ValidityStatus.STALE_WARNING:
                needs_warning = True
                warnings.append("ADVERTENCIA DE VIGENCIA: Este precio lleva varios días sin actualizarse.")

            if item.reliability_status == ReliabilityStatus.LOW_CONFIDENCE:
                needs_warning = True
                warnings.append(
                    "ADVERTENCIA DE CONFIABILIDAD: Precio con variación atípica pendiente de confirmación comunitaria."
                )

            # 3. Regla EC-06 (M-02 = 1.00): Todo contenido promocional se distingue en el 100% de los casos
            if item.is_promotional:
                needs_warning = True
                promo_tag = (
                    f"CONTENIDO PROMOCIONAL DISTINGUIDO: {item.promotion_description}"
                    if item.promotion_description
                    else "CONTENIDO PROMOCIONAL DISTINGUIDO: Oferta publicada por el comercio."
                )
                warnings.append(promo_tag)

            enriched_item = replace(
                item,
                requires_warning_label=needs_warning,
                warning_messages=tuple(warnings),
            )

            valid_candidates.append(enriched_item)
            if enriched_item.is_promotional:
                promotional_items.append(enriched_item)

        # 4. Ordenamiento estrictamente neutral según el criterio declarado al consumidor
        # Ningún atributo comercial (is_promotional ni source_type) puede mejorar artificialmente la posición.
        if sort_crit == SortCriterion.UNIT_PRICE_ASC:
            valid_candidates.sort(
                key=lambda e: (e.normalized_ref_price, e.raw_price, -e.freshness_score, str(e.report_id))
            )
        elif sort_crit == SortCriterion.RAW_PRICE_ASC:
            valid_candidates.sort(
                key=lambda e: (e.raw_price, e.normalized_ref_price, -e.freshness_score, str(e.report_id))
            )
        elif sort_crit == SortCriterion.FRESHNESS_DESC:
            valid_candidates.sort(
                key=lambda e: (-e.freshness_score, e.normalized_ref_price, str(e.report_id))
            )

        promotional_items.sort(key=lambda e: (e.normalized_ref_price, e.raw_price))

        return ComparisonOutput(
            declared_criterion=sort_crit,
            ranked_results=tuple(valid_candidates),
            promotional_highlights=tuple(promotional_items),
            excluded_count=excluded,
        )

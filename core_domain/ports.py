"""
Puertos de extensión del Núcleo de Dominio (EC-05, M-08, M-09).
Define el contrato formal mediante el cual el Módulo Comercial (Corte 3: perfiles de comercios,
precios oficiales y promociones) se enchufa al comparador sin modificar los componentes
preexistentes del núcleo (manteniendo M-09 <= 0.15).
"""

from typing import Protocol

from core_domain.entities import ComparablePriceEntry


class PriceSourcePort(Protocol):
    """
    Puerto de lectura de fuentes de precios (Patrón Open-Closed / Plugin).
    - En el Corte 2 lo implementa CommunityPriceSourceAdapter.
    - En el Corte 3 se agrega CommercialPromotionSourceAdapter sin alterar el núcleo.
    """

    def fetch_entries_for_product(self, product_id: int) -> list[ComparablePriceEntry]:
        """Retorna las entradas comparables de una fuente específica para el producto indicado."""
        ...

"""
Vistas de consulta y autocompletado rápido del Catálogo (EC-01, EC-04).
"""

from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from catalog.models import Establishment, Product, ProductPresentation
from catalog.serializers import (
    EstablishmentSerializer,
    ProductPresentationSerializer,
    ProductSerializer,
)


class EstablishmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Directorio de establecimientos con ubicación en Armenia y Quindío.
    Permite filtrar rápidamente por barrio, municipio o texto libre para agilizar EC-01.
    """

    serializer_class = EstablishmentSerializer
    queryset = Establishment.objects.filter(is_active=True)

    @extend_schema(
        summary="Listar o buscar establecimientos comerciales (Armenia y Quindío)",
        parameters=[
            OpenApiParameter("q", str, description="Búsqueda por nombre o barrio (autocompletado EC-01)."),
            OpenApiParameter("municipality", str, description="Filtrar por municipio (ej. Armenia, Calarcá)."),
            OpenApiParameter("type", str, description="Filtrar por tipo: NEIGHBORHOOD_SHOP, MINIMARKET, SUPERMARKET."),
        ],
    )
    def list(self, request: Request, *args, **kwargs) -> Response:
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.request.query_params.get("q", "").strip()
        municipality = self.request.query_params.get("municipality", "").strip()
        est_type = self.request.query_params.get("type", "").strip()

        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(neighborhood__icontains=query)
                | Q(address__icontains=query)
            )
        if municipality:
            qs = qs.filter(municipality__iexact=municipality)
        if est_type:
            qs = qs.filter(establishment_type=est_type)

        return qs


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Catálogo de productos base y sus presentaciones.
    Incluye el endpoint central `/api/v1/products/{id}/compare/` (EC-02, EC-04, EC-06).
    """

    serializer_class = ProductSerializer
    queryset = Product.objects.filter(is_active=True).prefetch_related("presentations")

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.request.query_params.get("q", "").strip()
        category = self.request.query_params.get("category", "").strip()

        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(aliases__icontains=query)
                | Q(presentations__brand__icontains=query)
                | Q(presentations__ean_barcode__iexact=query)
            ).distinct()
        if category:
            qs = qs.filter(category=category)

        return qs


class ProductPresentationViewSet(viewsets.ReadOnlyModelViewSet):
    """Consulta directa de presentaciones por código de barras EAN o producto (EC-01)."""

    serializer_class = ProductPresentationSerializer
    queryset = ProductPresentation.objects.filter(is_active=True).select_related("product")

    def get_queryset(self):
        qs = super().get_queryset()
        ean = self.request.query_params.get("ean", "").strip()
        product_id = self.request.query_params.get("product_id", "").strip()

        if ean:
            qs = qs.filter(ean_barcode=ean)
        if product_id.isdigit():
            qs = qs.filter(product_id=int(product_id))
        return qs

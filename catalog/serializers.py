"""
Serializers de la API del Catálogo.
"""

from rest_framework import serializers

from catalog.models import Establishment, Product, ProductPresentation


class EstablishmentSerializer(serializers.ModelSerializer):
    """Serializer público del directorio de establecimientos (tiendas de barrio, minimercados y supermercados)."""

    establishment_type_display = serializers.CharField(
        source="get_establishment_type_display",
        read_only=True,
    )

    class Meta:
        model = Establishment
        fields = (
            "id",
            "name",
            "establishment_type",
            "establishment_type_display",
            "municipality",
            "neighborhood",
            "address",
            "latitude",
            "longitude",
        )


class ProductPresentationSerializer(serializers.ModelSerializer):
    """Serializer de presentaciones con unidad de medida para reconocimiento unificado."""

    class Meta:
        model = ProductPresentation
        fields = (
            "id",
            "product",
            "brand",
            "presentation_name",
            "ean_barcode",
            "quantity",
            "unit",
        )


class ProductSerializer(serializers.ModelSerializer):
    """Serializer de producto base con sus presentaciones para consulta rápida en góndola (EC-01)."""

    presentations = ProductPresentationSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "category",
            "aliases",
            "description",
            "presentations",
        )

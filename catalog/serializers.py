"""
Serializers de la API del Catálogo.
"""

from rest_framework import serializers

from catalog.models import Establishment, PaymentMethod, Product, ProductPresentation


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer del catálogo oficial de métodos de pago (`catalog_paymentmethod`)."""

    category_display = serializers.CharField(
        source="get_category_display",
        read_only=True,
    )

    class Meta:
        model = PaymentMethod
        fields = (
            "id",
            "code",
            "name",
            "category",
            "category_display",
            "icon_image",
            "display_order",
            "is_active",
        )
        read_only_fields = (
            "id",
            "category_display",
            "icon_image",
        )


class PaymentMethodIconUploadSerializer(serializers.Serializer):
    """DTO de entrada para subir o actualizar el icono oficial de un método de pago (`PaymentMethod`)."""

    icon_image = serializers.FileField(
        required=True,
        help_text="Archivo de imagen o icono del método de pago (JPEG, PNG o WEBP, máx. 5 MB, purga EXIF).",
    )


class EstablishmentSerializer(serializers.ModelSerializer):
    """
    Serializer del directorio de establecimientos (tiendas de barrio, minimercados y supermercados).
    Incluye `owner` (relación 1 a muchos con `User`), `payment_methods` (objetos detallados) y
    `payment_method_codes` (códigos aceptados para lectura y escritura dinámica).
    """

    owner_username = serializers.CharField(
        source="owner.username",
        read_only=True,
        default=None,
    )
    establishment_type_display = serializers.CharField(
        source="get_establishment_type_display",
        read_only=True,
    )
    payment_methods = PaymentMethodSerializer(many=True, read_only=True)
    payment_method_codes = serializers.ListField(
        child=serializers.SlugField(max_length=40),
        required=False,
        write_only=True,
        help_text="Lista de códigos de métodos de pago aceptados (ej. ['cash', 'nequi', 'bre_b']).",
    )

    class Meta:
        model = Establishment
        fields = (
            "id",
            "owner",
            "owner_username",
            "name",
            "establishment_type",
            "establishment_type_display",
            "municipality",
            "neighborhood",
            "address",
            "latitude",
            "longitude",
            "logo_image",
            "payment_methods",
            "payment_method_codes",
            "is_active",
        )
        read_only_fields = (
            "id",
            "owner",
            "owner_username",
            "establishment_type_display",
            "logo_image",
            "payment_methods",
        )

    def to_representation(self, instance: Establishment) -> dict:
        data = super().to_representation(instance)
        data["payment_method_codes"] = [
            pm["code"] for pm in data.get("payment_methods", [])
        ]
        return data


class EstablishmentLogoImageUploadSerializer(serializers.Serializer):
    """DTO de entrada para subir o actualizar el logo o imagen de un establecimiento comercial."""

    logo_image = serializers.FileField(
        required=True,
        help_text="Archivo de imagen o logo del comercio (JPEG, PNG o WEBP, máx. 5 MB, purga EXIF).",
    )


class ProductPresentationSerializer(serializers.ModelSerializer):
    """Serializer de presentaciones con unidad de medida e imagen de referencia para reconocimiento unificado."""

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
            "reference_image",
        )


class PresentationReferenceImageUploadSerializer(serializers.Serializer):
    """DTO de entrada para adjuntar o actualizar la imagen de referencia de una presentación."""

    reference_image = serializers.FileField(
        required=True,
        help_text="Archivo de imagen (JPEG, PNG o WEBP, máx. 5 MB).",
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
            "product_image",
            "is_active",
            "presentations",
        )
        read_only_fields = ("product_image", "is_active")


class ProductRepresentativeImageUploadSerializer(serializers.Serializer):
    """DTO de entrada para subir o actualizar la imagen representativa de un producto molde (`Product`)."""

    product_image = serializers.FileField(
        required=True,
        help_text="Archivo de imagen representativa del producto (JPEG, PNG o WEBP, máx. 5 MB, purga EXIF).",
    )


class ProductMutationSerializer(serializers.ModelSerializer):
    """Serializer para creación y actualización de productos por el Moderador."""

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "category",
            "aliases",
            "description",
            "product_image",
            "is_active",
        )
        read_only_fields = ("product_image",)


class ProductPresentationMutationSerializer(serializers.ModelSerializer):
    """Serializer para creación y edición de presentaciones de productos por el Moderador."""

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
            "is_active",
        )

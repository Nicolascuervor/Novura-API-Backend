"""
Modelos del Catálogo de Productos, Presentaciones y Directorio de Establecimientos.
Soporta reconocimiento de productos en distintas presentaciones y denominaciones (Sección 4.2 de la Guía)
y normalización automática de unidades de medida (M-01).
"""

from django.db import models

from core_domain.entities import ProductCategory, UnitOfMeasure


class Establishment(models.Model):
    """
    Establecimiento comercial en Armenia y el departamento del Quindío
    (tienda de barrio, minimercado o supermercado).
    Nota: Las coordenadas aquí corresponden exclusivamente a la ubicación pública del comercio,
    NUNCA al reporte ni al reportante (cumpliendo Ley 1581 y M-06).
    """

    class EstablishmentType(models.TextChoices):
        NEIGHBORHOOD_SHOP = "NEIGHBORHOOD_SHOP", "Tienda de Barrio"
        MINIMARKET = "MINIMARKET", "Minimercado"
        SUPERMARKET = "SUPERMARKET", "Supermercado / Gran Superficie"

    name = models.CharField(max_length=160, db_index=True)
    establishment_type = models.CharField(
        max_length=32,
        choices=EstablishmentType.choices,
        default=EstablishmentType.NEIGHBORHOOD_SHOP,
        db_index=True,
    )
    municipality = models.CharField(max_length=80, default="Armenia", db_index=True)
    neighborhood = models.CharField(max_length=120, db_index=True)
    address = models.CharField(max_length=200)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["municipality", "name"]
        indexes = [
            models.Index(fields=["municipality", "neighborhood"]),
            models.Index(fields=["establishment_type", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_establishment_type_display()} - {self.neighborhood}, {self.municipality})"


class Product(models.Model):
    """
    Producto base de la canasta familiar que agrupa distintas marcas, presentaciones y denominaciones.
    Permite reconocer que dos registros corresponden al mismo producto genérico (Pregunta 4 de la Guía).
    """

    name = models.CharField(max_length=160, unique=True, db_index=True)
    category = models.CharField(
        max_length=32,
        choices=[(c.value, c.value) for c in ProductCategory],
        default=ProductCategory.GROCERY.value,
        db_index=True,
    )
    aliases = models.CharField(
        max_length=255,
        blank=True,
        help_text="Denominaciones regionales o sinónimos separados por coma para búsqueda rápida en góndola (EC-01).",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} [{self.category}]"


class ProductPresentation(models.Model):
    """
    Presentación específica de un producto (marca, cantidad y unidad de medida).
    Ej: Leche Entera Colanta Bolsa 900 ml vs. Leche Entera Alquería Caja 1.1 L.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="presentations",
    )
    brand = models.CharField(max_length=100, db_index=True)
    presentation_name = models.CharField(
        max_length=180,
        help_text="Ej: Bolsa 900 ml, Paquete 500 g, Cubeta 30 und",
    )
    ean_barcode = models.CharField(max_length=32, blank=True, db_index=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    unit = models.CharField(
        max_length=16,
        choices=[(u.value, u.value) for u in UnitOfMeasure],
        default=UnitOfMeasure.GRAM.value,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["product__name", "brand", "quantity"]
        unique_together = [("product", "brand", "presentation_name")]

    def __str__(self) -> str:
        return f"{self.product.name} - {self.brand} ({self.presentation_name})"

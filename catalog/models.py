"""
Modelos del Catálogo de Productos, Presentaciones y Directorio de Establecimientos.
Soporta reconocimiento de productos en distintas presentaciones y denominaciones (Sección 4.2 de la Guía)
y normalización automática de unidades de medida (M-01).
"""

from django.conf import settings
from django.db import models

from core_domain.entities import ProductCategory, UnitOfMeasure


class PaymentMethod(models.Model):
    """
    Catálogo normalizado (3NF) de medios de pago aceptados por los establecimientos comerciales
    en Armenia y el Quindío (Efectivo, Nequi, Daviplata, Bre-B, QR Bancolombia, Visa, Mastercard, etc.).
    """

    class PaymentCategory(models.TextChoices):
        CASH = "CASH", "Efectivo"
        DIGITAL_WALLET = "DIGITAL_WALLET", "Billetera Digital / Transferencia Inmediata"
        CARD = "CARD", "Tarjeta Débito o Crédito"
        CREDIT = "CREDIT", "Cupo / Financiación Directa"
        VOUCHER = "VOUCHER", "Bonos / Cajas de Compensación"

    code = models.SlugField(
        max_length=40,
        unique=True,
        db_index=True,
        help_text="Código único estable (ej. cash, nequi, daviplata, bre_b, qr_bancolombia, visa).",
    )
    name = models.CharField(max_length=100, unique=True, db_index=True)
    category = models.CharField(
        max_length=32,
        choices=PaymentCategory.choices,
        default=PaymentCategory.DIGITAL_WALLET,
        db_index=True,
    )
    icon_image = models.ImageField(
        upload_to="catalog/payment_methods/%Y/%m/",
        null=True,
        blank=True,
        help_text="Icono o logo oficial del método de pago sanitizado (JPEG/PNG/WEBP <= 5MB, sin EXIF).",
    )
    display_order = models.PositiveSmallIntegerField(default=100, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Establishment(models.Model):
    """
    Establecimiento comercial en Armenia y el departamento del Quindío
    (tienda de barrio, minimercado o supermercado).
    Relación 1 a Muchos (`owner`): Un usuario con rol Comercio (`MERCHANT`) puede ser propietario
    de uno o varios establecimientos y ejercer CRUD completo sobre ellos (con protección Anti-IDOR).
    Nota: Las coordenadas aquí corresponden exclusivamente a la ubicación pública del comercio,
    NUNCA al reporte ni al reportante (cumpliendo Ley 1581 y M-06).
    """

    class EstablishmentType(models.TextChoices):
        NEIGHBORHOOD_SHOP = "NEIGHBORHOOD_SHOP", "Tienda de Barrio"
        MINIMARKET = "MINIMARKET", "Minimercado"
        SUPERMARKET = "SUPERMARKET", "Supermercado / Gran Superficie"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_establishments",
        help_text="Usuario propietario/representante del establecimiento (relación 1 a muchos).",
    )
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
    logo_image = models.ImageField(
        upload_to="catalog/establishments/%Y/%m/",
        null=True,
        blank=True,
        help_text="Imagen o logo oficial del comercio sanitizado (JPEG/PNG/WEBP <= 5MB, sin EXIF).",
    )
    payment_methods = models.ManyToManyField(
        PaymentMethod,
        blank=True,
        related_name="establishments",
        help_text="Métodos de pago válidos aceptados por este establecimiento comercial.",
    )
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


class Category(models.Model):
    """
    Categoría del catálogo administrable y extensible (EC-02, EC-04).
    Permite incorporar nuevas categorías desde el panel administrativo
    o fixtures sin alterar el esquema relacional de productos ni requerir
    modificaciones estáticas en el frontend.
    """

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    volatility = models.CharField(
        max_length=10,
        choices=[("high", "Alta volatilidad"), ("low", "Baja volatilidad")],
        default="low",
    )
    color = models.CharField(max_length=30, default="sky")
    description = models.CharField(max_length=255, blank=True, default="")
    display_order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        from core_domain.entities import ProductCategory

        if self.code:
            self.code = self.code.strip().upper()
            valid_codes = [c.value for c in ProductCategory]
            if self.code not in valid_codes:
                raise ValidationError({
                    "code": (
                        f"El código '{self.code}' no está soportado en las reglas de dominio del núcleo (ProductCategory). "
                        f"Para preservar la consistencia del patrón híbrido, las categorías deben estar respaldadas "
                        f"por el dominio puro. Códigos soportados: {', '.join(valid_codes)}."
                    )
                })

            high_volatility_codes = {ProductCategory.FRUITS_VEGGIES.value, ProductCategory.PERISHABLE.value}
            expected_volatility = "high" if self.code in high_volatility_codes else "low"
            if self.volatility != expected_volatility:
                raise ValidationError({
                    "volatility": (
                        f"Inconsistencia con ADR-04: La categoría '{self.code}' debe tener volatilidad '{expected_volatility}' "
                        f"para garantizar coherencia con las ventanas temporales de ValidityPolicy."
                    )
                })

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


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
    product_image = models.ImageField(
        upload_to="catalog/products/%Y/%m/",
        null=True,
        blank=True,
        help_text="Imagen representativa del producto molde sanitizada (JPEG/PNG/WEBP <= 5MB, sin EXIF).",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        # Validar contra categorías activas de base de datos si existen registros
        try:
            if Category.objects.exists():
                active_cat = Category.objects.filter(code=self.category, is_active=True).first()
                if not active_cat:
                    raise ValidationError({
                        "category": f"La categoría '{self.category}' no existe o se encuentra desactivada administrativamente."
                    })
        except Exception as e:
            if isinstance(e, ValidationError):
                raise e

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} [{self.category}]"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


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
    reference_image = models.ImageField(
        upload_to="catalog/presentations/%Y/%m/",
        null=True,
        blank=True,
        help_text="Imagen de referencia del producto sanitizada (JPEG/PNG/WEBP <= 5MB, sin EXIF).",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["product__name", "brand", "quantity"]
        unique_together = [("product", "brand", "presentation_name")]

    def __str__(self) -> str:
        return f"{self.product.name} - {self.brand} ({self.presentation_name})"

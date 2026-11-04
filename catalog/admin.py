from django.contrib import admin

from catalog.models import Establishment, Product, ProductPresentation


@admin.register(Establishment)
class EstablishmentAdmin(admin.ModelAdmin):
    list_display = ("name", "establishment_type", "neighborhood", "municipality", "is_active")
    list_filter = ("establishment_type", "municipality", "is_active")
    search_fields = ("name", "neighborhood", "address")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "aliases", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "aliases")


@admin.register(ProductPresentation)
class ProductPresentationAdmin(admin.ModelAdmin):
    list_display = ("product", "brand", "presentation_name", "quantity", "unit", "ean_barcode", "is_active")
    list_filter = ("unit", "is_active", "product__category")
    search_fields = ("product__name", "brand", "presentation_name", "ean_barcode")

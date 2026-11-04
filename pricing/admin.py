from django.contrib import admin

from pricing.models import PriceReport


@admin.register(PriceReport)
class PriceReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "presentation",
        "establishment",
        "raw_price",
        "normalized_ref_price",
        "reference_unit_label",
        "reliability_status",
        "confidence_score",
        "source_type",
        "is_promotional",
        "reported_at",
    )
    list_filter = ("reliability_status", "source_type", "is_promotional", "establishment__municipality")
    search_fields = ("presentation__product__name", "establishment__name", "anomaly_notes")
    readonly_fields = ("reporter_hash", "reported_at")

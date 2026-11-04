from django.contrib import admin

from accounts.models import EstablishmentCorrectionRequest, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "role",
        "managed_establishment",
        "verified_reports_count",
        "rejected_reports_count",
        "accepted_data_policy",
        "is_suspended",
        "created_at",
    )
    list_filter = ("role", "is_suspended", "accepted_data_policy")
    search_fields = ("user__username", "user__email", "managed_establishment__name")


@admin.register(EstablishmentCorrectionRequest)
class EstablishmentCorrectionRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "establishment", "merchant_user", "status", "created_at", "resolved_at")
    list_filter = ("status",)
    search_fields = ("establishment__name", "merchant_user__username", "justification")

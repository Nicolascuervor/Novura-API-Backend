from django.contrib import admin

from accounts.models import AuditEventLog, EstablishmentCorrectionRequest, UserProfile


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


@admin.register(AuditEventLog)
class AuditEventLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "module",
        "action_type",
        "severity",
        "actor_username",
        "actor_role",
        "target_model",
        "target_id",
        "target_repr",
    )
    list_filter = ("module", "severity", "actor_role", "action_type")
    search_fields = ("summary", "actor_username", "target_repr", "target_id", "action_type")
    readonly_fields = (
        "actor_user",
        "actor_username",
        "actor_role",
        "module",
        "action_type",
        "severity",
        "target_model",
        "target_id",
        "target_repr",
        "summary",
        "previous_state",
        "new_state",
        "ip_hash",
        "created_at",
    )

    def has_add_permission(self, request):
        del request
        return False

    def has_delete_permission(self, request, obj=None):
        del request, obj
        return False


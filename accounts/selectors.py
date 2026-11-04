"""
Selectores de Lectura Optimizada del Módulo `accounts` (CQRS / `django-architecture-enforcer` + `django-response-time-enforcer`).
Garantiza cero problemas N+1 mediante `select_related` y aislamiento estricto por Actor (Anti-IDOR).
"""

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import QuerySet

from accounts.models import ActorRole, EstablishmentCorrectionRequest, UserProfile
from core_domain.entities import ReliabilityStatus
from pricing.models import PriceReport


def get_or_create_actor_profile(*, user: AbstractBaseUser) -> UserProfile:
    """Obtiene el perfil del usuario con `select_related` sobre su establecimiento asignado."""
    profile, _ = UserProfile.objects.select_related("user", "managed_establishment").get_or_create(
        user=user
    )
    return profile


def get_correction_requests_for_actor(*, user: AbstractBaseUser) -> QuerySet[EstablishmentCorrectionRequest]:
    """
    Selector Anti-IDOR (OWASP A01):
    - Si es Moderador o Staff, retorna todas las solicitudes con `select_related`.
    - Si es Comercio, retorna exclusivamente las solicitudes creadas por ese usuario para su propio establecimiento.
    """
    base_qs = EstablishmentCorrectionRequest.objects.select_related(
        "establishment",
        "merchant_user",
        "resolved_by",
    )
    profile = getattr(user, "profile", None)
    if getattr(user, "is_staff", False) or (profile and profile.role == ActorRole.MODERATOR):
        return base_qs.all()

    return base_qs.filter(merchant_user=user)


def get_flagged_price_reports_for_moderation() -> QuerySet[PriceReport]:
    """
    Selector optimizado para el Moderador (`django-response-time-enforcer`):
    Carga en una sola consulta SQL (`select_related`) el reporte, su presentación, producto y establecimiento.
    """
    return (
        PriceReport.objects.filter(
            reliability_status__in=[
                ReliabilityStatus.ANOMALOUS.value,
                ReliabilityStatus.LOW_CONFIDENCE.value,
            ]
        )
        .select_related("presentation", "presentation__product", "establishment")
        .order_by("-reported_at")
    )


def get_all_profiles_for_moderation() -> QuerySet[UserProfile]:
    """Selector paginable con `select_related` para gestión de cuentas por el Moderador."""
    return UserProfile.objects.select_related("user", "managed_establishment").order_by("-created_at")

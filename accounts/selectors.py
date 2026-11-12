"""
Selectores de Lectura Optimizada del Módulo `accounts` (CQRS / `django-architecture-enforcer` + `django-response-time-enforcer`).
Garantiza cero problemas N+1 mediante `select_related` y aislamiento estricto por Actor (Anti-IDOR).
"""

from datetime import timedelta
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import Count, Q, QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from accounts.models import (
    ActorRole,
    AuditEventLog,
    EstablishmentCorrectionRequest,
    UserProfile,
    VerificationStatus,
)
from catalog.models import Establishment, PaymentMethod, Product, ProductPresentation
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


def get_audit_event_logs_for_moderation(
    *,
    module: str = "",
    action_type: str = "",
    severity: str = "",
    actor_id: str = "",
    actor_role: str = "",
    target_model: str = "",
    target_id: str = "",
    date_from: str = "",
    date_to: str = "",
    query: str = "",
) -> QuerySet[AuditEventLog]:
    """
    Selector optimizado con filtros compuestos para la Vista de Auditoría del Moderador.
    """
    qs = AuditEventLog.objects.select_related("actor_user").all()

    if module:
        qs = qs.filter(module__iexact=module.strip())
    if action_type:
        qs = qs.filter(action_type__iexact=action_type.strip())
    if severity:
        qs = qs.filter(severity__iexact=severity.strip())
    if actor_id.strip().isdigit():
        qs = qs.filter(actor_user_id=int(actor_id.strip()))
    if actor_role:
        qs = qs.filter(actor_role__iexact=actor_role.strip())
    if target_model:
        qs = qs.filter(target_model__iexact=target_model.strip())
    if target_id:
        qs = qs.filter(target_id=target_id.strip())

    if date_from:
        dt_from = parse_datetime(date_from) or parse_date(date_from)
        if dt_from is not None:
            qs = qs.filter(created_at__gte=dt_from)

    if date_to:
        dt_to = parse_datetime(date_to) or parse_date(date_to)
        if dt_to is not None:
            qs = qs.filter(created_at__lte=dt_to)

    if query:
        q_clean = query.strip()
        qs = qs.filter(
            Q(summary__icontains=q_clean)
            | Q(actor_username__icontains=q_clean)
            | Q(target_repr__icontains=q_clean)
            | Q(action_type__icontains=q_clean)
            | Q(target_id__iexact=q_clean)
        )

    return qs


def get_moderation_dashboard_summary() -> dict[str, Any]:
    """
    Calcula en consultas agregadas los KPIs y contadores de estado del sistema
    para el Panel de Administración y Auditoría del Moderador, con caché de 30s en Redis/Django Cache.
    """
    from django.core.cache import cache

    cache_key = "pricecol:moderation:dashboard_summary"
    cached_summary = cache.get(cache_key)
    if cached_summary is not None:
        return cached_summary

    now = timezone.now()
    last_24h = now - timedelta(hours=24)

    profile_stats = UserProfile.objects.aggregate(
        total_accounts=Count("id"),
        consumers=Count("id", filter=Q(role=ActorRole.CONSUMER)),
        reporters=Count("id", filter=Q(role=ActorRole.REPORTER)),
        merchants=Count("id", filter=Q(role=ActorRole.MERCHANT)),
        moderators=Count("id", filter=Q(role=ActorRole.MODERATOR)),
        suspended_accounts=Count("id", filter=Q(is_suspended=True)),
        verified_merchants=Count(
            "id",
            filter=Q(role=ActorRole.MERCHANT, verification_status=VerificationStatus.VERIFIED),
        ),
        pending_verification_merchants=Count(
            "id",
            filter=Q(role=ActorRole.MERCHANT, verification_status=VerificationStatus.PENDING),
        ),
    )

    est_stats = Establishment.objects.filter(is_active=True).aggregate(
        total_active=Count("id"),
        supermarkets=Count("id", filter=Q(establishment_type=Establishment.EstablishmentType.SUPERMARKET)),
        minimarkets=Count("id", filter=Q(establishment_type=Establishment.EstablishmentType.MINIMARKET)),
        neighborhood_shops=Count(
            "id",
            filter=Q(establishment_type=Establishment.EstablishmentType.NEIGHBORHOOD_SHOP),
        ),
    )

    report_stats = PriceReport.objects.aggregate(
        total_reports=Count("id"),
        verified_reports=Count("id", filter=Q(reliability_status=ReliabilityStatus.VERIFIED.value)),
        low_confidence_reports=Count(
            "id",
            filter=Q(reliability_status=ReliabilityStatus.LOW_CONFIDENCE.value),
        ),
        anomalous_reports=Count("id", filter=Q(reliability_status=ReliabilityStatus.ANOMALOUS.value)),
        reports_last_24h=Count("id", filter=Q(reported_at__gte=last_24h)),
    )

    pending_corrections = EstablishmentCorrectionRequest.objects.filter(
        status=EstablishmentCorrectionRequest.RequestStatus.PENDING
    ).count()

    audit_stats = AuditEventLog.objects.aggregate(
        total_events=Count("id"),
        events_last_24h=Count("id", filter=Q(created_at__gte=last_24h)),
        warning_events=Count("id", filter=Q(severity=AuditEventLog.AuditSeverity.WARNING)),
        critical_events=Count("id", filter=Q(severity=AuditEventLog.AuditSeverity.CRITICAL)),
        auth_events=Count("id", filter=Q(module=AuditEventLog.AuditModule.AUTH)),
        account_events=Count("id", filter=Q(module=AuditEventLog.AuditModule.ACCOUNT)),
        establishment_events=Count("id", filter=Q(module=AuditEventLog.AuditModule.ESTABLISHMENT)),
        catalog_events=Count("id", filter=Q(module=AuditEventLog.AuditModule.CATALOG)),
        pricing_events=Count("id", filter=Q(module=AuditEventLog.AuditModule.PRICING)),
        moderation_events=Count("id", filter=Q(module=AuditEventLog.AuditModule.MODERATION)),
    )

    summary_payload = {
        "accounts": profile_stats,
        "catalog": {
            "establishments": est_stats,
            "active_products": Product.objects.filter(is_active=True).count(),
            "active_presentations": ProductPresentation.objects.filter(is_active=True).count(),
            "active_payment_methods": PaymentMethod.objects.filter(is_active=True).count(),
        },
        "pricing_and_moderation": {
            **report_stats,
            "flagged_pending_review": (
                report_stats["low_confidence_reports"] + report_stats["anomalous_reports"]
            ),
            "pending_correction_requests": pending_corrections,
        },
        "audit_overview": {
            "total_events": audit_stats["total_events"],
            "events_last_24h": audit_stats["events_last_24h"],
            "warning_events": audit_stats["warning_events"],
            "critical_events": audit_stats["critical_events"],
            "by_module": {
                "AUTH": audit_stats["auth_events"],
                "ACCOUNT": audit_stats["account_events"],
                "ESTABLISHMENT": audit_stats["establishment_events"],
                "CATALOG": audit_stats["catalog_events"],
                "PRICING": audit_stats["pricing_events"],
                "MODERATION": audit_stats["moderation_events"],
            },
        },
    }
    cache.set(cache_key, summary_payload, timeout=30)
    return summary_payload


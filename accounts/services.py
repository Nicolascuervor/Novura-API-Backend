"""
Capa de Servicios de Negocio del Módulo `accounts` (`django-architecture-enforcer` + `django-security-auditor`).
Encapsula toda la lógica de negocio transaccional (`@transaction.atomic`), prevención de IDOR/BOLA,
sanitización XSS (`strip_tags`) y protección contra condiciones de carrera (`F()` expressions).
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.html import strip_tags

from accounts.models import ActorRole, EstablishmentCorrectionRequest, UserProfile
from catalog.models import Establishment, ProductPresentation
from core_domain.entities import ReliabilityStatus, SourceType
from pricing.models import PriceReport
from pricing.services import (
     invalidate_product_comparison_cache,
)

User = get_user_model()


class AccountSecurityDomainError(PermissionError):
    """Excepción de dominio cuando un actor intenta violar reglas de propiedad (IDOR / BOLA) o seguridad."""


def sanitize_plain_text(value: str | None) -> str:
    """Elimina cualquier etiqueta HTML/script (`<script>...</script>`) previniendo Stored XSS (OWASP A03)."""
    if not value:
        return ""
    cleaned = strip_tags(value)
    return " ".join(cleaned.split()).strip()


@transaction.atomic
def register_actor_account(
    *,
    username: str,
    email: str,
    password: str,
    role: str,
    accepted_data_policy: bool,
    managed_establishment: Establishment | None = None,
) -> UserProfile:
    """
    Servicio transaccional para registrar un nuevo Actor (Consumidor, Reportante o Comercio)
    cumpliendo con la Ley 1581 de 2012.
    """
    clean_username = sanitize_plain_text(username)
    if role == ActorRole.MODERATOR:
        raise AccountSecurityDomainError("No se permite el auto-registro con rol administrativo MODERATOR.")

    # Si un comercio no es MERCHANT, no puede vincularse un establecimiento en el registro
    target_establishment = managed_establishment if role == ActorRole.MERCHANT else None

    user = User.objects.create_user(
        username=clean_username,
        email=email.strip().lower(),
        password=password,
    )
    profile = UserProfile.objects.create(
        user=user,
        role=role,
        managed_establishment=target_establishment,
        accepted_data_policy=accepted_data_policy,
    )
    return profile


def resolve_verified_source_type_for_actor(
    *,
    profile: UserProfile,
    target_establishment: Establishment,
    requested_source_type: str | None = None,
) -> SourceType:
    """
    Prevención de BOLA / Falsificación de Fuente Oficial (`red-team-pentester`):
    - Un usuario con rol `MERCHANT` SOLO obtiene `SourceType.OFFICIAL_MERCHANT` cuando reporta sobre
      su propio establecimiento asignado (`profile.managed_establishment_id == target_establishment.id`).
    - Si reporta sobre un establecimiento de la competencia, se degrada a `COMMUNITY_OCCASIONAL`.
    """
    if (
        profile.role == ActorRole.MERCHANT
        and profile.managed_establishment_id is not None
        and profile.managed_establishment_id == target_establishment.id
    ):
        return SourceType.OFFICIAL_MERCHANT

    if profile.is_frequent_trusted_reporter:
        return SourceType.COMMUNITY_FREQUENT

    if requested_source_type == SourceType.PUBLIC_REFERENCE.value and profile.role == ActorRole.MODERATOR:
        return SourceType.PUBLIC_REFERENCE

    return SourceType.COMMUNITY_OCCASIONAL


@transaction.atomic
def update_actor_reputation_after_report(
    *,
    profile: UserProfile,
    report: PriceReport,
    presentation: ProductPresentation,
    establishment: Establishment,
) -> None:
    """
    Actualización atómica de reputación (`F()` expression) con protección Anti-Farming (`red-team-pentester`):
    - Evita condiciones de carrera concurrentes en base de datos.
    - Solo incrementa `verified_reports_count` si el mismo `reporter_hash` no había reportado ya un precio
      verificado para la misma presentación y establecimiento en las últimas 24 horas.
    """
    if report.reliability_status == ReliabilityStatus.VERIFIED.value:
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        prior_same_pair_count = (
            PriceReport.objects.filter(
                reporter_hash=report.reporter_hash,
                presentation=presentation,
                establishment=establishment,
                reliability_status=ReliabilityStatus.VERIFIED.value,
                reported_at__gte=twenty_four_hours_ago,
            )
            .exclude(pk=report.pk)
            .count()
        )
        if prior_same_pair_count == 0:
            UserProfile.objects.filter(pk=profile.pk).update(
                verified_reports_count=F("verified_reports_count") + 1
            )
            profile.refresh_from_db(fields=["verified_reports_count"])
    elif report.reliability_status == ReliabilityStatus.ANOMALOUS.value:
        UserProfile.objects.filter(pk=profile.pk).update(
            rejected_reports_count=F("rejected_reports_count") + 1
        )
        profile.refresh_from_db(fields=["rejected_reports_count"])


@transaction.atomic
def create_merchant_correction_request(
    *,
    merchant_user: AbstractBaseUser,
    establishment: Establishment,
    proposed_name: str = "",
    proposed_neighborhood: str = "",
    proposed_address: str = "",
    justification: str,
) -> EstablishmentCorrectionRequest:
    """
    Servicio protegido contra IDOR (OWASP A01):
    Verifica que el comerciante sea propietario/administrador del establecimiento que solicita corregir.
    """
    profile, _ = UserProfile.objects.get_or_create(user=merchant_user)

    if profile.role == ActorRole.MERCHANT and profile.managed_establishment_id != establishment.id:
        raise AccountSecurityDomainError(
            "Operación rechazada (Anti-IDOR): Solo puedes solicitar correcciones para tu propio establecimiento asignado."
        )

    return EstablishmentCorrectionRequest.objects.create(
        merchant_user=merchant_user,
        establishment=establishment,
        proposed_name=sanitize_plain_text(proposed_name),
        proposed_neighborhood=sanitize_plain_text(proposed_neighborhood),
        proposed_address=sanitize_plain_text(proposed_address),
        justification=sanitize_plain_text(justification),
    )


@transaction.atomic
def review_flagged_price_report_by_moderator(
    *,
    moderator_user: AbstractBaseUser,
    report: PriceReport,
    new_status: str,
    moderator_note: str = "",
) -> PriceReport:
    """Servicio transaccional del Moderador para aprobar o confirmar como anómalo un reporte dudoso."""
    clean_note = sanitize_plain_text(moderator_note)
    report.reliability_status = new_status
    report.confidence_score = (
        Decimal("0.95") if new_status == ReliabilityStatus.VERIFIED.value else Decimal("0.00")
    )
    if clean_note:
        mod_username = getattr(moderator_user, "username", "moderator")
        report.anomaly_notes = f"{report.anomaly_notes} | [Moderador {mod_username}]: {clean_note}".strip(" |")
    report.save(update_fields=["reliability_status", "confidence_score", "anomaly_notes"])

    invalidate_product_comparison_cache(report.presentation.product_id)
    return report


@transaction.atomic
def approve_merchant_correction_by_moderator(
    *,
    moderator_user: AbstractBaseUser,
    correction: EstablishmentCorrectionRequest,
    moderator_notes: str = "",
) -> EstablishmentCorrectionRequest:
    """Servicio transaccional del Moderador para aplicar una corrección solicitada por un Comercio."""
    est = correction.establishment

    if correction.proposed_name:
        est.name = sanitize_plain_text(correction.proposed_name)
    if correction.proposed_neighborhood:
        est.neighborhood = sanitize_plain_text(correction.proposed_neighborhood)
    if correction.proposed_address:
        est.address = sanitize_plain_text(correction.proposed_address)
    est.save()

    correction.status = EstablishmentCorrectionRequest.RequestStatus.APPROVED
    correction.resolved_by = moderator_user
    correction.resolved_at = timezone.now()
    correction.moderator_notes = (
        sanitize_plain_text(moderator_notes)
        or "Corrección verificada y aplicada por moderación."
    )
    correction.save()
    return correction

"""
Capa de Servicios de Negocio del Módulo `accounts` (`django-architecture-enforcer` + `django-security-auditor`).
Encapsula toda la lógica de negocio transaccional (`@transaction.atomic`), prevención de IDOR/BOLA,
sanitización XSS (`strip_tags`) y protección contra condiciones de carrera (`F()` expressions).
"""

import hashlib
import hmac
import secrets
import time
from datetime import timedelta
from decimal import Decimal
from typing import BinaryIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser, update_last_login
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.html import strip_tags

from accounts.models import (
    ActorRole,
    AuditEventLog,
    EstablishmentCorrectionRequest,
    UserProfile,
    VerificationStatus,
)
from catalog.models import Establishment, ProductPresentation
from catalog.services import ImageSecurityService, user_owns_establishment
from core_domain.entities import ReliabilityStatus, SourceType
from pricing.models import PriceReport
from pricing.services import (
    invalidate_product_comparison_cache,
)

User = get_user_model()

MIN_ENCODED_ID = 100_000_000
MAX_ENCODED_ID = 2_147_483_647
ENCODED_ID_SPAN = MAX_ENCODED_ID - MIN_ENCODED_ID + 1


class AccountSecurityDomainError(PermissionError):
    """Excepción de dominio cuando un actor intenta violar reglas de propiedad (IDOR / BOLA) o seguridad."""


def hash_ip_address(raw_ip: str | None) -> str:
    """Genera un hash SHA-256 con salt de una IP para auditoría sin almacenar PII cruda (Ley 1581)."""
    if not raw_ip or not raw_ip.strip():
        return ""
    salted = f"{settings.SECRET_KEY}:ip:{raw_ip.strip()}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


def record_audit_event(
    *,
    actor_user: AbstractBaseUser | None = None,
    module: str,
    action_type: str,
    target_model: str,
    target_id: str | int,
    target_repr: str = "",
    summary: str,
    severity: str = AuditEventLog.AuditSeverity.INFO,
    previous_state: dict | None = None,
    new_state: dict | None = None,
    ip_address: str | None = None,
) -> AuditEventLog:
    """
    Registra un evento inmutable en la bitácora de auditoría (`AuditEventLog`).
    Cumple con ISO/IEC 25010:2023 (Seguridad: No Repudio, Responsabilidad y Trazabilidad) y OWASP A09.
    """
    actor_username = "sistema"
    actor_role = "SYSTEM"
    resolved_user = None

    if actor_user is not None and getattr(actor_user, "is_authenticated", False):
        resolved_user = actor_user
        actor_username = getattr(actor_user, "username", None) or f"user-{actor_user.pk}"
        profile = UserProfile.objects.filter(user=actor_user).only("role").first()
        if profile is not None:
            actor_role = profile.role
        elif getattr(actor_user, "is_superuser", False) or getattr(actor_user, "is_staff", False):
            actor_role = ActorRole.MODERATOR

    from django.core.cache import cache

    log_entry = AuditEventLog.objects.create(
        actor_user=resolved_user,
        actor_username=actor_username,
        actor_role=actor_role,
        module=module,
        action_type=action_type,
        severity=severity,
        target_model=target_model,
        target_id=str(target_id),
        target_repr=sanitize_plain_text(target_repr)[:220],
        summary=sanitize_plain_text(summary)[:320],
        previous_state=previous_state or {},
        new_state=new_state or {},
        ip_hash=hash_ip_address(ip_address),
    )
    cache.delete("pricecol:moderation:dashboard_summary")
    return log_entry


def generate_encoded_entity_id(model_cls: type[models.Model], seed_hint: str = "") -> int:
    """
    Algoritmo criptográfico para codificar el ID primario (`id [PK] integer`) de usuarios y perfiles
    en el rango de 9 dígitos (`100_000_000` a `2_147_483_647`) usando HMAC-SHA256 + CSPRNG (`secrets`).
    Previene ataques de enumeración secuencial de cuentas (`1, 2, 3...` - OWASP A01:2021).
    """
    secret_bytes = settings.SECRET_KEY.encode("utf-8")
    for _ in range(32):
        entropy = f"{model_cls.__name__}:{seed_hint}:{secrets.token_hex(16)}:{time.time_ns()}".encode()
        digest = hmac.new(secret_bytes, entropy, hashlib.sha256).digest()
        raw_int = int.from_bytes(digest[:8], byteorder="big")
        candidate_id = MIN_ENCODED_ID + (raw_int % ENCODED_ID_SPAN)
        if not model_cls.objects.filter(pk=candidate_id).exists():
            return candidate_id
    raise RuntimeError("No fue posible generar un ID codificado único tras múltiples intentos.")


def assign_encoded_id_on_pre_save(sender: type[models.Model], instance: models.Model, **kwargs) -> None:
    """
    Hook `pre_save` para garantizar que cualquier creación de `User` o `UserProfile`
    (por API, `createsuperuser` o `seed`) reciba un ID codificado no incremental.
    """
    del kwargs
    if instance._state.adding and instance.pk is None:
        seed_hint = getattr(instance, "email", "") or getattr(instance, "username", "") or str(instance)
        instance.pk = generate_encoded_entity_id(sender, seed_hint=seed_hint)


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
    cumpliendo con la Ley 1581 de 2012, codificación de ID no incremental y activación de `last_login`.
    """
    clean_username = sanitize_plain_text(username)
    if role == ActorRole.MODERATOR:
        raise AccountSecurityDomainError("No se permite el auto-registro con rol administrativo MODERATOR.")

    # Si un comercio no es MERCHANT, no puede vincularse un establecimiento en el registro
    target_establishment = managed_establishment if role == ActorRole.MERCHANT else None
    normalized_email = email.strip().lower()

    user = User(
        id=generate_encoded_entity_id(User, seed_hint=normalized_email),
        username=clean_username,
        email=normalized_email,
    )
    user.set_password(password)
    user.save()
    update_last_login(None, user)

    profile = UserProfile.objects.create(
        id=generate_encoded_entity_id(UserProfile, seed_hint=f"profile:{user.id}"),
        user=user,
        role=role,
        managed_establishment=target_establishment,
        accepted_data_policy=accepted_data_policy,
    )
    if target_establishment is not None and target_establishment.owner_id is None:
        target_establishment.owner = user
        target_establishment.save(update_fields=["owner"])

    record_audit_event(
        actor_user=user,
        module=AuditEventLog.AuditModule.AUTH,
        action_type="USER_REGISTERED",
        target_model="UserProfile",
        target_id=profile.id,
        target_repr=f"{user.username} ({role})",
        summary=f"Nuevo registro de cuenta '{user.username}' con rol {role}.",
        severity=AuditEventLog.AuditSeverity.INFO,
        new_state={
            "user_id": user.id,
            "profile_id": profile.id,
            "username": user.username,
            "role": role,
            "managed_establishment_id": target_establishment.id if target_establishment else None,
        },
    )
    return profile


def resolve_verified_source_type_for_actor(
    *,
    profile: UserProfile,
    target_establishment: Establishment,
    requested_source_type: str | None = None,
) -> SourceType:
    """
    Prevención de BOLA / Falsificación de Fuente Oficial / Suplantación (`red-team-pentester`):
    - Un usuario `MERCHANT` SOLO obtiene `SourceType.OFFICIAL_MERCHANT` si:
        1. Su empresa está verificada (`is_verified = True`). Registrarse como "D1" no prueba ser D1.
        2. Reporta sobre su propio establecimiento asignado.
    - En cualquier otro caso se degrada a fuente comunitaria.
    """
    if (
        profile.role == ActorRole.MERCHANT
        and profile.is_verified
        and user_owns_establishment(profile=profile, establishment=target_establishment)
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

    if profile.role == ActorRole.MERCHANT and not user_owns_establishment(
        profile=profile,
        establishment=establishment,
    ):
        raise AccountSecurityDomainError(
            "Operación rechazada (Anti-IDOR): Solo puedes solicitar correcciones para tu propio establecimiento asignado."
        )

    correction = EstablishmentCorrectionRequest.objects.create(
        merchant_user=merchant_user,
        establishment=establishment,
        proposed_name=sanitize_plain_text(proposed_name),
        proposed_neighborhood=sanitize_plain_text(proposed_neighborhood),
        proposed_address=sanitize_plain_text(proposed_address),
        justification=sanitize_plain_text(justification),
    )
    record_audit_event(
        actor_user=merchant_user,
        module=AuditEventLog.AuditModule.MODERATION,
        action_type="CORRECTION_REQUEST_CREATED",
        target_model="EstablishmentCorrectionRequest",
        target_id=correction.id,
        target_repr=establishment.name,
        summary=f"Solicitud de corrección creada para '{establishment.name}'.",
        severity=AuditEventLog.AuditSeverity.INFO,
        new_state={
            "establishment_id": establishment.id,
            "proposed_name": correction.proposed_name,
            "proposed_neighborhood": correction.proposed_neighborhood,
            "proposed_address": correction.proposed_address,
            "status": correction.status,
        },
    )
    return correction


@transaction.atomic
def review_flagged_price_report_by_moderator(
    *,
    moderator_user: AbstractBaseUser,
    report: PriceReport,
    new_status: str,
    moderator_note: str = "",
) -> PriceReport:
    """Servicio transaccional del Moderador para aprobar o confirmar como anómalo un reporte dudoso."""
    previous_status = report.reliability_status
    previous_confidence = str(report.confidence_score)
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
    record_audit_event(
        actor_user=moderator_user,
        module=AuditEventLog.AuditModule.MODERATION,
        action_type="FLAGGED_REPORT_REVIEWED",
        target_model="PriceReport",
        target_id=report.id,
        target_repr=f"{report.presentation} @ {report.establishment.name}",
        summary=f"Moderador revisó reporte #{report.id} ({previous_status} -> {new_status}).",
        severity=(
            AuditEventLog.AuditSeverity.WARNING
            if new_status == ReliabilityStatus.ANOMALOUS.value
            else AuditEventLog.AuditSeverity.INFO
        ),
        previous_state={
            "reliability_status": previous_status,
            "confidence_score": previous_confidence,
        },
        new_state={
            "reliability_status": new_status,
            "confidence_score": str(report.confidence_score),
            "moderator_note": clean_note,
        },
    )
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
    previous_est_state = {
        "name": est.name,
        "neighborhood": est.neighborhood,
        "address": est.address,
    }

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
    from pricecol_api_backend.http_cache import bump_catalog_cache_version

    bump_catalog_cache_version()

    record_audit_event(
        actor_user=moderator_user,
        module=AuditEventLog.AuditModule.MODERATION,
        action_type="CORRECTION_REQUEST_RESOLVED",
        target_model="EstablishmentCorrectionRequest",
        target_id=correction.id,
        target_repr=est.name,
        summary=f"Moderador aprobó solicitud de corrección #{correction.id} sobre '{est.name}'.",
        severity=AuditEventLog.AuditSeverity.INFO,
        previous_state=previous_est_state,
        new_state={
            "name": est.name,
            "neighborhood": est.neighborhood,
            "address": est.address,
            "status": correction.status,
            "moderator_notes": correction.moderator_notes,
        },
    )
    return correction


@transaction.atomic
def set_profile_verification_status_by_moderator(
    *,
    moderator_user: AbstractBaseUser,
    profile: UserProfile,
    new_status: str,
    notes: str = "",
) -> UserProfile:
    """
    Punto único para cambiar el estado de verificación de una empresa.
    Deja trazabilidad (quién y cuándo). El flujo automático futuro (correo corporativo / NIT)
    deberá reutilizar este mismo servicio.
    """
    previous_status = profile.verification_status
    profile.verification_status = new_status
    if new_status in (VerificationStatus.VERIFIED, VerificationStatus.REJECTED):
        profile.verified_by = moderator_user
        profile.verified_at = timezone.now()
    else:
        profile.verified_by = None
        profile.verified_at = None
    clean_notes = sanitize_plain_text(notes)
    if clean_notes:
        profile.verification_notes = clean_notes
    profile.save()

    record_audit_event(
        actor_user=moderator_user,
        module=AuditEventLog.AuditModule.MODERATION,
        action_type="MERCHANT_VERIFICATION_CHANGED",
        target_model="UserProfile",
        target_id=profile.id,
        target_repr=profile.user.username,
        summary=f"Estado de verificación de '{profile.user.username}' cambiado de {previous_status} a {new_status}.",
        severity=(
            AuditEventLog.AuditSeverity.WARNING
            if new_status == VerificationStatus.REJECTED
            else AuditEventLog.AuditSeverity.INFO
        ),
        previous_state={"verification_status": previous_status},
        new_state={"verification_status": new_status, "notes": clean_notes},
    )
    return profile


@transaction.atomic
def update_actor_profile_image(
    *,
    profile: UserProfile,
    uploaded_file: BinaryIO,
    filename: str = "",
) -> UserProfile:
    """
    Valida, sanitiza (purga EXIF/GPS, máx. 5 MB, JPEG/PNG/WEBP) y actualiza la foto de perfil
    del actor en su cuenta privada (`/api/v1/auth/me/`).
    """
    sanitized_content = ImageSecurityService.validate_and_sanitize(
        file_obj=uploaded_file,
        filename=filename,
    )
    if profile.profile_image:
        profile.profile_image.delete(save=False)
    profile.profile_image.save(
        sanitized_content.name,
        sanitized_content,
        save=True,
    )
    record_audit_event(
        actor_user=profile.user,
        module=AuditEventLog.AuditModule.ACCOUNT,
        action_type="AVATAR_UPLOADED",
        target_model="UserProfile",
        target_id=profile.id,
        target_repr=profile.user.username,
        summary=f"El usuario '{profile.user.username}' actualizó su foto de perfil.",
        severity=AuditEventLog.AuditSeverity.INFO,
        new_state={"profile_image": str(profile.profile_image)},
    )
    return profile

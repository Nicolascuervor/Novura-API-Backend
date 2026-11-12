"""
Modelos de Perfiles de los 4 Actores del Proyecto Nuclear (Sección 4.1 de la Guía):
- Consumidor (CONSUMER)
- Reportante (REPORTER)
- Comercio (MERCHANT)
- Moderador (MODERATOR)

Cumple con:
- Ley 1581 de 2012 (Protección de Datos Personales y registro de autorización del titular `accepted_data_policy`).
- M-06 = 1.00 (Privacidad por diseño: la identidad del reportante nunca se expone en endpoints públicos de precios).
- Equidad entre comercios (Sección 12.1.3): Modelo `EstablishmentCorrectionRequest` para que cualquier comercio
  solicite corregir información errónea sobre su negocio.
"""

from django.conf import settings
from django.db import models

from catalog.models import Establishment


class ActorRole(models.TextChoices):
    """Roles definidos en la Tabla 4.1 de la Guía del Seminario Nuclear."""

    CONSUMER = "CONSUMER", "Consumidor (Consulta precios)"
    REPORTER = "REPORTER", "Reportante (Consumidor registrado que aporta precios)"
    MERCHANT = "MERCHANT", "Comercio (Tienda, minimercado o supermercado con perfil)"
    MODERATOR = "MODERATOR", "Moderador (Rol administrativo de integridad)"


class VerificationStatus(models.TextChoices):
    """
    Ciclo de vida de la verificación de identidad comercial ("insignia verificada" estilo redes sociales).
    Registrarse como Comercio con el nombre "D1" NO prueba que el usuario sea realmente D1.
    El flujo futuro (validación por correo corporativo / NIT) moverá el estado:
    UNVERIFIED -> PENDING -> VERIFIED | REJECTED.
    """

    UNVERIFIED = "UNVERIFIED", "Sin verificar"
    PENDING = "PENDING", "Verificación solicitada (pendiente de revisión)"
    VERIFIED = "VERIFIED", "Empresa verificada"
    REJECTED = "REJECTED", "Verificación rechazada"


class UserProfile(models.Model):
    """
    Perfil extendido vinculado 1 a 1 con el usuario de Django.
    Gestiona el rol del actor, su reputación comunitaria, el cumplimiento de Ley 1581
    y el estado de verificación de identidad comercial.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(
        max_length=20,
        choices=ActorRole.choices,
        default=ActorRole.REPORTER,
        db_index=True,
    )
    # Vínculo voluntario para el actor Comercio (MERCHANT)
    managed_establishment = models.ForeignKey(
        Establishment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merchant_profiles",
        help_text="Establecimiento asociado cuando el actor tiene rol MERCHANT.",
    )
    # Métricas para que el Reportante "sepa que su aporte es útil" (Involucramiento del usuario - ISO/IEC 25010)
    verified_reports_count = models.PositiveIntegerField(default=0)
    rejected_reports_count = models.PositiveIntegerField(default=0)

    # Cumplimiento Ley 1581 de 2012 (Sección 12 Marco Legal)
    accepted_data_policy = models.BooleanField(
        default=True,
        help_text="Autorización expresa del titular para el tratamiento de datos personales (Ley 1581 de 2012).",
    )
    data_policy_accepted_at = models.DateTimeField(auto_now_add=True)
    is_suspended = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Permite al Moderador suspender cuentas que atenten contra la integridad (EC-03).",
    )

    # --- Verificación de identidad comercial (preparado para el flujo futuro "Verificar mi empresa") ---
    verification_status = models.CharField(
        max_length=16,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
        db_index=True,
        help_text="Fuente única de verdad del estado de verificación.",
    )
    is_verified = models.BooleanField(
        default=False,
        db_index=True,
        editable=False,
        help_text="Derivado de verification_status (se sincroniza en save()). Nunca editable por el usuario.",
    )
    business_legal_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Razón social declarada por el comercio (pendiente de validar).",
    )
    business_tax_id = models.CharField(
        max_length=20,
        blank=True,
        db_index=True,
        help_text="NIT declarado por el comercio (pendiente de validar).",
    )
    verification_requested_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_profiles",
        help_text="Moderador que aprobó o rechazó la verificación.",
    )
    verification_notes = models.TextField(blank=True)
    profile_image = models.ImageField(
        upload_to="accounts/avatars/%Y/%m/",
        null=True,
        blank=True,
        help_text="Foto de perfil del usuario sanitizada (JPEG/PNG/WEBP <= 5MB, sin EXIF).",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.username} [{self.get_role_display()}]"

    def save(self, *args, **kwargs) -> None:
        """Mantiene `is_verified` consistente con `verification_status` (una sola fuente de verdad)."""
        self.is_verified = self.verification_status == VerificationStatus.VERIFIED
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "verification_status" in update_fields:
            kwargs["update_fields"] = {*update_fields, "is_verified"}
        super().save(*args, **kwargs)

    @property
    def is_frequent_trusted_reporter(self) -> bool:
        """Determina si el reportante ya es un usuario frecuente confiable (EC-03)."""
        return self.verified_reports_count >= 5 and self.rejected_reports_count == 0


class EstablishmentCorrectionRequest(models.Model):
    """
    Permite al actor Comercio "corregir información errónea sobre su negocio" (Tabla 4.1 y Consideración Ética 3:
    Equidad entre comercios) con revisión trazable por parte del Moderador.
    """

    class RequestStatus(models.TextChoices):
        PENDING = "PENDING", "Pendiente de Revisión"
        APPROVED = "APPROVED", "Aprobada y Aplicada"
        REJECTED = "REJECTED", "Rechazada"

    merchant_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="correction_requests",
    )
    establishment = models.ForeignKey(
        Establishment,
        on_delete=models.CASCADE,
        related_name="correction_requests",
    )
    proposed_name = models.CharField(max_length=160, blank=True)
    proposed_neighborhood = models.CharField(max_length=120, blank=True)
    proposed_address = models.CharField(max_length=200, blank=True)
    justification = models.TextField(
        help_text="Descripción del error u observación reportada por el comercio.",
    )
    status = models.CharField(
        max_length=16,
        choices=RequestStatus.choices,
        default=RequestStatus.PENDING,
        db_index=True,
    )
    moderator_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_corrections",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Corrección #{self.pk} para {self.establishment.name} ({self.status})"


class AuditEventLog(models.Model):
    """
    Bitácora inmutable de auditoría (*Audit Trail*) del sistema Pricecol.
    Cumple con ISO/IEC 25010:2023 (Seguridad: No Repudio, Responsabilidad y Trazabilidad),
    OWASP A09 (Security Logging and Monitoring) y Ley 1581 de 2012.
    Registra cada movimiento relevante dentro de la aplicación (autenticación, cuentas,
    establecimientos, catálogo de productos/presentaciones/medios de pago, reportes de precios y moderación).
    """

    class AuditModule(models.TextChoices):
        AUTH = "AUTH", "Autenticación y Sesiones"
        ACCOUNT = "ACCOUNT", "Cuentas y Perfiles"
        ESTABLISHMENT = "ESTABLISHMENT", "Establecimientos Comerciales"
        CATALOG = "CATALOG", "Catálogo de Productos y Medios de Pago"
        PRICING = "PRICING", "Reportes y Comparación de Precios"
        MODERATION = "MODERATION", "Moderación e Integridad"

    class AuditSeverity(models.TextChoices):
        INFO = "INFO", "Informativo"
        WARNING = "WARNING", "Advertencia / Variación Atípica"
        CRITICAL = "CRITICAL", "Crítico / Seguridad"

    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
        help_text="Usuario que ejecutó la acción (nulo si fue el sistema o si el usuario fue eliminado).",
    )
    actor_username = models.CharField(
        max_length=150,
        db_index=True,
        help_text="Snapshot inmutable del username del actor al momento del evento.",
    )
    actor_role = models.CharField(
        max_length=24,
        db_index=True,
        default="SYSTEM",
        help_text="Rol del actor al momento del evento (CONSUMER, REPORTER, MERCHANT, MODERATOR, SYSTEM).",
    )
    module = models.CharField(
        max_length=24,
        choices=AuditModule.choices,
        db_index=True,
    )
    action_type = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Código estandarizado de la acción (ej. USER_REGISTERED, ESTABLISHMENT_UPDATED, PRICE_REPORT_CREATED).",
    )
    severity = models.CharField(
        max_length=16,
        choices=AuditSeverity.choices,
        default=AuditSeverity.INFO,
        db_index=True,
    )
    target_model = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Entidad afectada (ej. UserProfile, Establishment, Product, ProductPresentation, PriceReport).",
    )
    target_id = models.CharField(
        max_length=64,
        db_index=True,
        help_text="ID primario del registro afectado.",
    )
    target_repr = models.CharField(
        max_length=220,
        blank=True,
        help_text="Nombre o representación legible del objeto afectado.",
    )
    summary = models.CharField(
        max_length=320,
        help_text="Descripción legible en español del movimiento para el panel de auditoría.",
    )
    previous_state = models.JSONField(
        default=dict,
        blank=True,
        help_text="Snapshot JSON de los valores previos antes del cambio (vacío en creaciones).",
    )
    new_state = models.JSONField(
        default=dict,
        blank=True,
        help_text="Snapshot JSON de los valores nuevos o metadatos resultantes de la acción.",
    )
    ip_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="Hash SHA-256 con salt de la dirección IP de origen (trazabilidad sin exponer PII cruda - Ley 1581).",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["module", "-created_at"]),
            models.Index(fields=["action_type", "-created_at"]),
            models.Index(fields=["target_model", "target_id"]),
        ]

    def __str__(self) -> str:
        return f"[{self.module}:{self.action_type}] {self.actor_username} -> {self.target_model}#{self.target_id}"


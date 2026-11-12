"""
Serializers de Registro, Inicio de Sesión JWT, Perfil de Actores (Consumidor, Reportante, Comercio)
y Gestión de Moderación (Moderador).
Cumple estrictamente con `django-architecture-enforcer` (cero lógica de negocio en serializers)
y `django-security-auditor` (protección contra Mass Assignment e inyección XSS).
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import (
    ActorRole,
    AuditEventLog,
    EstablishmentCorrectionRequest,
    UserProfile,
)
from accounts.services import sanitize_plain_text
from catalog.models import Establishment
from core_domain.entities import ReliabilityStatus
from pricing.models import PriceReport

User = get_user_model()


class ActorRegistrationSerializer(serializers.Serializer):
    """
    Validación de entrada para el registro de cuentas de Actores (Tabla 4.1):
    - CONSUMER (Consumidor)
    - REPORTER (Reportante comunitario)
    - MERCHANT (Comercio)
    """

    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    role = serializers.ChoiceField(
        choices=[
            (ActorRole.CONSUMER.value, ActorRole.CONSUMER.label),
            (ActorRole.REPORTER.value, ActorRole.REPORTER.label),
            (ActorRole.MERCHANT.value, ActorRole.MERCHANT.label),
        ],
        default=ActorRole.REPORTER.value,
    )
    managed_establishment_id = serializers.PrimaryKeyRelatedField(
        queryset=Establishment.objects.filter(is_active=True),
        source="managed_establishment",
        required=False,
        allow_null=True,
        help_text="Opcional al registrarse como MERCHANT: ID del establecimiento existente.",
    )
    accepted_data_policy = serializers.BooleanField(
        help_text="Autorización obligatoria de tratamiento de datos personales (Ley 1581 de 2012)."
    )

    def validate_username(self, value: str) -> str:
        cleaned = sanitize_plain_text(value)
        if not cleaned:
            raise serializers.ValidationError("El nombre de usuario no puede estar vacío ni contener etiquetas HTML.")
        if User.objects.filter(username__iexact=cleaned).exists():
            raise serializers.ValidationError("Este nombre de usuario ya está registrado.")
        return cleaned

    def validate_email(self, value: str) -> str:
        normalized = value.strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("Este correo electrónico ya está registrado.")
        return normalized

    def validate_accepted_data_policy(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError(
                "Debes aceptar la política de tratamiento de datos personales (Ley 1581 de 2012) para crear una cuenta."
            )
        return value


class PricecolTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Serializer JWT minimalista con login estándar **email + contraseña**
    (Principio de Minimización de Datos - Ley 1581 / OWASP):
    Valida que la cuenta no esté suspendida y retorna exclusivamente `access` y `refresh`.
    Los datos del perfil del Actor se consultan por separado en `GET /api/v1/auth/me/`.
    """

    username_field = "email"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["email"] = serializers.EmailField(write_only=True)

    def validate(self, attrs: dict) -> dict:
        attrs["email"] = attrs["email"].strip().lower()
        data = super().validate(attrs)
        profile, _ = UserProfile.objects.get_or_create(user=self.user)

        if profile.is_suspended:
            raise serializers.ValidationError(
                "Esta cuenta ha sido suspendida por un Moderador debido a infracciones de integridad."
            )

        return data


class TokenPairResponseSerializer(serializers.Serializer):
    """Esquema de respuesta exclusivo de tokens JWT (sin datos de usuario para evitar fugas de información)."""

    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)


class ActorProfileSerializer(serializers.ModelSerializer):
    """
    Vista privada del propio perfil (`/api/v1/auth/me/`).
    Blindado contra Mass Assignment (`red-team-pentester`): `role`, `managed_establishment`,
    `verified_reports_count`, `rejected_reports_count` e `is_suspended` son estrictamente `read_only`.
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    managed_establishment_name = serializers.CharField(
        source="managed_establishment.name",
        read_only=True,
        default=None,
    )
    owned_establishment_ids = serializers.SerializerMethodField()
    impact_summary = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = (
            "user_id",
            "username",
            "email",
            "last_login",
            "role",
            "role_display",
            "managed_establishment",
            "managed_establishment_name",
            "owned_establishment_ids",
            "verified_reports_count",
            "rejected_reports_count",
            "is_frequent_trusted_reporter",
            "is_verified",
            "verification_status",
            "accepted_data_policy",
            "data_policy_accepted_at",
            "is_suspended",
            "profile_image",
            "impact_summary",
        )
        read_only_fields = (
            "user_id",
            "username",
            "email",
            "last_login",
            "role",
            "role_display",
            "managed_establishment",
            "managed_establishment_name",
            "owned_establishment_ids",
            "verified_reports_count",
            "rejected_reports_count",
            "is_frequent_trusted_reporter",
            "is_verified",
            "verification_status",
            "accepted_data_policy",
            "data_policy_accepted_at",
            "is_suspended",
            "profile_image",
            "impact_summary",
        )

    def get_owned_establishment_ids(self, obj: UserProfile) -> list[int]:
        ids = set(
            Establishment.objects.filter(owner_id=obj.user_id, is_active=True).values_list("id", flat=True)
        )
        if obj.managed_establishment_id is not None:
            ids.add(obj.managed_establishment_id)
        return sorted(ids)

    def get_impact_summary(self, obj: UserProfile) -> str:
        if obj.role == ActorRole.MERCHANT:
            est = obj.managed_establishment.name if obj.managed_establishment else "Sin asignar"
            if not obj.is_verified:
                return (
                    f"Perfil de comercio ({est}) SIN VERIFICAR. Tus precios se publican como reportes "
                    "comunitarios hasta que tu empresa sea verificada."
                )
            return f"Perfil oficial de comercio verificado ({est}). Puedes publicar precios oficiales y solicitar correcciones."
        if obj.role == ActorRole.MODERATOR:
            return "Rol administrativo activo para preservar la integridad de la comparación."
        return (
            f"Has aportado {obj.verified_reports_count} precios verificados que ayudan a los hogares del Quindío a ahorrar."
        )


class ActorProfileImageUploadSerializer(serializers.Serializer):
    """DTO de entrada para subir o actualizar la foto de perfil del usuario (`/api/v1/auth/me/`)."""

    profile_image = serializers.FileField(
        required=True,
        help_text="Foto de perfil del usuario (JPEG, PNG o WEBP, máx. 5 MB, purga EXIF automática).",
    )


class EstablishmentCorrectionRequestSerializer(serializers.ModelSerializer):
    """Serializer para que un Comercio solicite corregir información errónea de su negocio (Tabla 4.1)."""

    establishment_current_name = serializers.CharField(source="establishment.name", read_only=True)

    class Meta:
        model = EstablishmentCorrectionRequest
        fields = (
            "id",
            "establishment",
            "establishment_current_name",
            "proposed_name",
            "proposed_neighborhood",
            "proposed_address",
            "justification",
            "status",
            "moderator_notes",
            "created_at",
            "resolved_at",
        )
        read_only_fields = ("status", "moderator_notes", "created_at", "resolved_at")


class ModeratorReviewReportSerializer(serializers.Serializer):
    """Acción del Moderador para aprobar o rechazar un reporte dudoso/anómalo (Tabla 4.1)."""

    new_status = serializers.ChoiceField(
        choices=[
            (ReliabilityStatus.VERIFIED.value, "Aprobar como Verificado (VERIFIED)"),
            (ReliabilityStatus.ANOMALOUS.value, "Confirmar como Falso/Anómalo (ANOMALOUS)"),
        ]
    )
    moderator_note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class ModeratorAccountManagementSerializer(serializers.ModelSerializer):
    """Vista administrativa para que el Moderador gestione cuentas y suspenda actores malintencionados."""

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)

    class Meta:
        model = UserProfile
        fields = (
            "id",
            "user_id",
            "username",
            "email",
            "last_login",
            "role",
            "managed_establishment",
            "verified_reports_count",
            "rejected_reports_count",
            "is_suspended",
            "verification_status",
            "is_verified",
            "business_legal_name",
            "business_tax_id",
            "verified_at",
            "created_at",
        )
        read_only_fields = (
            "user_id",
            "username",
            "email",
            "last_login",
            "verified_reports_count",
            "rejected_reports_count",
            "is_verified",
            "verified_at",
            "created_at",
        )


class ModeratorFlaggedPriceReportSerializer(serializers.ModelSerializer):
    """Vista exclusiva del Moderador sobre reportes dudosos (`ANOMALOUS` o `LOW_CONFIDENCE`)."""

    establishment_name = serializers.CharField(source="establishment.name", read_only=True)
    presentation_label = serializers.CharField(source="presentation.__str__", read_only=True)

    class Meta:
        model = PriceReport
        fields = (
            "id",
            "presentation",
            "presentation_label",
            "establishment",
            "establishment_name",
            "raw_price",
            "normalized_ref_price",
            "reference_unit_label",
            "reliability_status",
            "confidence_score",
            "anomaly_notes",
            "source_type",
            "reported_at",
        )


class AuditEventLogSerializer(serializers.ModelSerializer):
    """
    Serializer de solo lectura para la Bitácora Inmutable de Auditoría (`AuditEventLog`).
    Exclusivo para el rol administrativo `MODERATOR` (ISO/IEC 25010:2023 - No Repudio y Trazabilidad).
    """

    module_display = serializers.CharField(source="get_module_display", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)

    class Meta:
        model = AuditEventLog
        fields = (
            "id",
            "actor_user",
            "actor_username",
            "actor_role",
            "module",
            "module_display",
            "action_type",
            "severity",
            "severity_display",
            "target_model",
            "target_id",
            "target_repr",
            "summary",
            "previous_state",
            "new_state",
            "ip_hash",
            "created_at",
        )
        read_only_fields = fields


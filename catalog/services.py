"""
Capa de Servicios del Catálogo y Seguridad de Archivos Multimedia (`catalog/services.py`).
Cumple estrictamente con:
- `django-architecture-enforcer`: Lógica de negocio e I/O desacoplada de vistas y serializadores;
  excepciones propias de Python (`InvalidImageError`) y anotaciones de tipo completas.
- `django-security-auditor`: Mitigación OWASP Unrestricted File Upload:
  1. Límite duro de tamaño (máx. 5 MB).
  2. Lista blanca estricta de formatos reales por Magic Bytes (`JPEG`, `PNG`, `WEBP`).
  3. Protección contra Decompression Bombs (límite de píxeles).
  4. Purga forense del 100% de metadatos EXIF/GPS (Ley 1581 de 2012 y métrica M-06 = 1.00).
  5. Renombrado inmutable a `UUIDv4` (prevención de Path Traversal e inyección en nombres).
"""

import io
import uuid
from typing import Any, BinaryIO

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.html import strip_tags
from PIL import Image, UnidentifiedImageError

from accounts.models import ActorRole, UserProfile
from catalog.models import Establishment, PaymentMethod, Product, ProductPresentation

MAX_IMAGE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB
MAX_IMAGE_PIXELS_DEFAULT: int = 25_000_000  # 25 Megapíxeles

ALLOWED_IMAGE_FORMATS: dict[str, str] = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}


class InvalidImageError(ValueError):
    """Excepción de dominio/servicio lanzada cuando una imagen incumple políticas de integridad o seguridad."""


class EstablishmentImagePermissionError(PermissionError):
    """Excepción Anti-IDOR lanzada cuando un actor intenta modificar la imagen de un comercio ajeno."""


class ImageSecurityService:
    """Servicio transversal para validación criptográfica/estructural y sanitización EXIF de imágenes."""

    @staticmethod
    def validate_and_sanitize(
        file_obj: BinaryIO,
        filename: str = "",
        max_size_bytes: int = MAX_IMAGE_SIZE_BYTES,
        max_pixels: int = MAX_IMAGE_PIXELS_DEFAULT,
    ) -> ContentFile:
        """
        Valida un archivo binario de imagen, purga sus metadatos EXIF/GPS re-codificando la matriz
        de píxeles en memoria y devuelve un `ContentFile` seguro con nombre `UUIDv4`.
        """
        del filename  # El nombre original jamás se reutiliza para prevenir Path Traversal
        if file_obj is None:
            raise InvalidImageError("No se proporcionó ningún archivo de imagen.")

        file_obj.seek(0)
        raw_bytes = file_obj.read(max_size_bytes + 1)
        if not raw_bytes:
            raise InvalidImageError("El archivo de imagen está vacío.")

        if len(raw_bytes) > max_size_bytes:
            raise InvalidImageError(
                "El archivo excede el tamaño máximo permitido de 5 MB."
            )

        try:
            with Image.open(io.BytesIO(raw_bytes)) as probe_img:
                detected_format = (probe_img.format or "").upper()
                if detected_format not in ALLOWED_IMAGE_FORMATS:
                    raise InvalidImageError(
                        "El formato de imagen no está permitido. Use exclusivamente JPEG, PNG o WEBP."
                    )

                width, height = probe_img.size
                if width <= 0 or height <= 0 or (width * height) > max_pixels:
                    raise InvalidImageError(
                        "Las dimensiones o el total de píxeles de la imagen exceden el límite de seguridad."
                    )
                probe_img.verify()

            # Reabrir tras .verify() para decodificar píxeles reales y clonar sin diccionarios EXIF/GPS
            with Image.open(io.BytesIO(raw_bytes)) as src_img:
                src_img.load()
                # Si la imagen tiene paleta indexada (Modo 'P'), o transparencia indexada,
                # o formato JPEG que no soporta canal alfa o paletas, normalizamos adecuadamente.
                if detected_format == "JPEG":
                    if src_img.mode not in ("RGB", "L"):
                        src_img = src_img.convert("RGB")
                    clean_img = Image.new("RGB", src_img.size, (255, 255, 255))
                    clean_img.paste(src_img)
                else:
                    # Para PNG o WEBP: si viene en modo con paleta ('P', '1', etc.),
                    # convertir a RGBA o RGB para no perder la tabla de color (palette)
                    # al clonar en una nueva imagen vacía.
                    if src_img.mode in ("P", "1") or "transparency" in src_img.info or src_img.mode not in ("RGB", "RGBA", "L", "LA"):
                        src_img = src_img.convert("RGBA")

                    clean_img = Image.new(src_img.mode, src_img.size)
                    clean_img.paste(src_img)

                output_buffer = io.BytesIO()
                save_kwargs: dict[str, int | bool] = {}
                if detected_format in ("JPEG", "WEBP"):
                    save_kwargs["quality"] = 88
                if detected_format == "JPEG":
                    save_kwargs["optimize"] = True

                clean_img.save(output_buffer, format=detected_format, **save_kwargs)
        except InvalidImageError:
            raise
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
            raise InvalidImageError(
                "El archivo adjunto no es una imagen válida o está corrupto."
            ) from exc

        safe_extension = ALLOWED_IMAGE_FORMATS[detected_format]
        safe_filename = f"{uuid.uuid4()}{safe_extension}"
        return ContentFile(output_buffer.getvalue(), name=safe_filename)


def update_presentation_reference_image(
    *,
    presentation: ProductPresentation,
    uploaded_file: BinaryIO,
    filename: str = "",
) -> ProductPresentation:
    """
    Valida, sanitiza (purga EXIF/GPS) y persiste la imagen de referencia de una presentación del catálogo.
    """
    sanitized_content = ImageSecurityService.validate_and_sanitize(
        file_obj=uploaded_file,
        filename=filename,
    )
    if presentation.reference_image:
        presentation.reference_image.delete(save=False)
    presentation.reference_image.save(
        sanitized_content.name,
        sanitized_content,
        save=True,
    )
    return presentation


def update_product_representative_image(
    *,
    product: Product,
    uploaded_file: BinaryIO,
    filename: str = "",
) -> Product:
    """
    Valida, sanitiza (purga EXIF/GPS, máx. 5 MB, JPEG/PNG/WEBP, UUIDv4) y persiste la imagen
    representativa de un producto molde (`Product.product_image`).
    """
    sanitized_content = ImageSecurityService.validate_and_sanitize(
        file_obj=uploaded_file,
        filename=filename,
    )
    if product.product_image:
        product.product_image.delete(save=False)
    product.product_image.save(
        sanitized_content.name,
        sanitized_content,
        save=True,
    )
    return product


def update_payment_method_icon_image(
    *,
    payment_method: PaymentMethod,
    uploaded_file: BinaryIO,
    filename: str = "",
) -> PaymentMethod:
    """
    Valida, sanitiza (purga EXIF/GPS, máx. 5 MB, JPEG/PNG/WEBP, UUIDv4) y persiste el icono
    o logo oficial de un método de pago (`PaymentMethod.icon_image`).
    """
    sanitized_content = ImageSecurityService.validate_and_sanitize(
        file_obj=uploaded_file,
        filename=filename,
    )
    if payment_method.icon_image:
        payment_method.icon_image.delete(save=False)
    payment_method.icon_image.save(
        sanitized_content.name,
        sanitized_content,
        save=True,
    )
    return payment_method


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(strip_tags(value).split()).strip()


def user_owns_establishment(*, profile: UserProfile, establishment: Establishment) -> bool:
    """
    Verifica si un actor `MERCHANT` es propietario del establecimiento (relación 1 a muchos `owner`
    o vínculo `managed_establishment`).
    """
    return bool(
        profile.role == ActorRole.MERCHANT
        and (
            (establishment.owner_id is not None and establishment.owner_id == profile.user_id)
            or (
                profile.managed_establishment_id is not None
                and profile.managed_establishment_id == establishment.id
            )
        )
    )


def can_actor_manage_establishment(*, profile: UserProfile, establishment: Establishment) -> bool:
    """Retorna True si el actor es el propietario (`MERCHANT`) o un `MODERATOR`."""
    if profile.is_suspended:
        return False
    return bool(
        profile.role == ActorRole.MODERATOR
        or getattr(profile.user, "is_superuser", False)
        or getattr(profile.user, "is_staff", False)
        or user_owns_establishment(profile=profile, establishment=establishment)
    )


def _sync_establishment_payment_methods(
    establishment: Establishment,
    validated_data: dict[str, Any],
) -> None:
    """
    Sincroniza la relación muchos-a-muchos `payment_methods` si el payload incluye
    `payment_method_codes` (ej. `["cash", "nequi", "bre_b"]`).
    """
    if "payment_method_codes" not in validated_data:
        return
    raw_codes = validated_data.get("payment_method_codes") or []
    normalized_codes = [str(c).strip().lower() for c in raw_codes if str(c).strip()]
    methods = list(
        PaymentMethod.objects.filter(
            code__in=normalized_codes,
            is_active=True,
        )
    )
    establishment.payment_methods.set(methods)


@transaction.atomic
def create_establishment_for_actor(
    *,
    profile: UserProfile,
    validated_data: dict[str, Any],
) -> Establishment:
    """
    Crea un establecimiento asignando automáticamente `owner = profile.user` (relación 1 a muchos).
    Si el comercio aún no tenía `managed_establishment` principal asignado, vincula el primero automáticamente.
    """
    if profile.is_suspended or profile.role not in (ActorRole.MERCHANT, ActorRole.MODERATOR):
        raise EstablishmentImagePermissionError(
            "Solo los usuarios con rol Comercio (MERCHANT) o Moderador pueden crear establecimientos."
        )

    establishment = Establishment.objects.create(
        owner=profile.user,
        name=_clean_text(validated_data.get("name", "")),
        establishment_type=validated_data.get(
            "establishment_type",
            Establishment.EstablishmentType.NEIGHBORHOOD_SHOP,
        ),
        municipality=_clean_text(validated_data.get("municipality", "Armenia")) or "Armenia",
        neighborhood=_clean_text(validated_data.get("neighborhood", "")),
        address=_clean_text(validated_data.get("address", "")),
        latitude=validated_data.get("latitude"),
        longitude=validated_data.get("longitude"),
        is_active=True,
    )
    _sync_establishment_payment_methods(establishment, validated_data)

    if profile.role == ActorRole.MERCHANT and profile.managed_establishment_id is None:
        profile.managed_establishment = establishment
        profile.save(update_fields=["managed_establishment"])

    from accounts.models import AuditEventLog
    from accounts.services import record_audit_event

    record_audit_event(
        actor_user=profile.user,
        module=AuditEventLog.AuditModule.ESTABLISHMENT,
        action_type="ESTABLISHMENT_CREATED",
        target_model="Establishment",
        target_id=establishment.id,
        target_repr=establishment.name,
        summary=f"Se creó el establecimiento '{establishment.name}' en {establishment.municipality}.",
        severity=AuditEventLog.AuditSeverity.INFO,
        new_state={
            "id": establishment.id,
            "name": establishment.name,
            "establishment_type": establishment.establishment_type,
            "municipality": establishment.municipality,
            "neighborhood": establishment.neighborhood,
            "address": establishment.address,
            "owner_id": establishment.owner_id,
            "payment_method_codes": list(
                establishment.payment_methods.filter(is_active=True).values_list("code", flat=True)
            ),
        },
    )
    return establishment


@transaction.atomic
def update_establishment_for_actor(
    *,
    profile: UserProfile,
    establishment: Establishment,
    validated_data: dict[str, Any],
) -> Establishment:
    """
    Actualiza los datos de un establecimiento verificando propiedad estricta (Anti-IDOR).
    Solo el usuario propietario (`establishment.owner`) o un `MODERATOR` puede editarlo.
    """
    if not can_actor_manage_establishment(profile=profile, establishment=establishment):
        raise EstablishmentImagePermissionError(
            "Acceso denegado (Anti-IDOR): Solo el comercio propietario de este establecimiento "
            "o un Moderador pueden editar sus datos."
        )

    previous_state = {
        "name": establishment.name,
        "establishment_type": establishment.establishment_type,
        "municipality": establishment.municipality,
        "neighborhood": establishment.neighborhood,
        "address": establishment.address,
        "is_active": establishment.is_active,
        "payment_method_codes": list(
            establishment.payment_methods.filter(is_active=True).values_list("code", flat=True)
        ),
    }

    for text_field in ("name", "municipality", "neighborhood", "address"):
        if text_field in validated_data:
            setattr(establishment, text_field, _clean_text(validated_data[text_field]))

    for other_field in ("establishment_type", "latitude", "longitude", "is_active"):
        if other_field in validated_data:
            setattr(establishment, other_field, validated_data[other_field])

    establishment.save()
    _sync_establishment_payment_methods(establishment, validated_data)

    from accounts.models import AuditEventLog
    from accounts.services import record_audit_event

    new_state = {
        "name": establishment.name,
        "establishment_type": establishment.establishment_type,
        "municipality": establishment.municipality,
        "neighborhood": establishment.neighborhood,
        "address": establishment.address,
        "is_active": establishment.is_active,
        "payment_method_codes": list(
            establishment.payment_methods.filter(is_active=True).values_list("code", flat=True)
        ),
    }
    record_audit_event(
        actor_user=profile.user,
        module=AuditEventLog.AuditModule.ESTABLISHMENT,
        action_type="ESTABLISHMENT_UPDATED",
        target_model="Establishment",
        target_id=establishment.id,
        target_repr=establishment.name,
        summary=f"Se actualizaron los datos del establecimiento '{establishment.name}'.",
        severity=AuditEventLog.AuditSeverity.INFO,
        previous_state=previous_state,
        new_state=new_state,
    )
    return establishment


@transaction.atomic
def deactivate_establishment_for_actor(
    *,
    profile: UserProfile,
    establishment: Establishment,
) -> Establishment:
    """
    Desactiva (borrado lógico `is_active = False`) un establecimiento verificando propiedad (Anti-IDOR).
    """
    if not can_actor_manage_establishment(profile=profile, establishment=establishment):
        raise EstablishmentImagePermissionError(
            "Acceso denegado (Anti-IDOR): Solo el comercio propietario de este establecimiento "
            "o un Moderador pueden eliminarlo o desactivarlo."
        )
    establishment.is_active = False
    establishment.save(update_fields=["is_active"])

    from accounts.models import AuditEventLog
    from accounts.services import record_audit_event

    record_audit_event(
        actor_user=profile.user,
        module=AuditEventLog.AuditModule.ESTABLISHMENT,
        action_type="ESTABLISHMENT_DEACTIVATED",
        target_model="Establishment",
        target_id=establishment.id,
        target_repr=establishment.name,
        summary=f"Se desactivó el establecimiento '{establishment.name}'.",
        severity=AuditEventLog.AuditSeverity.WARNING,
        previous_state={"is_active": True},
        new_state={"is_active": False},
    )
    return establishment


def update_establishment_logo_image(
    *,
    profile: UserProfile,
    establishment: Establishment,
    uploaded_file: BinaryIO,
    filename: str = "",
) -> Establishment:
    """
    Valida propiedad sobre el establecimiento (Anti-IDOR / OWASP A01), sanitiza la imagen
    (purga EXIF/GPS, máx. 5 MB, JPEG/PNG/WEBP) y actualiza `establishment.logo_image`.
    """
    if not can_actor_manage_establishment(profile=profile, establishment=establishment):
        raise EstablishmentImagePermissionError(
            "Acceso denegado (Anti-IDOR): Solo el comercio propietario de este establecimiento "
            "o un Moderador pueden actualizar su imagen o logo."
        )

    sanitized_content = ImageSecurityService.validate_and_sanitize(
        file_obj=uploaded_file,
        filename=filename,
    )
    if establishment.logo_image:
        establishment.logo_image.delete(save=False)
    establishment.logo_image.save(
        sanitized_content.name,
        sanitized_content,
        save=True,
    )
    from accounts.models import AuditEventLog
    from accounts.services import record_audit_event

    record_audit_event(
        actor_user=profile.user,
        module=AuditEventLog.AuditModule.ESTABLISHMENT,
        action_type="ESTABLISHMENT_LOGO_UPDATED",
        target_model="Establishment",
        target_id=establishment.id,
        target_repr=establishment.name,
        summary=f"Se actualizó el logo del establecimiento '{establishment.name}'.",
        severity=AuditEventLog.AuditSeverity.INFO,
        new_state={"logo_image": str(establishment.logo_image)},
    )
    return establishment

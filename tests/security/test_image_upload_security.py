"""
Suite de Pruebas TDD y Pentesting de Subida de Imágenes (Fase RED -> GREEN).
Cubre:
1. Pruebas Unitarias Puras sobre `ImageSecurityService` (sin base de datos):
   - Validación de formatos permitidos (JPEG, PNG, WEBP) por Magic Bytes.
   - Rechazo de archivos que excedan los 5 MB (`InvalidImageError`).
   - Rechazo de archivos maliciosos disfrazados (Polyglot / Spoofing de extensión `.jpg` con payload ejecutable o SVG/XSS).
   - Rechazo de bombas de descompresión (> 25 Megapíxeles).
   - Purga forense de metadatos EXIF/GPS (Privacidad por Diseño Ley 1581 / M-06 = 1.00) y renombrado a UUIDv4.
2. Pruebas de Integración de Contratos API (con base de datos y `settings.MEDIA_ROOT` aislado en `tmp_path`):
   - `POST /api/v1/presentations/{id}/image/` (Imagen de referencia del catálogo).
   - `POST /api/v1/price-reports/` con `evidence_image` en `multipart/form-data`.
"""

import io
import uuid
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import ActorRole, UserProfile, VerificationStatus
from catalog.models import Establishment, Product, ProductPresentation
from catalog.services import ImageSecurityService, InvalidImageError
from core_domain.entities import ProductCategory, UnitOfMeasure

User = get_user_model()


def _build_image_bytes(
    fmt: str = "JPEG",
    size: tuple[int, int] = (120, 120),
    color: tuple[int, int, int] = (34, 139, 34),
    with_gps_exif: bool = False,
) -> bytes:
    """Genera una imagen binaria válida en memoria (opcionalmente con metadatos EXIF/GPS inyectados)."""
    image = Image.new("RGB", size, color=color)
    buffer = io.BytesIO()
    if with_gps_exif and fmt.upper() == "JPEG":
        exif = image.getexif()
        # 0x010F = Make (Marca del teléfono), 0x8825 = GPSInfo tag
        exif[0x010F] = "Xiaomi Redmi Note 13 Pro - Dispositivo Personal"
        exif[0x0132] = "2026:11:09 16:45:00"
        exif[0x8825] = {1: "N", 2: (4, 32, 20), 3: "W", 4: (75, 40, 28)}
        image.save(buffer, format=fmt, exif=exif.tobytes())
    else:
        image.save(buffer, format=fmt)
    return buffer.getvalue()


class TestImageSecurityServiceUnitTDD:
    """Pruebas unitarias aisladas sobre la capa de servicio `ImageSecurityService` (Cero DB)."""

    @pytest.mark.parametrize(
        ("fmt", "ext"),
        [
            ("JPEG", ".jpg"),
            ("PNG", ".png"),
            ("WEBP", ".webp"),
        ],
    )
    def test_sanitize_valid_formats_strips_exif_and_renames_to_uuid4(self, fmt: str, ext: str) -> None:
        # Arrange
        raw_bytes = _build_image_bytes(fmt=fmt, with_gps_exif=(fmt == "JPEG"))
        uploaded_file = SimpleUploadedFile(
            name=f"../../peligro_path_traversal_arroz{ext}",
            content=raw_bytes,
            content_type=f"image/{fmt.lower()}",
        )

        # Act
        sanitized = ImageSecurityService.validate_and_sanitize(
            file_obj=uploaded_file,
            filename=uploaded_file.name,
        )

        # Assert
        assert sanitized.name.endswith(ext)
        assert ".." not in sanitized.name
        assert "peligro" not in sanitized.name
        stem = sanitized.name.rsplit(".", 1)[0]
        assert str(uuid.UUID(stem, version=4)) == stem

        sanitized.seek(0)
        reopened = Image.open(sanitized)
        assert dict(reopened.getexif()) == {}

    def test_reject_file_exceeding_5mb_limit(self) -> None:
        # Arrange: 5 MB + 1 byte
        oversized_bytes = b"\xff\xd8\xff\xe0" + (b"A" * (5 * 1024 * 1024))
        uploaded_file = SimpleUploadedFile(
            name="foto_pesada.jpg",
            content=oversized_bytes,
            content_type="image/jpeg",
        )

        # Act & Assert
        with pytest.raises(InvalidImageError, match="5 MB"):
            ImageSecurityService.validate_and_sanitize(
                file_obj=uploaded_file,
                filename=uploaded_file.name,
            )

    def test_reject_polyglot_executable_or_svg_xss_spoofed_as_jpg(self) -> None:
        # Arrange: Payload SVG con script XSS renombrado a .jpg
        malicious_svg_xss = (
            b'<svg xmlns="http://www.w3.org/2000/svg">'
            b"<script>alert('XSS');</script></svg>"
        )
        uploaded_file = SimpleUploadedFile(
            name="trampa_xss.jpg",
            content=malicious_svg_xss,
            content_type="image/jpeg",
        )

        # Act & Assert
        with pytest.raises(InvalidImageError):
            ImageSecurityService.validate_and_sanitize(
                file_obj=uploaded_file,
                filename=uploaded_file.name,
            )

    def test_reject_disallowed_gif_format_even_if_valid_image(self) -> None:
        # Arrange: Imagen GIF real pero fuera de la lista blanca (JPEG, PNG, WEBP)
        gif_bytes = _build_image_bytes(fmt="GIF")
        uploaded_file = SimpleUploadedFile(
            name="animacion.gif",
            content=gif_bytes,
            content_type="image/gif",
        )

        # Act & Assert
        with pytest.raises(InvalidImageError, match="formato"):
            ImageSecurityService.validate_and_sanitize(
                file_obj=uploaded_file,
                filename=uploaded_file.name,
            )

    def test_reject_decompression_bomb_exceeding_max_pixels(self) -> None:
        # Arrange: Imagen que supera el umbral de píxeles configurado
        raw_bytes = _build_image_bytes(fmt="PNG", size=(200, 200))
        uploaded_file = SimpleUploadedFile(
            name="bomba.png",
            content=raw_bytes,
            content_type="image/png",
        )

        # Act & Assert: Forzamos límite bajo en la llamada para verificar la guarda sin agotar RAM del test
        with pytest.raises(InvalidImageError, match="dimensiones|píxeles"):
            ImageSecurityService.validate_and_sanitize(
                file_obj=uploaded_file,
                filename=uploaded_file.name,
                max_pixels=10_000,  # 200x200 = 40,000 px > 10,000 px
            )


@pytest.mark.django_db
class TestImageUploadEndpointsIntegrationTDD:
    """Pruebas de contrato HTTP para subida de imágenes en Catálogo y Reportes de Precio."""

    def test_authenticated_actor_can_upload_reference_image_to_presentation_and_report_with_evidence(
        self,
        settings,
        tmp_path,
    ) -> None:
        # Arrange
        settings.MEDIA_ROOT = tmp_path
        user = User.objects.create_user(
            username="reporter_foto",
            email="reporter_foto@pricecol.co",
            password="SecurePassword123!",
        )
        UserProfile.objects.create(
            user=user,
            role=ActorRole.REPORTER,
            verification_status=VerificationStatus.VERIFIED,
            is_verified=True,
            accepted_data_policy=True,
        )
        establishment = Establishment.objects.create(
            name="Supermercado La 14 Armenia",
            establishment_type=Establishment.EstablishmentType.SUPERMARKET,
            municipality="Armenia",
            neighborhood="Centro",
            address="Cra 14 # 18-20",
        )
        product = Product.objects.create(
            name="Café Tostado y Molido",
            category=ProductCategory.GROCERY.value,
            aliases="cafe, tinto",
        )
        presentation = ProductPresentation.objects.create(
            product=product,
            brand="Quindío",
            presentation_name="Bolsa 500 g",
            ean_barcode="7709998887776",
            quantity=Decimal("500.000"),
            unit=UnitOfMeasure.GRAM.value,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        ref_img_bytes = _build_image_bytes(fmt="JPEG", with_gps_exif=True)
        ref_upload = SimpleUploadedFile("cafe_quindio.jpg", ref_img_bytes, content_type="image/jpeg")

        # Act 1: Subir imagen de referencia a la presentación del catálogo
        pres_res = client.post(
            f"/api/v1/presentations/{presentation.id}/image/",
            data={"reference_image": ref_upload},
            format="multipart",
        )

        # Assert 1
        assert pres_res.status_code == 200
        assert pres_res.data["reference_image"] is not None
        presentation.refresh_from_db()
        assert bool(presentation.reference_image) is True
        saved_ref_img = Image.open(presentation.reference_image.path)
        assert dict(saved_ref_img.getexif()) == {}

        # Act 2: Registrar un reporte de precio en góndola adjuntando foto de evidencia
        ev_img_bytes = _build_image_bytes(fmt="WEBP")
        ev_upload = SimpleUploadedFile("evidencia_gondola.webp", ev_img_bytes, content_type="image/webp")
        report_res = client.post(
            "/api/v1/price-reports/",
            data={
                "presentation_id": presentation.id,
                "establishment_id": establishment.id,
                "raw_price": "14500.00",
                "evidence_image": ev_upload,
            },
            format="multipart",
        )

        # Assert 2
        assert report_res.status_code == 201
        assert report_res.data["evidence_image"] is not None

    def test_anonymous_user_cannot_upload_reference_image(self, settings, tmp_path) -> None:
        # Arrange
        settings.MEDIA_ROOT = tmp_path
        product = Product.objects.create(
            name="Sal Refinada",
            category=ProductCategory.GROCERY.value,
        )
        presentation = ProductPresentation.objects.create(
            product=product,
            brand="Refisal",
            presentation_name="Bolsa 1 kg",
            quantity=Decimal("1.000"),
            unit=UnitOfMeasure.KILOGRAM.value,
        )
        client = APIClient()
        img_bytes = _build_image_bytes(fmt="PNG")
        upload = SimpleUploadedFile("sal.png", img_bytes, content_type="image/png")

        # Act
        response = client.post(
            f"/api/v1/presentations/{presentation.id}/image/",
            data={"reference_image": upload},
            format="multipart",
        )

        # Assert
        assert response.status_code in (401, 403)

    def test_actor_can_upload_profile_image_on_me_with_exif_purged_and_rejects_invalid_file(
        self,
        settings,
        tmp_path,
    ) -> None:
        # Arrange
        settings.MEDIA_ROOT = tmp_path
        user = User.objects.create_user(
            username="perfil_usuario",
            email="perfil@pricecol.co",
            password="SecurePassword123!",
        )
        profile = UserProfile.objects.create(
            user=user,
            role=ActorRole.REPORTER,
            accepted_data_policy=True,
        )
        client = APIClient()
        client.force_authenticate(user=user)

        avatar_bytes = _build_image_bytes(fmt="JPEG", with_gps_exif=True)
        avatar_upload = SimpleUploadedFile("mi_selfie_con_gps.jpg", avatar_bytes, content_type="image/jpeg")

        # Act 1: Subir foto de perfil en PATCH /api/v1/auth/me/
        res_patch = client.patch(
            "/api/v1/auth/me/",
            data={"profile_image": avatar_upload},
            format="multipart",
        )

        # Assert 1: 200 OK, renombrado a UUIDv4 y 0 metadatos EXIF/GPS
        assert res_patch.status_code == 200
        assert res_patch.data["profile_image"] is not None
        assert "mi_selfie_con_gps" not in res_patch.data["profile_image"]
        profile.refresh_from_db()
        assert bool(profile.profile_image) is True
        saved_avatar = Image.open(profile.profile_image.path)
        assert dict(saved_avatar.getexif()) == {}

        # Act 2: Subir foto vía POST /api/v1/auth/me/avatar/ con archivo malicioso .svg
        bad_svg = SimpleUploadedFile(
            "avatar_xss.svg",
            b"<svg><script>alert('xss')</script></svg>",
            content_type="image/svg+xml",
        )
        res_bad = client.post(
            "/api/v1/auth/me/avatar/",
            data={"profile_image": bad_svg},
            format="multipart",
        )

        # Assert 2: Rechazado con 400 Bad Request
        assert res_bad.status_code == 400

    def test_merchant_can_upload_logo_for_own_establishment_but_idor_blocks_competitor_and_reporter(
        self,
        settings,
        tmp_path,
    ) -> None:
        # Arrange
        settings.MEDIA_ROOT = tmp_path
        est_own = Establishment.objects.create(
            name="Minimercado Don Chucho",
            establishment_type=Establishment.EstablishmentType.MINIMARKET,
            municipality="Armenia",
            neighborhood="Granada",
            address="Calle 10 # 15-20",
        )
        est_competitor = Establishment.objects.create(
            name="Supermercado Competidor",
            establishment_type=Establishment.EstablishmentType.SUPERMARKET,
            municipality="Armenia",
            neighborhood="Centro",
            address="Cra 15 # 20-10",
        )

        merchant_user = User.objects.create_user(
            username="don_chucho_merchant",
            email="chucho@pricecol.co",
            password="SecurePassword123!",
        )
        UserProfile.objects.create(
            user=merchant_user,
            role=ActorRole.MERCHANT,
            managed_establishment=est_own,
            verification_status=VerificationStatus.VERIFIED,
            is_verified=True,
            accepted_data_policy=True,
        )

        reporter_user = User.objects.create_user(
            username="vecino_reporter",
            email="vecino@pricecol.co",
            password="SecurePassword123!",
        )
        UserProfile.objects.create(
            user=reporter_user,
            role=ActorRole.REPORTER,
            accepted_data_policy=True,
        )

        client = APIClient()

        # Act 1: Un REPORTER intenta cambiar el logo de un comercio -> 403 Forbidden
        client.force_authenticate(user=reporter_user)
        logo_bytes_1 = _build_image_bytes(fmt="PNG")
        res_reporter = client.post(
            f"/api/v1/establishments/{est_own.id}/image/",
            data={"logo_image": SimpleUploadedFile("hack.png", logo_bytes_1, content_type="image/png")},
            format="multipart",
        )
        assert res_reporter.status_code == 403

        # Act 2 (Anti-IDOR): El MERCHANT intenta cambiar el logo del COMPETIDOR -> 403 Forbidden
        client.force_authenticate(user=merchant_user)
        logo_bytes_2 = _build_image_bytes(fmt="PNG")
        res_idor = client.post(
            f"/api/v1/establishments/{est_competitor.id}/image/",
            data={"logo_image": SimpleUploadedFile("sabotaje.png", logo_bytes_2, content_type="image/png")},
            format="multipart",
        )
        assert res_idor.status_code == 403

        # Act 3 (Happy Path): El MERCHANT sube el logo de SU PROPIO establecimiento -> 200 OK
        logo_bytes_own = _build_image_bytes(fmt="JPEG", with_gps_exif=True)
        res_own = client.post(
            f"/api/v1/establishments/{est_own.id}/image/",
            data={"logo_image": SimpleUploadedFile("logo_don_chucho.jpg", logo_bytes_own, content_type="image/jpeg")},
            format="multipart",
        )

        # Assert 3
        assert res_own.status_code == 200
        assert res_own.data["logo_image"] is not None
        est_own.refresh_from_db()
        assert bool(est_own.logo_image) is True
        saved_logo = Image.open(est_own.logo_image.path)
        assert dict(saved_logo.getexif()) == {}

    def test_moderator_can_upload_product_image_with_exif_purged_and_non_moderator_is_blocked(
        self,
        settings,
        tmp_path,
    ) -> None:
        # Arrange
        settings.MEDIA_ROOT = tmp_path
        product = Product.objects.create(
            name="Ajo",
            category=ProductCategory.PERISHABLE.value,
            aliases="ajo, cabeza de ajo",
            description="Ajo fresco para sazón.",
        )

        reporter_user = User.objects.create_user(
            username="reporter_normal",
            email="rep_ajo@pricecol.co",
            password="SecurePassword123!",
        )
        UserProfile.objects.create(
            user=reporter_user,
            role=ActorRole.REPORTER,
            accepted_data_policy=True,
        )

        moderator_user = User.objects.create_user(
            username="mod_catalogo",
            email="mod_ajo@pricecol.co",
            password="SecurePassword123!",
            is_staff=True,
        )
        UserProfile.objects.create(
            user=moderator_user,
            role=ActorRole.MODERATOR,
            accepted_data_policy=True,
        )

        client = APIClient()

        # Act 1: Un REPORTER intenta subir imagen representativa del producto molde -> 403 Forbidden
        client.force_authenticate(user=reporter_user)
        img_bytes_1 = _build_image_bytes(fmt="PNG")
        res_forbidden = client.post(
            f"/api/v1/products/{product.id}/image/",
            data={"product_image": SimpleUploadedFile("ajo_hack.png", img_bytes_1, content_type="image/png")},
            format="multipart",
        )
        assert res_forbidden.status_code == 403

        # Act 2 (Happy Path): El MODERATOR sube la imagen representativa del producto con EXIF -> 200 OK
        client.force_authenticate(user=moderator_user)
        img_bytes_mod = _build_image_bytes(fmt="JPEG", with_gps_exif=True)
        res_ok = client.post(
            f"/api/v1/products/{product.id}/image/",
            data={"product_image": SimpleUploadedFile("ajo_fresco_gps.jpg", img_bytes_mod, content_type="image/jpeg")},
            format="multipart",
        )

        # Assert 2: 200 OK, `product_image` presente, renombrado a UUIDv4 y 0 metadatos EXIF/GPS
        assert res_ok.status_code == 200
        assert res_ok.data["product_image"] is not None
        assert "ajo_fresco_gps" not in res_ok.data["product_image"]
        product.refresh_from_db()
        assert bool(product.product_image) is True
        saved_prod_img = Image.open(product.product_image.path)
        assert dict(saved_prod_img.getexif()) == {}




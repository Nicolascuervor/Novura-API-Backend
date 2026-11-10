"""
Comando `python manage.py reset_clean_moderator`:
Ejecuta una limpieza total de la base de datos (catálogo, reportes, solicitudes de corrección,
sesiones, bitácoras de admin, archivos en `media/` y cuentas de prueba) y deja únicamente
el usuario Moderador activo (`moderador_admin` / `moderador@pricecol.co`) con su ID codificado
de 9 dígitos no incremental y `last_login` activo.
"""

import shutil
from pathlib import Path

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import (
    ActorRole,
    EstablishmentCorrectionRequest,
    UserProfile,
    VerificationStatus,
)
from accounts.services import generate_encoded_entity_id
from catalog.models import Establishment, Product, ProductPresentation
from pricing.models import PriceReport

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Limpia por completo todas las tablas de la base de datos y archivos media de prueba, "
        "dejando únicamente el usuario Moderador activo con ID codificado no secuencial."
    )

    def handle(self, *args, **options) -> None:
        del args, options
        self.stdout.write("Iniciando limpieza total de la base de datos y directorio media/...")

        with transaction.atomic():
            PriceReport.objects.all().delete()
            EstablishmentCorrectionRequest.objects.all().delete()
            ProductPresentation.objects.all().delete()
            Product.objects.all().delete()
            Establishment.objects.all().delete()
            LogEntry.objects.all().delete()
            Session.objects.all().delete()
            UserProfile.objects.all().delete()
            User.objects.all().delete()

            moderator_email = "moderador@pricecol.co"
            moderator_user = User(
                id=generate_encoded_entity_id(User, seed_hint=moderator_email),
                username="moderador_admin",
                email=moderator_email,
                is_staff=True,
                is_superuser=True,
                is_active=True,
            )
            moderator_user.set_password("Pricecol2026*")
            moderator_user.save()
            update_last_login(None, moderator_user)

            moderator_profile = UserProfile.objects.create(
                id=generate_encoded_entity_id(UserProfile, seed_hint=f"profile:{moderator_user.id}"),
                user=moderator_user,
                role=ActorRole.MODERATOR,
                accepted_data_policy=True,
                verification_status=VerificationStatus.VERIFIED,
            )

        # Limpiar archivos de imágenes subidas en media/ (conservando la carpeta raíz)
        media_root = Path(settings.MEDIA_ROOT)
        if media_root.exists():
            for child in media_root.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                elif child.is_file() and child.name != ".gitkeep":
                    child.unlink(missing_ok=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Limpieza total completada. Único usuario activo: "
                f"username='{moderator_user.username}', email='{moderator_user.email}', "
                f"user.id={moderator_user.id}, profile.id={moderator_profile.id}, "
                f"last_login={moderator_user.last_login.isoformat()}"
            )
        )

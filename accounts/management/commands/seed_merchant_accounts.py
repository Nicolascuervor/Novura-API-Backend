"""
Comando `python manage.py seed_merchant_accounts`:
Crea y verifica oficialmente la cuenta de representante legal / Comercio (`MERCHANT`)
para cada uno de los establecimientos registrados en `catalog_establishment`,
asociando `managed_establishment`, `verification_status = VERIFIED`, `is_verified = True`,
Razón Social (`business_legal_name`), NIT (`business_tax_id`), `verified_by` (Moderador),
IDs codificados no incrementales de 9 dígitos y `last_login` activo.
No altera ni borra los logos (`logo_image`) que ya hayan sido subidos a los establecimientos.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import ActorRole, UserProfile, VerificationStatus
from accounts.services import generate_encoded_entity_id
from catalog.models import Establishment

User = get_user_model()

# Mapa de metadatos corporativos y credenciales para cada establecimiento de Armenia, Quindío
MERCHANT_SPECS_BY_ESTABLISHMENT_NAME: dict[str, dict[str, str]] = {
    "Tiendas Ara": {
        "username": "comercio_ara",
        "email": "ara@pricecol.co",
        "legal_name": "Jerónimo Martins Colombia S.A.S.",
        "tax_id": "900480569-1",
    },
    "Tiendas D1": {
        "username": "comercio_d1",
        "email": "d1@pricecol.co",
        "legal_name": "D1 S.A.S.",
        "tax_id": "900276962-1",
    },
    "Dollarcity": {
        "username": "comercio_dollarcity",
        "email": "dollarcity@pricecol.co",
        "legal_name": "Dollarcity Colombia S.A.S.",
        "tax_id": "900843120-4",
    },
    "Carulla": {
        "username": "comercio_carulla",
        "email": "carulla@pricecol.co",
        "legal_name": "Almacenes Éxito S.A. - Marca Carulla",
        "tax_id": "890900608-9",
    },
    "Olímpica": {
        "username": "comercio_olimpica",
        "email": "olimpica@pricecol.co",
        "legal_name": "Supertiendas y Droguerías Olímpica S.A.",
        "tax_id": "890107487-3",
    },
    "Autoservicio Surti Hogar": {
        "username": "comercio_surti_hogar",
        "email": "surtihogar@pricecol.co",
        "legal_name": "Inversiones Surti Hogar del Quindío S.A.S.",
        "tax_id": "901124510-2",
    },
    "Super Inter Avenida Centenario": {
        "username": "comercio_super_inter",
        "email": "superinter@pricecol.co",
        "legal_name": "Super Inter Supermercados S.A.S.",
        "tax_id": "800149695-1",
    },
    "Autoservicio Rindemax": {
        "username": "comercio_rindemax",
        "email": "rindemax@pricecol.co",
        "legal_name": "Comercializadora Rindemax Armenia S.A.S.",
        "tax_id": "900631480-7",
    },
    "Metromarket": {
        "username": "comercio_metromarket",
        "email": "metromarket@pricecol.co",
        "legal_name": "Metromarket del Eje S.A.S.",
        "tax_id": "901289340-5",
    },
    "Supermercado Laureles": {
        "username": "comercio_laureles",
        "email": "laureles@pricecol.co",
        "legal_name": "Abastecedora Supermercado Laureles Ltda.",
        "tax_id": "801004219-8",
    },
    "Supermercado Multiahorro": {
        "username": "comercio_multiahorro",
        "email": "multiahorro@pricecol.co",
        "legal_name": "Supermercado Multiahorro del Centro S.A.S.",
        "tax_id": "900712890-3",
    },
    "El Cosechero de Armenia": {
        "username": "comercio_el_cosechero",
        "email": "elcosechero@pricecol.co",
        "legal_name": "Distribuidora Agrícola El Cosechero S.A.S.",
        "tax_id": "900518432-6",
    },
    "Andi Su Mercado": {
        "username": "comercio_andi_mercado",
        "email": "andimercado@pricecol.co",
        "legal_name": "Andi Su Mercado Mercar S.A.S.",
        "tax_id": "890001542-0",
    },
    "Ventanilla Verde Supermercado": {
        "username": "comercio_ventanilla_verde",
        "email": "ventanillaverde@pricecol.co",
        "legal_name": "Supermercado Ventanilla Verde S.A.S.",
        "tax_id": "900945112-9",
    },
    "Tienda Limonar": {
        "username": "comercio_tienda_limonar",
        "email": "tiendalimonar@pricecol.co",
        "legal_name": "Minimercado y Tienda El Limonar",
        "tax_id": "75089412-3",
    },
}


class Command(BaseCommand):
    help = (
        "Crea y verifica como empresa confirmada (MERCHANT + VERIFIED) el usuario representante "
        "de cada establecimiento registrado en la base de datos."
    )

    def handle(self, *args, **options) -> None:
        del args, options
        self.stdout.write("Vinculando y verificando representantes oficiales de cada establecimiento...")

        moderator_user = User.objects.filter(is_superuser=True).first() or User.objects.filter(is_staff=True).first()
        establishments = Establishment.objects.filter(is_active=True).order_by("id")

        if not establishments.exists():
            self.stdout.write(self.style.WARNING("No se encontraron establecimientos activos en la base de datos."))
            return

        now = timezone.now()
        created_users = 0
        updated_users = 0

        with transaction.atomic():
            for est in establishments:
                spec = MERCHANT_SPECS_BY_ESTABLISHMENT_NAME.get(est.name)
                if spec is None:
                    slug = (
                        est.name.lower()
                        .replace(" ", "_")
                        .replace("á", "a")
                        .replace("é", "e")
                        .replace("í", "i")
                        .replace("ó", "o")
                        .replace("ú", "u")
                    )[:24]
                    spec = {
                        "username": f"comercio_{slug}",
                        "email": f"{slug}@pricecol.co",
                        "legal_name": f"{est.name} S.A.S.",
                        "tax_id": f"900{est.id:06d}-1",
                    }

                user = User.objects.filter(email__iexact=spec["email"]).first()
                if user is None:
                    user = User(
                        id=generate_encoded_entity_id(User, seed_hint=spec["email"]),
                        username=spec["username"],
                        email=spec["email"],
                        is_active=True,
                    )
                    user.set_password("Pricecol2026*")
                    user.save()
                    update_last_login(None, user)
                    created_users += 1
                else:
                    user.username = spec["username"]
                    user.is_active = True
                    user.set_password("Pricecol2026*")
                    user.save(update_fields=["username", "is_active", "password"])
                    if user.last_login is None:
                        update_last_login(None, user)
                    updated_users += 1

                profile = UserProfile.objects.filter(user=user).first()
                if profile is None:
                    profile = UserProfile.objects.create(
                        id=generate_encoded_entity_id(UserProfile, seed_hint=f"profile:{user.id}"),
                        user=user,
                        role=ActorRole.MERCHANT,
                        managed_establishment=est,
                        accepted_data_policy=True,
                        verification_status=VerificationStatus.VERIFIED,
                        business_legal_name=spec["legal_name"],
                        business_tax_id=spec["tax_id"],
                        verification_requested_at=now,
                        verified_at=now,
                        verified_by=moderator_user,
                        verification_notes=(
                            "Empresa verificada oficialmente y vinculada a su establecimiento comercial en Armenia, Quindío."
                        ),
                    )
                else:
                    profile.role = ActorRole.MERCHANT
                    profile.managed_establishment = est
                    profile.accepted_data_policy = True
                    profile.verification_status = VerificationStatus.VERIFIED
                    profile.business_legal_name = spec["legal_name"]
                    profile.business_tax_id = spec["tax_id"]
                    profile.verification_requested_at = profile.verification_requested_at or now
                    profile.verified_at = now
                    profile.verified_by = moderator_user
                    profile.verification_notes = (
                        "Empresa verificada oficialmente y vinculada a su establecimiento comercial en Armenia, Quindío."
                    )
                    profile.save()

                if est.owner_id != user.id:
                    est.owner = user
                    est.save(update_fields=["owner"])

                self.stdout.write(
                    self.style.SUCCESS(
                        f" [OK] Establecimiento #{est.id} '{est.name}' -> "
                        f"Usuario='{user.username}' ({user.email}) | "
                        f"user.id={user.id} | profile.id={profile.id} | "
                        f"NIT={profile.business_tax_id} | VERIFIED={profile.is_verified}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nProceso completado: {created_users} cuentas de comercio creadas y verificadas, "
                f"{updated_users} actualizadas. Contraseña estándar: Pricecol2026*"
            )
        )

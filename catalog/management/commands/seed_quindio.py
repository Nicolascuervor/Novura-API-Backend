"""
Comando `python manage.py seed_quindio`:
Resuelve la Pregunta Abierta #5 de la Guía del Seminario Nuclear:
"¿De dónde provienen los primeros datos, antes de que exista una comunidad de reportantes?
Puede considerarse, por ejemplo, el uso de fuentes públicas como el Sistema de Información de
Precios del Sector Agropecuario (SIPSA) del DANE."
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import ActorRole, UserProfile
from catalog.models import Establishment, Product, ProductPresentation
from core_domain.entities import ProductCategory, SourceType, UnitOfMeasure
from pricing.services import ReportPriceUseCase

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Puebla la base de datos con el catálogo inicial de productos de la canasta familiar, "
        "establecimientos en Armenia/Quindío y precios base de referencia pública (DANE SIPSA) y comunitaria."
    )

    def handle(self, *args, **options) -> None:
        self.stdout.write("Iniciando carga de datos semilla para Armenia y Quindío (SIPSA / Canasta Familiar)...")

        establishments_data = [
            {
                "name": "Tienda de Barrio Don Chucho",
                "establishment_type": Establishment.EstablishmentType.NEIGHBORHOOD_SHOP,
                "municipality": "Armenia",
                "neighborhood": "La Castellana",
                "address": "Calle 10 Norte # 14-22",
                "latitude": Decimal("4.548910"),
                "longitude": Decimal("-75.661230"),
            },
            {
                "name": "Granero y Tienda El Cafetal",
                "establishment_type": Establishment.EstablishmentType.NEIGHBORHOOD_SHOP,
                "municipality": "Armenia",
                "neighborhood": "Centro / Plaza Minorista",
                "address": "Carrera 18 # 19-40",
                "latitude": Decimal("4.533890"),
                "longitude": Decimal("-75.681110"),
            },
            {
                "name": "Minimercado Mercar Quindío",
                "establishment_type": Establishment.EstablishmentType.MINIMARKET,
                "municipality": "Armenia",
                "neighborhood": "El Bosque",
                "address": "Carrera 23 # 12-05",
                "latitude": Decimal("4.538200"),
                "longitude": Decimal("-75.675400"),
            },
            {
                "name": "Supermercado Super Inter Centenario",
                "establishment_type": Establishment.EstablishmentType.SUPERMARKET,
                "municipality": "Armenia",
                "neighborhood": "Centenario",
                "address": "Avenida Bolívar # 15N-30",
                "latitude": Decimal("4.552100"),
                "longitude": Decimal("-75.658900"),
            },
            {
                "name": "Tienda La Economía de Calarcá",
                "establishment_type": Establishment.EstablishmentType.NEIGHBORHOOD_SHOP,
                "municipality": "Calarcá",
                "neighborhood": "Centro",
                "address": "Carrera 25 # 38-15",
                "latitude": Decimal("4.529300"),
                "longitude": Decimal("-75.640700"),
            },
        ]

        establishments = {}
        for item in establishments_data:
            est, _ = Establishment.objects.update_or_create(
                name=item["name"],
                municipality=item["municipality"],
                defaults=item,
            )
            establishments[item["name"]] = est

        # Productos base y presentaciones distintas para demostrar normalización por unidad de medida (M-01)
        products_spec = [
            {
                "name": "Arroz Blanco de Primera",
                "category": ProductCategory.GROCERY.value,
                "aliases": "arroz, arroz blanco, arroz corriente, sipsa arroz",
                "description": "Arroz blanco de consumo masivo en distintas presentaciones (g y kg).",
                "presentations": [
                    ("Diana", "Libra 500 g", "7702001001015", Decimal(500), UnitOfMeasure.GRAM.value),
                    ("Roa", "Bolsa 1 kg", "7702001002029", Decimal(1), UnitOfMeasure.KILOGRAM.value),
                    ("Diana", "Arroba / Bulto Familiar 2.5 kg", "7702001003033", Decimal("2.5"), UnitOfMeasure.KILOGRAM.value),
                ],
            },
            {
                "name": "Leche Entera Pasteurizada",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "leche, leche entera, bolsa de leche, caja de leche",
                "description": "Leche líquida entera comparada por 100 ml entre bolsas y cajas.",
                "presentations": [
                    ("Colanta", "Bolsa 900 ml", "7702123001112", Decimal(900), UnitOfMeasure.MILLILITER.value),
                    ("Alquería", "Bolsa Mega 1.1 L", "7702123002225", Decimal("1.1"), UnitOfMeasure.LITER.value),
                ],
            },
            {
                "name": "Huevo Rojo Tipo AA",
                "category": ProductCategory.PERISHABLE.value,
                "aliases": "huevos, panal de huevos, cubeta de huevos, sipsa huevo",
                "description": "Huevo rojo AA normalizado por unidad (1 und).",
                "presentations": [
                    ("Avícola del Quindío", "Cubeta x 30 und", "7709988776655", Decimal(30), UnitOfMeasure.UNIT.value),
                    ("Santa Reyes", "Medio Panal x 15 und", "7709988776648", Decimal(15), UnitOfMeasure.UNIT.value),
                ],
            },
        ]

        presentations_map = {}
        for p_data in products_spec:
            product, _ = Product.objects.update_or_create(
                name=p_data["name"],
                defaults={
                    "category": p_data["category"],
                    "aliases": p_data["aliases"],
                    "description": p_data["description"],
                },
            )
            for brand, pres_name, ean, qty, unit in p_data["presentations"]:
                pres, _ = ProductPresentation.objects.update_or_create(
                    product=product,
                    brand=brand,
                    presentation_name=pres_name,
                    defaults={
                        "ean_barcode": ean,
                        "quantity": qty,
                        "unit": unit,
                    },
                )
                presentations_map[(p_data["name"], brand, pres_name)] = pres

        use_case = ReportPriceUseCase()

        seed_reports = [
            # Arroz: Tienda de barrio vs Supermercado y distintas presentaciones
            (
                ("Arroz Blanco de Primera", "Diana", "Libra 500 g"),
                "Tienda de Barrio Don Chucho",
                Decimal(2200),
                SourceType.PUBLIC_REFERENCE,
                False,
                "",
            ),
            (
                ("Arroz Blanco de Primera", "Roa", "Bolsa 1 kg"),
                "Minimercado Mercar Quindío",
                Decimal(4200),
                SourceType.COMMUNITY_FREQUENT,
                False,
                "",
            ),
            (
                ("Arroz Blanco de Primera", "Diana", "Arroba / Bulto Familiar 2.5 kg"),
                "Supermercado Super Inter Centenario",
                Decimal(11000),
                SourceType.OFFICIAL_MERCHANT,
                True,
                "Promoción Quincena: Lleve bulto 2.5 kg a precio especial",
            ),
            # Leche: comparación 900ml vs 1.1L
            (
                ("Leche Entera Pasteurizada", "Colanta", "Bolsa 900 ml"),
                "Granero y Tienda El Cafetal",
                Decimal(4050),
                SourceType.COMMUNITY_FREQUENT,
                False,
                "",
            ),
            (
                ("Leche Entera Pasteurizada", "Alquería", "Bolsa Mega 1.1 L"),
                "Supermercado Super Inter Centenario",
                Decimal(5280),
                SourceType.OFFICIAL_MERCHANT,
                True,
                "Precio oficial destacado de la semana",
            ),
            # Huevos: Cubeta x30 vs x15 (Referencia DANE SIPSA Armenia)
            (
                ("Huevo Rojo Tipo AA", "Avícola del Quindío", "Cubeta x 30 und"),
                "Granero y Tienda El Cafetal",
                Decimal(15600),
                SourceType.PUBLIC_REFERENCE,
                False,
                "",
            ),
            (
                ("Huevo Rojo Tipo AA", "Santa Reyes", "Medio Panal x 15 und"),
                "Supermercado Super Inter Centenario",
                Decimal(9000),
                SourceType.COMMUNITY_OCCASIONAL,
                False,
                "",
            ),
        ]

        for pres_key, est_name, price, src_type, is_promo, promo_desc in seed_reports:
            use_case.execute(
                presentation=presentations_map[pres_key],
                establishment=establishments[est_name],
                raw_price=price,
                reporter_token=f"seed-{est_name}",
                source_type=src_type,
                is_promotional=is_promo,
                promotion_description=promo_desc,
            )

        # Crear cuentas semilla de los 4 Actores de la Tabla 4.1 para pruebas inmediatas en Postman
        demo_accounts = [
            ("consumidor_armenia", "consumidor@pricecol.co", "Pricecol2026*", ActorRole.CONSUMER, None, 0),
            ("reportante_quindio", "reportante@pricecol.co", "Pricecol2026*", ActorRole.REPORTER, None, 6),
            (
                "comercio_don_chucho",
                "donchucho@pricecol.co",
                "Pricecol2026*",
                ActorRole.MERCHANT,
                establishments["Tienda de Barrio Don Chucho"],
                2,
            ),
            ("moderador_admin", "moderador@pricecol.co", "Pricecol2026*", ActorRole.MODERATOR, None, 0),
        ]

        for username, email, pwd, role, est_obj, ver_count in demo_accounts:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "is_staff": role == ActorRole.MODERATOR,
                },
            )
            if created:
                user.set_password(pwd)
                user.save()
            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    "role": role,
                    "managed_establishment": est_obj,
                    "verified_reports_count": ver_count,
                    "accepted_data_policy": True,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Datos iniciales de Armenia/Quindío y cuentas de los 4 Actores (Tabla 4.1) cargados exitosamente."
            )
        )

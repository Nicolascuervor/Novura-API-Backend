"""
Comando `python manage.py seed_minimarkets`:
Puebla la tabla de establecimientos comerciales con la lista de minimercados
y supermercados tradicionales/locales en Armenia, Quindío.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from catalog.models import Establishment


class Command(BaseCommand):
    help = "Puebla la base de datos con minimercados y supermercados locales de Armenia, Quindío."

    def handle(self, *args, **options) -> None:
        del args, options
        self.stdout.write("Poblando minimercados y comercios locales en Armenia, Quindío...")

        minimarkets_data = [
            {
                "name": "Autoservicio Surti Hogar",
                "establishment_type": Establishment.EstablishmentType.MINIMARKET,
                "municipality": "Armenia",
                "neighborhood": "El Bosque",
                "address": "Calle 21 # 24-77 Esquina",
                "latitude": Decimal("4.536500"),
                "longitude": Decimal("-75.679200"),
            },
            {
                "name": "Super Inter Avenida Centenario",
                "establishment_type": Establishment.EstablishmentType.SUPERMARKET,
                "municipality": "Armenia",
                "neighborhood": "Centenario",
                "address": "Avenida Centenario # 2-50",
                "latitude": Decimal("4.541200"),
                "longitude": Decimal("-75.663500"),
            },
            {
                "name": "Autoservicio Rindemax",
                "establishment_type": Establishment.EstablishmentType.MINIMARKET,
                "municipality": "Armenia",
                "neighborhood": "San José / Centro",
                "address": "Carrera 23 # 10-28",
                "latitude": Decimal("4.542800"),
                "longitude": Decimal("-75.674100"),
            },
            {
                "name": "Metromarket",
                "establishment_type": Establishment.EstablishmentType.MINIMARKET,
                "municipality": "Armenia",
                "neighborhood": "Norte / Profesionales",
                "address": "Carrera 19 # 26N-49 Local 2",
                "latitude": Decimal("4.558300"),
                "longitude": Decimal("-75.656800"),
            },
            {
                "name": "Supermercado Laureles",
                "establishment_type": Establishment.EstablishmentType.SUPERMARKET,
                "municipality": "Armenia",
                "neighborhood": "Laureles",
                "address": "Calle 22 Norte # 14-31",
                "latitude": Decimal("4.555200"),
                "longitude": Decimal("-75.658700"),
            },
            {
                "name": "Supermercado Multiahorro",
                "establishment_type": Establishment.EstablishmentType.MINIMARKET,
                "municipality": "Armenia",
                "neighborhood": "Centro",
                "address": "Calle 15 # 18-27",
                "latitude": Decimal("4.538900"),
                "longitude": Decimal("-75.671300"),
            },
            {
                "name": "El Cosechero de Armenia",
                "establishment_type": Establishment.EstablishmentType.MINIMARKET,
                "municipality": "Armenia",
                "neighborhood": "Plaza Minorista",
                "address": "Carrera 25 con Calle 20 Esquina",
                "latitude": Decimal("4.535800"),
                "longitude": Decimal("-75.681500"),
            },
            {
                "name": "Andi Su Mercado",
                "establishment_type": Establishment.EstablishmentType.MINIMARKET,
                "municipality": "Armenia",
                "neighborhood": "Mercar",
                "address": "Vía Montenegro Km 1, Bodega 1, Local 6 (Mercar S.A.)",
                "latitude": Decimal("4.529800"),
                "longitude": Decimal("-75.698500"),
            },
            {
                "name": "Ventanilla Verde Supermercado",
                "establishment_type": Establishment.EstablishmentType.MINIMARKET,
                "municipality": "Armenia",
                "neighborhood": "Centro / San Fernando",
                "address": "Calle 23 # 16-21",
                "latitude": Decimal("4.534200"),
                "longitude": Decimal("-75.673900"),
            },
            {
                "name": "Tienda Limonar",
                "establishment_type": Establishment.EstablishmentType.NEIGHBORHOOD_SHOP,
                "municipality": "Armenia",
                "neighborhood": "El Limonar",
                "address": "Calle 5 # 24A-81",
                "latitude": Decimal("4.547100"),
                "longitude": Decimal("-75.676300"),
            },
        ]

        created_count = 0
        updated_count = 0

        for item in minimarkets_data:
            est, created = Establishment.objects.update_or_create(
                name=item["name"],
                municipality=item["municipality"],
                defaults=item,
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f" [+] Creado: {est.name} (ID: {est.id})"))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f" [*] Actualizado: {est.name} (ID: {est.id})"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Proceso finalizado con éxito: {created_count} creados, {updated_count} actualizados."
            )
        )

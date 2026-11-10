"""
Comando `python manage.py seed_establishments`:
Puebla la tabla de establecimientos comerciales con las 5 marcas solicitadas
en ubicaciones estratégicas de Armenia, Quindío.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from catalog.models import Establishment


class Command(BaseCommand):
    help = "Puebla la base de datos con los 5 establecimientos principales (Ara, D1, Dollarcity, Carulla, Olímpica) en Armenia/Quindío."

    def handle(self, *args, **options) -> None:
        del args, options
        self.stdout.write("Poblando establecimientos en Armenia, Quindío...")

        establishments_data = [
            {
                "name": "Tiendas Ara",
                "establishment_type": Establishment.EstablishmentType.SUPERMARKET,
                "municipality": "Armenia",
                "neighborhood": "Centro",
                "address": "Carrera 16 # 20-35",
                "latitude": Decimal("4.536100"),
                "longitude": Decimal("-75.672800"),
            },
            {
                "name": "Tiendas D1",
                "establishment_type": Establishment.EstablishmentType.SUPERMARKET,
                "municipality": "Armenia",
                "neighborhood": "Laureles",
                "address": "Avenida Bolívar # 14N-15",
                "latitude": Decimal("4.549200"),
                "longitude": Decimal("-75.660800"),
            },
            {
                "name": "Dollarcity",
                "establishment_type": Establishment.EstablishmentType.SUPERMARKET,
                "municipality": "Armenia",
                "neighborhood": "Centro Comercial Portal del Quindío",
                "address": "Avenida Bolívar # 19N-46, Local 201",
                "latitude": Decimal("4.557400"),
                "longitude": Decimal("-75.655200"),
            },
            {
                "name": "Carulla",
                "establishment_type": Establishment.EstablishmentType.SUPERMARKET,
                "municipality": "Armenia",
                "neighborhood": "Norte / Castellana",
                "address": "Carrera 14 # 9N-50",
                "latitude": Decimal("4.546300"),
                "longitude": Decimal("-75.662900"),
            },
            {
                "name": "Olímpica",
                "establishment_type": Establishment.EstablishmentType.SUPERMARKET,
                "municipality": "Armenia",
                "neighborhood": "Plaza Minorista / Providencia",
                "address": "Carrera 19 # 26-10",
                "latitude": Decimal("4.531800"),
                "longitude": Decimal("-75.679500"),
            },
        ]

        created_count = 0
        updated_count = 0

        for item in establishments_data:
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

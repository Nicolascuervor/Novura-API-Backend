"""
Comando de Django para simular y probar la vigencia de precios en el Frontend:
Genera o actualiza reportes con fechas pasadas (ej. 6 días = ADVERTENCIA, 8 días = EXPIRADO/EXCLUIDO).

Uso:
  python manage.py test_price_staleness --days 6    # Genera advertencia amarilla (STALE_WARNING)
  python manage.py test_price_staleness --days 8    # Excluye el reporte del ranking (EXPIRED)
  python manage.py test_price_staleness --reset     # Restaura todos los precios a vigentes de hoy
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import Establishment, Product, ProductPresentation
from core_domain.entities import ReliabilityStatus
from pricing.models import PriceReport
from pricing.services import invalidate_product_comparison_cache


class Command(BaseCommand):
    help = "Modifica la fecha de reportes de un producto para probar estados de vigencia (STALE_WARNING o EXPIRED) en el frontend."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=6,
            help="Antigüedad en días que se le asignará al reporte (ej. 6 para advertencia, 8 para expirado en perecederos).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Restaura la fecha de los reportes para que vuelvan a estar 100% vigentes (hoy).",
        )
        parser.add_argument(
            "--product-name",
            type=str,
            default="",
            help="Nombre o fragmento del producto a modificar (por defecto toma el primer perecedero).",
        )

    def handle(self, *args, **options):
        reset = options["reset"]
        days = options["days"]
        product_query = options["product_name"]

        # 1. Buscar el producto
        if product_query:
            product = Product.objects.filter(name__icontains=product_query).first()
        else:
            product = Product.objects.filter(category="PERISHABLE").first() or Product.objects.first()

        if not product:
            self.stdout.write(self.style.ERROR("[-] No se encontró ningún producto en el catálogo."))
            return

        presentations = ProductPresentation.objects.filter(product=product)
        reports = PriceReport.objects.filter(presentation__in=presentations)

        if not reports.exists():
            # Crear un reporte base si no existía ninguno
            presentation = presentations.first()
            establishment = Establishment.objects.first()
            if not presentation or not establishment:
                self.stdout.write(self.style.ERROR("[-] Se requiere al menos una presentación y un establecimiento."))
                return

            report = PriceReport.objects.create(
                presentation=presentation,
                establishment=establishment,
                raw_price=Decimal("4500.00"),
                normalized_ref_price=Decimal("450.00"),
                price_per_base_unit=Decimal("4.5000"),
                reference_unit_label="100g",
                reliability_status=ReliabilityStatus.VERIFIED.value,
                reporter_hash="test_simulated_reporter_hash",
            )
            reports = PriceReport.objects.filter(pk=report.pk)

        # 2. Aplicar la modificación de fecha
        target_date = timezone.now() if reset else (timezone.now() - timedelta(days=days))

        # Usamos .update() para modificar directamente la columna DB sin disparar auto_now_add
        count = reports.update(reported_at=target_date)

        # 3. Limpiar la caché de Redis y proxy para que el frontend vea el cambio al instante
        invalidate_product_comparison_cache(product.id)

        self.stdout.write(self.style.SUCCESS("=" * 65))
        self.stdout.write(self.style.SUCCESS("  SIMULACION DE VIGENCIA PARA FRONTEND"))
        self.stdout.write(self.style.SUCCESS("=" * 65))
        self.stdout.write(f" Producto:      {product.name} (Categoría: {product.category})")
        self.stdout.write(f" ID Producto:   {product.id}")
        self.stdout.write(f" Reportes mod.: {count}")
        self.stdout.write(f" Nueva fecha:   {target_date.strftime('%Y-%m-%d %H:%M:%S')}")

        if reset:
            self.stdout.write(self.style.SUCCESS("\n[OK] Precios restaurados a FECHA ACTUAL (Vigentes - VALID)."))
        else:
            self.stdout.write(f" Antigüedad:    {days} días ({days * 24} horas)")
            if product.category == "PERISHABLE":
                if days < 5:
                    status_desc = "VIGENTE (VALID) -> Se ve normal en el ranking."
                elif days <= 7:
                    status_desc = "ADVERTENCIA (STALE_WARNING) -> Se ve con aviso amarillo en el frontend."
                else:
                    status_desc = "EXPIRADO (EXPIRED) -> EXCLUIDO: No debe aparecer en el ranking del frontend."
            else:
                if days < 10:
                    status_desc = "VIGENTE (VALID) -> Se ve normal en el ranking."
                elif days <= 15:
                    status_desc = "ADVERTENCIA (STALE_WARNING) -> Se ve con aviso amarillo en el frontend."
                else:
                    status_desc = "EXPIRADO (EXPIRED) -> EXCLUIDO: No debe aparecer en el ranking del frontend."

            self.stdout.write(self.style.WARNING(f"\n[ESTADO ESPERADO EN FRONTEND]: {status_desc}"))

        self.stdout.write(self.style.SUCCESS("\n Endpoint de comparación para verificar en el navegador:"))
        self.stdout.write(f" -> http://localhost:8000/api/v1/products/{product.id}/compare/\n")

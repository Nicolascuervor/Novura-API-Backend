"""
Comando `python manage.py refresh_price_dates`:
Actualiza las fechas (`reported_at`) de todos los reportes de precios (`PriceReport`)
en la base de datos para que vuelvan a estar 100 % vigentes (`VALID` / "Reciente") hoy,
respetando las ventanas de alta volatilidad (<= 48h para Frutas/Verduras y Perecederos)
y baja volatilidad (<= 168h para Abarrotes, Bebidas, Aseo y Limpieza).

Además:
- Si existen múltiples reportes históricos para un mismo `(presentation, establishment)`,
  mantiene el más reciente dentro de las últimas 1 a 18 horas (100 % vigente hoy) y
  escalona los anteriores dentro de los últimos 15 a 75 días para que la gráfica de
  Historial y Tendencia de 90 días (Opción A2 / EC-08) conserve su curva temporal.
- Invalida automáticamente las claves de versión en Redis y caché HTTP (`ETag`) para que
  el Frontend muestre los precios confiables de inmediato al recargar la página.

Uso en local o en el servidor desplegado:
    python manage.py refresh_price_dates
"""

from collections import defaultdict
from datetime import timedelta

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from catalog.models import Product
from pricecol_api_backend.http_cache import bump_catalog_cache_version
from pricing.models import PriceReport
from pricing.services import invalidate_product_comparison_cache


class Command(BaseCommand):
    help = (
        "Actualiza las fechas (reported_at) de todos los precios reportados para que "
        "estén 100 % vigentes hoy en el comparador y catálogo del Frontend."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--max-age-hours",
            type=int,
            default=18,
            help=(
                "Antigüedad máxima en horas para el reporte vigente más reciente de cada "
                "producto/tienda (por defecto 18h, garantizando estado VALID en todas las categorías)."
            ),
        )

    def handle(self, *args, **options) -> None:
        del args
        max_age_hours = max(1, min(int(options["max_age_hours"]), 36))
        now = timezone.now()

        all_reports = list(
            PriceReport.objects.select_related("presentation", "presentation__product", "establishment")
            .order_by("-reported_at", "-id")
        )

        if not all_reports:
            self.stdout.write(
                self.style.WARNING(
                    "No hay reportes de precios en la base de datos. "
                    "Ejecuta primero: python manage.py seed_simulated_market_data"
                )
            )
            return

        grouped_reports: dict[tuple[int, int], list[PriceReport]] = defaultdict(list)
        for rep in all_reports:
            grouped_reports[(rep.presentation_id, rep.establishment_id)].append(rep)

        updated_current_count = 0
        updated_historical_count = 0

        with transaction.atomic():
            for pair_idx, ((_pres_id, _est_id), reports_for_pair) in enumerate(grouped_reports.items()):
                # 1. El reporte más reciente del par (índice 0) queda dentro de las últimas 1..max_age_hours horas
                latest_report = reports_for_pair[0]
                hours_ago = 1 + ((pair_idx * 3) % max_age_hours)
                minutes_ago = (pair_idx * 7) % 55
                fresh_timestamp = now - timedelta(hours=hours_ago, minutes=minutes_ago)

                PriceReport.objects.filter(pk=latest_report.pk).update(reported_at=fresh_timestamp)
                updated_current_count += 1

                # 2. Si hay reportes anteriores para esa misma presentación y tienda (historial de 90 días),
                #    escalonarlos hacia atrás entre 10 y 80 días para nutrir la gráfica A2 sin pisar el actual.
                for hist_idx, older_report in enumerate(reports_for_pair[1:], start=1):
                    days_back = min(85, hist_idx * 14 + (pair_idx % 6))
                    historical_timestamp = now - timedelta(days=days_back, hours=hours_ago)
                    PriceReport.objects.filter(pk=older_report.pk).update(reported_at=historical_timestamp)
                    updated_historical_count += 1

        # 3. Invalidar toda la caché de comparación, historial y catálogo en Redis / memoria
        active_product_ids = list(Product.objects.filter(is_active=True).values_list("id", flat=True))
        for pid in active_product_ids:
            invalidate_product_comparison_cache(pid)
        bump_catalog_cache_version()
        cache.delete("pricecol:moderation:dashboard_summary")

        self.stdout.write(self.style.SUCCESS("=" * 68))
        self.stdout.write(self.style.SUCCESS("  ACTUALIZACIÓN DE VIGENCIA DE PRECIOS COMPLETADA (EC-02 / ADR-04)"))
        self.stdout.write(self.style.SUCCESS("=" * 68))
        self.stdout.write(f" Fecha/hora base (ahora):          {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        self.stdout.write(f" Precios vigentes actualizados:    {updated_current_count} (entre 1h y {max_age_hours}h atrás -> 100% VALID)")
        self.stdout.write(f" Puntos históricos (90 días A2):   {updated_historical_count} (escalonados entre 10 y 85 días atrás)")
        self.stdout.write(f" Productos con caché invalidada:   {len(active_product_ids)}")
        self.stdout.write(self.style.SUCCESS("\n[OK] Todos los productos con reportes aparecen ahora como 'Reciente / Confiable' en el Frontend."))

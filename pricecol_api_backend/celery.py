"""
Configuración central de Celery para Pricecol API Backend.
Gestiona el procesamiento asíncrono de:
1. Pre-calentamiento proactivo del caché de comparación neutral (`pricing.prewarm_product_comparison_cache_task`).
2. Registro desacoplado de eventos en la bitácora de auditoría (`accounts.record_audit_event_task`).
3. Barrido periódico de vigencia de precios por categoría (`pricing.evaluate_catalog_price_validity_task` - EC-02).
"""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pricecol_api_backend.settings")

app = Celery("pricecol_api_backend")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "evaluate-catalog-price-validity-every-6-hours": {
        "task": "pricing.evaluate_catalog_price_validity_task",
        "schedule": crontab(minute=0, hour="*/6"),
    },
}

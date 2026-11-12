"""
Tareas asíncronas de Celery para el módulo `pricing` (`django-response-time-enforcer` + ATAM EC-02/EC-04):
1. `prewarm_product_comparison_cache_task`: Pre-calienta los 3 rankings de comparación de un producto en Redis
   inmediatamente después de un `transaction.on_commit()` para lograr Cache Hit < 5ms.
2. `evaluate_catalog_price_validity_task`: Tarea periódica (Celery Beat) que audita la vigencia de los precios
   por categoría (Perecederos 7d / Abarrotes 30d - EC-02), refresca cachés y deja trazabilidad en `AuditEventLog`.
"""

from typing import Any

from celery import shared_task
from django.db import transaction

from accounts.models import AuditEventLog
from accounts.services import record_audit_event
from catalog.models import Product
from core_domain.entities import ValidityStatus
from core_domain.neutral_comparator import SortCriterion
from pricing.services import CommunityPriceSourceAdapter, ComparePricesQueryService


@shared_task(name="pricing.prewarm_product_comparison_cache_task")
def prewarm_product_comparison_cache_task(product_id: int) -> dict[str, Any]:
    """
    Pre-calcula y almacena en caché (Redis / Django Cache) los 3 criterios de ordenamiento
    (`UNIT_PRICE_ASC`, `RAW_PRICE_ASC`, `FRESHNESS_DESC`) para un producto tras recibir un nuevo reporte
    o una decisión de moderación.
    """
    query_service = ComparePricesQueryService()
    warmed_criteria: list[str] = []

    for criterion in SortCriterion:
        query_service.compare_product(
            product_id=product_id,
            criterion=criterion,
            municipality=None,
            include_low_confidence=True,
        )
        warmed_criteria.append(criterion.value)

    return {
        "product_id": product_id,
        "warmed_criteria_count": len(warmed_criteria),
        "criteria": warmed_criteria,
    }


def schedule_prewarm_product_comparison_cache(product_id: int) -> None:
    """
    Despacha `prewarm_product_comparison_cache_task` de forma segura al confirmar la transacción SQL
    (`transaction.on_commit()`), con degradación elegante si el broker Redis no está levantado localmente.
    """

    def _enqueue() -> None:
        from kombu.exceptions import OperationalError

        try:
            prewarm_product_comparison_cache_task.delay(product_id)
        except (OperationalError, OSError):
            prewarm_product_comparison_cache_task(product_id)

    transaction.on_commit(_enqueue)


@shared_task(name="pricing.evaluate_catalog_price_validity_task")
def evaluate_catalog_price_validity_task() -> dict[str, int]:
    """
    Barrido periódico de vigencia (`EC-02`):
    Evalúa todos los productos activos, contabiliza reportes vigentes, próximos a vencer y vencidos,
    pre-calienta las cachés de los productos con reportes y registra un evento en `AuditEventLog`.
    """
    adapter = CommunityPriceSourceAdapter()
    active_products = list(Product.objects.filter(is_active=True).only("id", "name", "category"))

    evaluated_products = 0
    valid_reports = 0
    expiring_soon_reports = 0
    expired_reports = 0

    for product in active_products:
        entries = adapter.fetch_entries_for_product(product.id)
        evaluated_products += 1
        if not entries:
            continue

        for entry in entries:
            if entry.validity_status == ValidityStatus.VALID:
                valid_reports += 1
            elif entry.validity_status == ValidityStatus.EXPIRING_SOON:
                expiring_soon_reports += 1
            elif entry.validity_status == ValidityStatus.EXPIRED:
                expired_reports += 1

        prewarm_product_comparison_cache_task(product.id)

    summary_payload = {
        "evaluated_products": evaluated_products,
        "valid_reports": valid_reports,
        "expiring_soon_reports": expiring_soon_reports,
        "expired_reports": expired_reports,
    }

    record_audit_event(
        actor_user=None,
        module=AuditEventLog.AuditModule.MODERATION,
        action_type="VALIDITY_SWEEP_COMPLETED",
        target_model="Product",
        target_id="ALL",
        target_repr="Catálogo General de Productos",
        summary=(
            f"Barrido periódico de vigencia EC-02 completado sobre {evaluated_products} productos "
            f"({valid_reports} vigentes, {expiring_soon_reports} por vencer, {expired_reports} vencidos)."
        ),
        severity=(
            AuditEventLog.AuditSeverity.WARNING
            if expired_reports > 0
            else AuditEventLog.AuditSeverity.INFO
        ),
        new_state=summary_payload,
    )
    return summary_payload

"""
Tareas asíncronas de Celery para el módulo `accounts` (Trazabilidad y Auditoría Inmutable).
"""

from typing import Any

from celery import shared_task
from django.core.cache import cache

from accounts.models import AuditEventLog

MODERATION_DASHBOARD_SUMMARY_CACHE_KEY = "pricecol:moderation:dashboard_summary"


@shared_task(name="accounts.record_audit_event_task")
def record_audit_event_task(
    *,
    actor_user_id: int | None,
    actor_username: str,
    actor_role: str,
    module: str,
    action_type: str,
    severity: str,
    target_model: str,
    target_id: str,
    target_repr: str,
    summary: str,
    previous_state: dict[str, Any] | None = None,
    new_state: dict[str, Any] | None = None,
    ip_hash: str = "",
) -> int:
    """
    Persiste un registro en `AuditEventLog` e invalida el caché del resumen de moderación.
    """
    log_entry = AuditEventLog.objects.create(
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        actor_role=actor_role,
        module=module,
        action_type=action_type,
        severity=severity,
        target_model=target_model,
        target_id=str(target_id),
        target_repr=target_repr,
        summary=summary,
        previous_state=previous_state or {},
        new_state=new_state or {},
        ip_hash=ip_hash,
    )
    cache.delete(MODERATION_DASHBOARD_SUMMARY_CACHE_KEY)
    return log_entry.id

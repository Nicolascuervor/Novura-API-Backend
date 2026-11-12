"""
Inicialización del paquete `pricecol_api_backend`.
Expone `celery_app` para que las tareas `@shared_task` se vinculen automáticamente al iniciar Django.
"""

from pricecol_api_backend.celery import app as celery_app

__all__ = ("celery_app",)

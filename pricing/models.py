"""
Modelos de Persistencia de Precios Colaborativos (Núcleo - Corte 2).
Diseñado bajo Privacidad por Diseño (Ley 1581 de 2012 y Medida M-06 = 1.00):
- NUNCA almacena ni expone coordenadas GPS personales del reportante.
- Almacena un hash pseudonimizado (`reporter_hash`) únicamente para control antifraude de ráfagas (EC-03)
  y trazabilidad interna de moderación sin exponer identidad pública.
"""

from django.db import models

from catalog.models import Establishment, ProductPresentation
from core_domain.entities import ReliabilityStatus, SourceType


class PriceReport(models.Model):
    """Registro de precio reportado para una presentación en un establecimiento."""

    presentation = models.ForeignKey(
        ProductPresentation,
        on_delete=models.CASCADE,
        related_name="price_reports",
    )
    establishment = models.ForeignKey(
        Establishment,
        on_delete=models.CASCADE,
        related_name="price_reports",
    )
    raw_price = models.DecimalField(max_digits=12, decimal_places=2, db_index=True)

    # Pre-cálculo de normalización al escribir para optimizar lecturas concurrentes (EC-04: 500 usuarios)
    normalized_ref_price = models.DecimalField(max_digits=12, decimal_places=2, db_index=True)
    price_per_base_unit = models.DecimalField(max_digits=12, decimal_places=4)
    reference_unit_label = models.CharField(max_length=16, default="100g")

    source_type = models.CharField(
        max_length=32,
        choices=[(s.value, s.value) for s in SourceType],
        default=SourceType.COMMUNITY_OCCASIONAL.value,
        db_index=True,
    )
    reliability_status = models.CharField(
        max_length=24,
        choices=[(r.value, r.value) for r in ReliabilityStatus],
        default=ReliabilityStatus.VERIFIED.value,
        db_index=True,
    )
    confidence_score = models.DecimalField(max_digits=4, decimal_places=2, default=0.85)
    anomaly_notes = models.TextField(blank=True)

    # Campos listos para el puerto de extensión del Módulo Comercial sin romper esquema (EC-05 / M-09)
    is_promotional = models.BooleanField(default=False, db_index=True)
    promotion_description = models.CharField(max_length=200, blank=True)

    # Privacidad por Diseño (M-06 / Ley 1581): hash irreversible SHA-256 (sin PII ni GPS del reportante)
    reporter_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Hash pseudonimizado irreversible para control de ráfagas antifraude (Ley 1581).",
    )
    reported_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-reported_at"]
        indexes = [
            models.Index(fields=["presentation", "establishment", "-reported_at"]),
            models.Index(fields=["presentation", "reliability_status", "-reported_at"]),
            models.Index(fields=["reporter_hash", "-reported_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.presentation} @ {self.establishment.name}: "
            f"${self.raw_price} (${self.normalized_ref_price}/{self.reference_unit_label})"
        )

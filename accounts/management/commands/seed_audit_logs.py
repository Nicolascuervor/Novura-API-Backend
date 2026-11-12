"""
Comando de administración para poblar eventos iniciales de auditoría (`AuditEventLog`)
basados en los usuarios, establecimientos, productos, presentaciones y reportes de precios
existentes en la base de datos, para que la Vista de Auditoría del Moderador tenga
trazabilidad histórica completa desde el primer inicio.

Ejecución:
    python manage.py seed_audit_logs
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import ActorRole, AuditEventLog, UserProfile
from accounts.services import record_audit_event
from catalog.models import Establishment, Product
from pricing.models import PriceReport

User = get_user_model()


class Command(BaseCommand):
    help = "Genera registros históricos iniciales en AuditEventLog a partir de las entidades activas en la DB."

    @transaction.atomic
    def handle(self, *args, **options):
        del args, options
        if AuditEventLog.objects.count() >= 30:
            self.stdout.write(
                self.style.SUCCESS(
                    f"AuditEventLog ya cuenta con {AuditEventLog.objects.count()} eventos registrados. No se requiere duplicar."
                )
            )
            return

        now = timezone.now()
        moderator_profile = UserProfile.objects.filter(role=ActorRole.MODERATOR).select_related("user").first()
        moderator_user = moderator_profile.user if moderator_profile else None

        created_events = 0

        # 1. Eventos de registro y verificación de cuentas (AUTH y MODERATION)
        profiles = list(UserProfile.objects.select_related("user", "managed_establishment").order_by("id"))
        for idx, prof in enumerate(profiles):
            ev_reg = record_audit_event(
                actor_user=prof.user,
                module=AuditEventLog.AuditModule.AUTH,
                action_type="USER_REGISTERED",
                target_model="UserProfile",
                target_id=prof.id,
                target_repr=f"{prof.user.username} ({prof.role})",
                summary=f"Registro de cuenta '{prof.user.username}' con rol {prof.role}.",
                severity=AuditEventLog.AuditSeverity.INFO,
                new_state={
                    "user_id": prof.user_id,
                    "username": prof.user.username,
                    "role": prof.role,
                },
            )
            AuditEventLog.objects.filter(pk=ev_reg.pk).update(
                created_at=now - timedelta(days=5, hours=idx % 12, minutes=(idx * 7) % 59)
            )
            created_events += 1

            if prof.role == ActorRole.MERCHANT and prof.is_verified and moderator_user:
                ev_ver = record_audit_event(
                    actor_user=moderator_user,
                    module=AuditEventLog.AuditModule.MODERATION,
                    action_type="MERCHANT_VERIFICATION_CHANGED",
                    target_model="UserProfile",
                    target_id=prof.id,
                    target_repr=prof.user.username,
                    summary=f"Moderador verificó oficialmente al comercio '{prof.user.username}' ({prof.business_legal_name or 'Marca Confirmada'}).",
                    severity=AuditEventLog.AuditSeverity.INFO,
                    previous_state={"verification_status": "PENDING"},
                    new_state={
                        "verification_status": "VERIFIED",
                        "business_legal_name": prof.business_legal_name,
                        "business_tax_id": prof.business_tax_id,
                    },
                )
                AuditEventLog.objects.filter(pk=ev_ver.pk).update(
                    created_at=now - timedelta(days=4, hours=idx % 10, minutes=(idx * 11) % 59)
                )
                created_events += 1

        # 2. Eventos de establecimientos y medios de pago (ESTABLISHMENT)
        establishments = list(
            Establishment.objects.filter(is_active=True)
            .select_related("owner")
            .prefetch_related("payment_methods")
            .order_by("id")
        )
        for idx, est in enumerate(establishments):
            actor = est.owner or moderator_user
            pm_codes = list(est.payment_methods.filter(is_active=True).values_list("code", flat=True))
            ev_est = record_audit_event(
                actor_user=actor,
                module=AuditEventLog.AuditModule.ESTABLISHMENT,
                action_type="ESTABLISHMENT_CREATED",
                target_model="Establishment",
                target_id=est.id,
                target_repr=est.name,
                summary=f"Registro y vinculación del establecimiento '{est.name}' en {est.municipality} con {len(pm_codes)} medios de pago.",
                severity=AuditEventLog.AuditSeverity.INFO,
                new_state={
                    "id": est.id,
                    "name": est.name,
                    "establishment_type": est.establishment_type,
                    "municipality": est.municipality,
                    "owner_id": est.owner_id,
                    "payment_method_codes": pm_codes,
                },
            )
            AuditEventLog.objects.filter(pk=ev_est.pk).update(
                created_at=now - timedelta(days=3, hours=idx % 12, minutes=(idx * 5) % 59)
            )
            created_events += 1

        # 3. Eventos de productos del catálogo (CATALOG)
        products = list(Product.objects.filter(is_active=True).order_by("id")[:15])
        for idx, prod in enumerate(products):
            ev_prod = record_audit_event(
                actor_user=moderator_user,
                module=AuditEventLog.AuditModule.CATALOG,
                action_type="PRODUCT_CREATED",
                target_model="Product",
                target_id=prod.id,
                target_repr=prod.name,
                summary=f"Creación del producto molde '{prod.name}' en la categoría {prod.category}.",
                severity=AuditEventLog.AuditSeverity.INFO,
                new_state={"id": prod.id, "name": prod.name, "category": prod.category},
            )
            AuditEventLog.objects.filter(pk=ev_prod.pk).update(
                created_at=now - timedelta(days=2, hours=idx % 12, minutes=(idx * 9) % 59)
            )
            created_events += 1

        # 4. Eventos de reportes de precios verificados y alertas de variación (PRICING)
        recent_reports = list(
            PriceReport.objects.select_related("presentation", "presentation__product", "establishment")
            .order_by("-reported_at")[:35]
        )
        for rep in recent_reports:
            is_flagged = rep.reliability_status in ("LOW_CONFIDENCE", "ANOMALOUS")
            actor = rep.establishment.owner if rep.source_type == "OFFICIAL_MERCHANT" else None
            ev_rep = record_audit_event(
                actor_user=actor,
                module=AuditEventLog.AuditModule.PRICING,
                action_type="PRICE_REPORT_CREATED",
                target_model="PriceReport",
                target_id=rep.id,
                target_repr=f"{rep.presentation} @ {rep.establishment.name}",
                summary=(
                    f"Reporte #{rep.id} (${rep.raw_price} COP -> ${rep.normalized_ref_price}/{rep.reference_unit_label}) "
                    f"en '{rep.establishment.name}' clasificado como {rep.reliability_status}."
                ),
                severity=(
                    AuditEventLog.AuditSeverity.WARNING
                    if is_flagged
                    else AuditEventLog.AuditSeverity.INFO
                ),
                new_state={
                    "report_id": rep.id,
                    "raw_price": str(rep.raw_price),
                    "normalized_ref_price": str(rep.normalized_ref_price),
                    "reference_unit_label": rep.reference_unit_label,
                    "reliability_status": rep.reliability_status,
                    "source_type": rep.source_type,
                },
            )
            AuditEventLog.objects.filter(pk=ev_rep.pk).update(created_at=rep.reported_at)
            created_events += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Bitácora de auditoría poblada exitosamente: {created_events} eventos creados "
                f"(Total en AuditEventLog: {AuditEventLog.objects.count()})."
            )
        )

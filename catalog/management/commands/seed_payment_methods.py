"""
Comando de administración para poblar el catálogo oficial de medios de pago (`PaymentMethod`)
y asignar medios de pago realistas a los establecimientos existentes en Armenia y Quindío.

Ejecución:
    python manage.py seed_payment_methods
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Establishment, PaymentMethod

PAYMENT_METHODS_CATALOG = [
    {
        "code": "cash",
        "name": "Efectivo",
        "category": PaymentMethod.PaymentCategory.CASH,
        "display_order": 1,
    },
    {
        "code": "nequi",
        "name": "Nequi",
        "category": PaymentMethod.PaymentCategory.DIGITAL_WALLET,
        "display_order": 2,
    },
    {
        "code": "daviplata",
        "name": "Daviplata",
        "category": PaymentMethod.PaymentCategory.DIGITAL_WALLET,
        "display_order": 3,
    },
    {
        "code": "bre_b",
        "name": "Bre-B",
        "category": PaymentMethod.PaymentCategory.DIGITAL_WALLET,
        "display_order": 4,
    },
    {
        "code": "qr_bancolombia",
        "name": "QR Bancolombia",
        "category": PaymentMethod.PaymentCategory.DIGITAL_WALLET,
        "display_order": 5,
    },
    {
        "code": "visa",
        "name": "Visa",
        "category": PaymentMethod.PaymentCategory.CARD,
        "display_order": 6,
    },
    {
        "code": "mastercard",
        "name": "Mastercard",
        "category": PaymentMethod.PaymentCategory.CARD,
        "display_order": 7,
    },
    {
        "code": "sistecredito",
        "name": "Sistecrédito",
        "category": PaymentMethod.PaymentCategory.CREDIT,
        "display_order": 8,
    },
    {
        "code": "addi",
        "name": "Addi",
        "category": PaymentMethod.PaymentCategory.CREDIT,
        "display_order": 9,
    },
    {
        "code": "apple_pay",
        "name": "Apple Pay",
        "category": PaymentMethod.PaymentCategory.DIGITAL_WALLET,
        "display_order": 10,
    },
    {
        "code": "google_wallet",
        "name": "Google Wallet",
        "category": PaymentMethod.PaymentCategory.DIGITAL_WALLET,
        "display_order": 11,
    },
    {
        "code": "transfiya",
        "name": "Transfiya",
        "category": PaymentMethod.PaymentCategory.DIGITAL_WALLET,
        "display_order": 12,
    },
    {
        "code": "amex",
        "name": "American Express (Amex)",
        "category": PaymentMethod.PaymentCategory.CARD,
        "display_order": 13,
    },
    {
        "code": "diners_club",
        "name": "Diners Club",
        "category": PaymentMethod.PaymentCategory.CARD,
        "display_order": 14,
    },
    {
        "code": "pluxee",
        "name": "Pluxee (Sodexo)",
        "category": PaymentMethod.PaymentCategory.VOUCHER,
        "display_order": 15,
    },
    {
        "code": "edenred",
        "name": "Edenred",
        "category": PaymentMethod.PaymentCategory.VOUCHER,
        "display_order": 16,
    },
    {
        "code": "compensation_card",
        "name": "Tarjetas de Cajas de Compensación (ej. Comfenalco)",
        "category": PaymentMethod.PaymentCategory.VOUCHER,
        "display_order": 17,
    },
]

# Asignación realista por cadena o tipo de establecimiento
SUPERMARKET_BRAND_PAYMENT_CODES = {
    "ara": [
        "cash",
        "nequi",
        "daviplata",
        "bre_b",
        "qr_bancolombia",
        "visa",
        "mastercard",
        "apple_pay",
        "google_wallet",
        "pluxee",
        "edenred",
        "compensation_card",
    ],
    "d1": [
        "cash",
        "nequi",
        "daviplata",
        "bre_b",
        "visa",
        "mastercard",
        "apple_pay",
        "google_wallet",
        "pluxee",
        "edenred",
        "compensation_card",
    ],
    "dollarcity": [
        "cash",
        "visa",
        "mastercard",
        "amex",
        "diners_club",
        "apple_pay",
        "google_wallet",
    ],
    "carulla": [
        "cash",
        "nequi",
        "daviplata",
        "bre_b",
        "qr_bancolombia",
        "visa",
        "mastercard",
        "amex",
        "diners_club",
        "apple_pay",
        "google_wallet",
        "sistecredito",
        "addi",
        "pluxee",
        "edenred",
        "compensation_card",
    ],
    "olímpica": [
        "cash",
        "nequi",
        "daviplata",
        "bre_b",
        "qr_bancolombia",
        "visa",
        "mastercard",
        "amex",
        "diners_club",
        "apple_pay",
        "google_wallet",
        "sistecredito",
        "addi",
        "pluxee",
        "edenred",
        "compensation_card",
    ],
    "olimpica": [
        "cash",
        "nequi",
        "daviplata",
        "bre_b",
        "qr_bancolombia",
        "visa",
        "mastercard",
        "amex",
        "diners_club",
        "apple_pay",
        "google_wallet",
        "sistecredito",
        "addi",
        "pluxee",
        "edenred",
        "compensation_card",
    ],
    "super inter": [
        "cash",
        "nequi",
        "daviplata",
        "bre_b",
        "qr_bancolombia",
        "visa",
        "mastercard",
        "amex",
        "pluxee",
        "edenred",
        "compensation_card",
    ],
}

DEFAULT_SUPERMARKET_CODES = [
    "cash",
    "nequi",
    "daviplata",
    "bre_b",
    "qr_bancolombia",
    "visa",
    "mastercard",
    "transfiya",
    "compensation_card",
]

DEFAULT_MINIMARKET_CODES = [
    "cash",
    "nequi",
    "daviplata",
    "bre_b",
    "qr_bancolombia",
    "transfiya",
    "visa",
    "mastercard",
]

DEFAULT_NEIGHBORHOOD_SHOP_CODES = [
    "cash",
    "nequi",
    "daviplata",
    "bre_b",
    "qr_bancolombia",
    "transfiya",
]


class Command(BaseCommand):
    help = "Puebla los 17 medios de pago oficiales y los vincula a los establecimientos existentes."

    @transaction.atomic
    def handle(self, *args, **options):
        del args, options
        method_map: dict[str, PaymentMethod] = {}
        created_count = 0
        updated_count = 0

        for item in PAYMENT_METHODS_CATALOG:
            pm, created = PaymentMethod.objects.update_or_create(
                code=item["code"],
                defaults={
                    "name": item["name"],
                    "category": item["category"],
                    "display_order": item["display_order"],
                    "is_active": True,
                },
            )
            method_map[pm.code] = pm
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Catálogo de medios de pago sincronizado: {created_count} creados, {updated_count} actualizados (Total: {len(method_map)})."
            )
        )

        establishments = Establishment.objects.filter(is_active=True).prefetch_related("payment_methods")
        linked_establishments = 0

        for est in establishments:
            # Solo asignamos por defecto si el establecimiento aún no tiene medios de pago configurados
            if est.payment_methods.exists():
                continue

            name_lower = est.name.lower()
            selected_codes = None

            for brand_key, brand_codes in SUPERMARKET_BRAND_PAYMENT_CODES.items():
                if brand_key in name_lower:
                    selected_codes = brand_codes
                    break

            if selected_codes is None:
                if est.establishment_type == Establishment.EstablishmentType.SUPERMARKET:
                    selected_codes = DEFAULT_SUPERMARKET_CODES
                elif est.establishment_type == Establishment.EstablishmentType.MINIMARKET:
                    selected_codes = DEFAULT_MINIMARKET_CODES
                else:
                    selected_codes = DEFAULT_NEIGHBORHOOD_SHOP_CODES

            pm_objects = [method_map[c] for c in selected_codes if c in method_map]
            est.payment_methods.set(pm_objects)
            linked_establishments += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Medios de pago asignados exitosamente a {linked_establishments} establecimientos activos."
            )
        )

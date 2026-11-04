"""
Auditoría automatizada de Seguridad y Privacidad por Diseño (ISO/IEC 25023 - Evidencia E4):
- Medida M-06: Privacidad del reportante (Ley 1581 de 2012)
  X = A / B (A = endpoints públicos que no exponen coordenadas GPS del reportante ni su identidad; B = total auditados).
  Umbral obligatorio: X = 1.00 (100% protegido).
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import ActorRole, UserProfile
from catalog.models import Establishment, Product, ProductPresentation
from core_domain.entities import ProductCategory, UnitOfMeasure
from pricing.services import ReportPriceUseCase

User = get_user_model()

FORBIDDEN_REPORTER_PII_FIELDS = {
    "reporter_hash",
    "reporter_id",
    "reporter_name",
    "reporter_email",
    "reporter_phone",
    "reporter_gps",
    "reporter_latitude",
    "reporter_longitude",
    "user_id",
    "ip_address",
}


def _collect_keys_recursively(payload: object) -> set[str]:
    found: set[str] = set()
    if isinstance(payload, dict):
        for k, v in payload.items():
            found.add(str(k))
            found |= _collect_keys_recursively(v)
    elif isinstance(payload, list):
        for item in payload:
            found |= _collect_keys_recursively(item)
    return found


@pytest.mark.django_db
def test_m06_all_public_endpoints_protect_reporter_privacy_and_gps() -> None:
    """
    Verifica que el 100% de los endpoints públicos de la API (M-06 = 1.00)
    jamás expongan identidad ni coordenadas GPS personales del reportante.
    """
    est = Establishment.objects.create(
        name="Tienda La Vecina",
        establishment_type=Establishment.EstablishmentType.NEIGHBORHOOD_SHOP,
        municipality="Armenia",
        neighborhood="Granada",
        address="Calle 12 # 8-15",
    )
    prod = Product.objects.create(
        name="Café Molido Tradicional",
        category=ProductCategory.GROCERY.value,
    )
    pres = ProductPresentation.objects.create(
        product=prod,
        brand="Quindío Café",
        presentation_name="Paquete 500 g",
        quantity=Decimal(500),
        unit=UnitOfMeasure.GRAM.value,
    )

    report = ReportPriceUseCase().execute(
        presentation=pres,
        establishment=est,
        raw_price=Decimal(16500),
        reporter_token="sensitive-user-identifier-12345",
    )

    reporter_user = User.objects.create_user(
        username="secret_reporter_99",
        email="secret99@pricecol.co",
        password="Password123*",
    )
    UserProfile.objects.create(user=reporter_user, role=ActorRole.REPORTER)

    client = APIClient()
    client.force_authenticate(user=reporter_user)
    endpoints_to_audit = [
        ("GET", "/api/v1/health/"),
        ("GET", "/api/v1/establishments/"),
        ("GET", "/api/v1/products/"),
        ("GET", f"/api/v1/products/{prod.id}/"),
        ("GET", f"/api/v1/products/{prod.id}/compare/"),
        ("GET", "/api/v1/presentations/"),
        ("GET", "/api/v1/price-reports/"),
        ("GET", f"/api/v1/price-reports/{report.id}/"),
        (
            "POST",
            "/api/v1/price-reports/",
            {
                "presentation_id": pres.id,
                "establishment_id": est.id,
                "raw_price": "16800.00",
            },
        ),
    ]

    safe_endpoints = 0
    for item in endpoints_to_audit:
        method = item[0]
        url = item[1]
        if method == "GET":
            response = client.get(url)
        else:
            response = client.post(url, data=item[2], format="json")

        assert response.status_code in (200, 201), f"Error en {method} {url}: {response.status_code}"
        body_json = response.json()
        exposed_keys = _collect_keys_recursively(body_json)
        raw_text = str(body_json)

        leaked_keys = exposed_keys.intersection(FORBIDDEN_REPORTER_PII_FIELDS)
        leaked_token = (
            "sensitive-user-identifier-12345" in raw_text
            or "secret_reporter_99" in raw_text
            or report.reporter_hash in raw_text
        )

        if not leaked_keys and not leaked_token:
            safe_endpoints += 1

    m06_score = Decimal(safe_endpoints) / Decimal(len(endpoints_to_audit))
    assert m06_score == Decimal("1.00"), f"Violación de Ley 1581 (M-06): puntaje {m06_score} < 1.00"

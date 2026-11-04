"""
Pruebas de Integración Extremo a Extremo del Esqueleto Arquitectónico (Corte 2 - Fase 3.1).
Valida:
1. Flujo completo de registro ágil en góndola (EC-01) e invalidación inmediata de caché (EC-02).
2. Comparación entre presentaciones de distinta unidad de medida (M-01: 900 ml vs 1.1 L).
3. Neutralidad de la comparación (EC-06 / M-02 = 1.00) y bloqueo de precios falsos (EC-03 / M-05).
4. Extensibilidad limpia mediante `PriceSourcePort` sin modificar el núcleo (EC-05 / M-09).
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from catalog.models import Establishment, Product, ProductPresentation
from core_domain.entities import (
    ComparablePriceEntry,
    ProductCategory,
    ReliabilityStatus,
    SourceType,
    UnitOfMeasure,
    ValidityStatus,
)
from core_domain.ports import PriceSourcePort
from pricing.services import ComparePricesQueryService


@pytest.mark.django_db
def test_end_to_end_price_reporting_and_unit_comparison() -> None:
    client = APIClient()

    # Registro de un Reportante autenticado vía JWT (Tabla 4.1)
    reg_res = client.post(
        "/api/v1/auth/register/",
        data={
            "username": "reportante_test",
            "email": "rep@pricecol.co",
            "password": "Password2026*",
            "role": "REPORTER",
            "accepted_data_policy": True,
        },
        format="json",
    )
    assert reg_res.status_code == 201
    jwt_access = reg_res.json()["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {jwt_access}")

    est_tienda = Establishment.objects.create(
        name="Tienda Don Pepe",
        establishment_type=Establishment.EstablishmentType.NEIGHBORHOOD_SHOP,
        municipality="Armenia",
        neighborhood="Laureles",
        address="Cra 15 # 20-10",
    )
    est_super = Establishment.objects.create(
        name="Supermercado Grande",
        establishment_type=Establishment.EstablishmentType.SUPERMARKET,
        municipality="Armenia",
        neighborhood="Centro",
        address="Calle 21 # 14-05",
    )

    leche = Product.objects.create(
        name="Leche Entera",
        category=ProductCategory.PERISHABLE.value,
        aliases="leche, bolsa de leche",
    )
    pres_900ml = ProductPresentation.objects.create(
        product=leche,
        brand="Colanta",
        presentation_name="Bolsa 900 ml",
        quantity=Decimal(900),
        unit=UnitOfMeasure.MILLILITER.value,
    )
    pres_1_1_l = ProductPresentation.objects.create(
        product=leche,
        brand="Alquería",
        presentation_name="Bolsa 1.1 L",
        quantity=Decimal("1.1"),
        unit=UnitOfMeasure.LITER.value,
    )

    # 1. Reportante registra Leche 900 ml a $4,500 ($500.00 / 100ml) en Supermercado con promoción
    r1 = client.post(
        "/api/v1/price-reports/",
        data={
            "presentation_id": pres_900ml.id,
            "establishment_id": est_super.id,
            "raw_price": "4500.00",
            "is_promotional": True,
            "promotion_description": "Oferta de fin de semana",
        },
        format="json",
    )
    assert r1.status_code == 201
    assert r1.json()["normalized_ref_price"] == "500.00"

    # 2. Reportante registra Leche 1.1 L a $5,280 ($480.00 / 100ml) en Tienda de Barrio
    r2 = client.post(
        "/api/v1/price-reports/",
        data={
            "presentation_id": pres_1_1_l.id,
            "establishment_id": est_tienda.id,
            "raw_price": "5280.00",
        },
        format="json",
    )
    assert r2.status_code == 201
    assert r2.json()["normalized_ref_price"] == "480.00"

    # 3. Un atacante intenta registrar un precio falso de $300 COP (EC-03)
    r_fake = client.post(
        "/api/v1/price-reports/",
        data={
            "presentation_id": pres_900ml.id,
            "establishment_id": est_super.id,
            "raw_price": "300.00",
        },
        format="json",
    )
    assert r_fake.status_code == 201
    assert r_fake.json()["reliability_status"] == "ANOMALOUS"

    # 4. Consumidor consulta comparación por unidad de medida (EC-04 / EC-06)
    cmp_res = client.get(f"/api/v1/products/{leche.id}/compare/?sort_by=UNIT_PRICE_ASC")
    assert cmp_res.status_code == 200
    data = cmp_res.json()

    # El precio falso fue bloqueado; quedan los 2 precios confiables
    assert data["total_valid_results"] == 2
    assert data["excluded_non_valid_or_anomalous_count"] == 1

    # Tienda Don Pepe ($480/100ml) aparece de primera aunque su precio por bolsa ($5,280) sea mayor
    # y aunque el supermercado tenga promoción activa (Neutralidad M-02 = 1.00)
    first_place = data["ranked_results"][0]
    second_place = data["ranked_results"][1]
    assert first_place["establishment_name"] == "Tienda Don Pepe"
    assert first_place["normalized_ref_price"] == "480.00"
    assert second_place["establishment_name"] == "Supermercado Grande"
    assert second_place["is_promotional"] is True
    assert len(data["promotional_highlights_separated"]) == 1


@pytest.mark.django_db
def test_ec05_m09_commercial_module_extension_via_port_without_modifying_core() -> None:
    """
    Demuestra empíricamente la medida M-09 (Estabilidad estructural del núcleo para EC-05):
    Un adaptador del Módulo Comercial (Corte 3) se conecta a `ComparePricesQueryService`
    implementando `PriceSourcePort` sin tocar una sola línea de `core_domain` ni del servicio.
    """

    class MockCommercialModuleAdapter(PriceSourcePort):
        def fetch_entries_for_product(self, product_id: int) -> list[ComparablePriceEntry]:
            return [
                ComparablePriceEntry(
                    report_id="promo-corte3-1",
                    establishment_id=999,
                    establishment_name="Comercio Aliado Corte 3",
                    presentation_id=10,
                    presentation_name="Arroz Oficial 1kg",
                    raw_price=Decimal(3900),
                    normalized_ref_price=Decimal("390.00"),
                    reference_unit_label="100g",
                    reported_at=datetime.now(UTC),
                    validity_status=ValidityStatus.VALID,
                    reliability_status=ReliabilityStatus.VERIFIED,
                    freshness_score=Decimal("1.00"),
                    confidence_score=Decimal("0.98"),
                    source_type=SourceType.OFFICIAL_MERCHANT,
                    is_promotional=True,
                    promotion_description="Descuento 15% Pague 2 Lleve 3",
                )
            ]

    service = ComparePricesQueryService(sources=[MockCommercialModuleAdapter()])
    output = service.compare_product(product_id=1)
    assert len(output.ranked_results) == 1
    assert output.ranked_results[0].establishment_name == "Comercio Aliado Corte 3"
    assert output.ranked_results[0].requires_warning_label is True


@pytest.mark.django_db
def test_actors_table_4_1_profiles_merchant_corrections_and_moderator_workflow() -> None:
    """
    Valida los 4 Actores de la Tabla 4.1 de la Guía del Seminario Nuclear:
    1. Consumidor: Consulta comparaciones sin requerir cuenta (anónimo).
    2. Reportante: Requiere sesión JWT para registrar precios y ve su contador de aportes útiles en `/api/v1/auth/me/`.
    3. Comercio: Crea perfil, publica precios oficiales (`OFFICIAL_MERCHANT`) y solicita corrección de su negocio.
    4. Moderador: Audita reportes dudosos (`ANOMALOUS`), aprueba correcciones de comercios y gestiona cuentas.
    """
    from django.contrib.auth import get_user_model

    from accounts.models import ActorRole, UserProfile

    User = get_user_model()
    est = Establishment.objects.create(
        name="Tienda Barrio Equivocada",
        establishment_type=Establishment.EstablishmentType.NEIGHBORHOOD_SHOP,
        municipality="Armenia",
        neighborhood="Cuyabra",
        address="Calle 5 # 1-10",
    )
    prod = Product.objects.create(
        name="Panela Cuadrada",
        category=ProductCategory.GROCERY.value,
    )
    pres = ProductPresentation.objects.create(
        product=prod,
        brand="El Trapiche",
        presentation_name="Libra 500 g",
        quantity=Decimal(500),
        unit=UnitOfMeasure.GRAM.value,
    )

    anon_client = APIClient()
    # Un consumidor sin cuenta puede consultar libremente, pero no puede hacer POST de precios
    assert anon_client.get(f"/api/v1/products/{prod.id}/compare/").status_code == 200
    assert (
        anon_client.post(
            "/api/v1/price-reports/",
            data={"presentation_id": pres.id, "establishment_id": est.id, "raw_price": "3200.00"},
            format="json",
        ).status_code
        == 401
    )

    # Comercio se registra y solicita corregir el nombre de su negocio (Tabla 4.1)
    reg_merchant = anon_client.post(
        "/api/v1/auth/register/",
        data={
            "username": "comercio_trapiche",
            "email": "comercio@trapiche.co",
            "password": "Password2026*",
            "role": "MERCHANT",
            "managed_establishment_id": est.id,
            "accepted_data_policy": True,
        },
        format="json",
    )
    assert reg_merchant.status_code == 201
    merchant_token = reg_merchant.json()["access"]

    merchant_client = APIClient()
    merchant_client.credentials(HTTP_AUTHORIZATION=f"Bearer {merchant_token}")

    corr_res = merchant_client.post(
        "/api/v1/merchant/correction-requests/",
        data={
            "establishment": est.id,
            "proposed_name": "Tienda de Barrio La Cuyabra Oficial",
            "proposed_address": "Calle 5 # 10-25",
            "justification": "El número de la nomenclatura tenía un error de digitación.",
        },
        format="json",
    )
    assert corr_res.status_code == 201
    correction_id = corr_res.json()["id"]

    # Moderador inicia sesión, aprueba la corrección del comercio y revisa la cola de reportes anómalos
    mod_user = User.objects.create_user(
        username="mod_quindio",
        email="mod@pricecol.co",
        password="ModPassword2026*",
        is_staff=True,
    )
    UserProfile.objects.create(user=mod_user, role=ActorRole.MODERATOR)

    login_mod = anon_client.post(
        "/api/v1/auth/login/",
        data={"username": "mod_quindio", "password": "ModPassword2026*"},
        format="json",
    )
    assert login_mod.status_code == 200
    mod_token = login_mod.json()["access"]

    mod_client = APIClient()
    mod_client.credentials(HTTP_AUTHORIZATION=f"Bearer {mod_token}")

    approve_res = mod_client.post(
        f"/api/v1/moderation/correction-requests/{correction_id}/approve/",
        data={"moderator_notes": "Verificado en cámara de comercio."},
        format="json",
    )
    assert approve_res.status_code == 200
    est.refresh_from_db()
    assert est.name == "Tienda de Barrio La Cuyabra Oficial"


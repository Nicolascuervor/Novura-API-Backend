"""
Pruebas de integración para la configuración de despliegue (CORS y servicio de /media/ en producción).
"""

import pytest
from django.test import override_settings


@pytest.mark.django_db
class TestDeployCorsConfiguration:
    @override_settings(CORS_ALLOWED_ORIGINS=["https://nuvora.vercel.app"])
    def test_cors_preflight_allows_whitelisted_origin(self, client):
        response = client.options(
            "/api/v1/health/",
            HTTP_ORIGIN="https://nuvora.vercel.app",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        )
        assert response.status_code == 204
        assert response["Access-Control-Allow-Origin"] == "https://nuvora.vercel.app"
        assert "Authorization" in response["Access-Control-Allow-Headers"]
        assert "ETag" in response["Access-Control-Expose-Headers"]

    @override_settings(CORS_ALLOWED_ORIGINS=["https://nuvora.vercel.app"])
    def test_cors_blocks_unlisted_origin_from_receiving_allow_header(self, client):
        response = client.get(
            "/api/v1/health/",
            HTTP_ORIGIN="https://malicious-site.example",
        )
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" not in response

    @override_settings(CORS_ALLOWED_ORIGINS=["https://nuvora.vercel.app"])
    def test_cors_adds_origin_header_on_normal_get_for_allowed_origin(self, client):
        response = client.get(
            "/api/v1/health/",
            HTTP_ORIGIN="https://nuvora.vercel.app",
        )
        assert response.status_code == 200
        assert response["Access-Control-Allow-Origin"] == "https://nuvora.vercel.app"
        assert "Origin" in response.get("Vary", "")

    def test_refresh_price_dates_command_restores_expired_reports_to_valid(self, client):
        from datetime import timedelta
        from decimal import Decimal

        from django.core.management import call_command
        from django.utils import timezone

        from catalog.models import Establishment, Product, ProductPresentation
        from core_domain.entities import ProductCategory, ReliabilityStatus, UnitOfMeasure
        from pricing.models import PriceReport

        product = Product.objects.create(
            name="Ajo Cosecha Quindío Test",
            category=ProductCategory.FRUITS_VEGGIES.value,
        )
        pres = ProductPresentation.objects.create(
            product=product,
            brand="Cosecha Quindío",
            presentation_name="Malla 100g",
            quantity=Decimal(100),
            unit=UnitOfMeasure.GRAM.value,
        )
        est = Establishment.objects.create(
            name="Tienda Test Armenia",
            establishment_type=Establishment.EstablishmentType.NEIGHBORHOOD_SHOP,
            municipality="Armenia",
            neighborhood="Centro",
            address="Calle 10 # 10-10",
        )
        rep = PriceReport.objects.create(
            presentation=pres,
            establishment=est,
            raw_price=Decimal("2500.00"),
            normalized_ref_price=Decimal("2500.00"),
            price_per_base_unit=Decimal("25.0000"),
            reference_unit_label="100g",
            reliability_status=ReliabilityStatus.VERIFIED.value,
            reporter_hash="hash_test_1",
        )
        # Envejecer 20 días para que quede EXPIRED
        expired_date = timezone.now() - timedelta(days=20)
        PriceReport.objects.filter(pk=rep.pk).update(reported_at=expired_date)

        # Antes del comando: 0 resultados válidos por estar expirado
        res_before = client.get(f"/api/v1/products/{product.id}/compare/")
        assert res_before.status_code == 200
        assert res_before.json()["total_valid_results"] == 0

        # Ejecutar comando refresh_price_dates
        call_command("refresh_price_dates")

        # Después del comando: el reporte vuelve a estar VALID hoy
        res_after = client.get(f"/api/v1/products/{product.id}/compare/")
        assert res_after.status_code == 200
        assert res_after.json()["total_valid_results"] == 1
        assert res_after.json()["ranked_results"][0]["validity_status"] == "VALID"


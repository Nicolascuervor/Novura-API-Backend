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

"""
URL configuration for pricecol_api_backend project.
Expone los endpoints REST v1 del Núcleo, Autenticación JWT y Perfiles de Actores (Tabla 4.1),
junto con la documentación interactiva OpenAPI 3 (Swagger / Redoc).
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter

from accounts.views import (
    ActorRegistrationAPIView,
    CurrentActorProfileAPIView,
    MerchantCorrectionRequestViewSet,
    ModeratorAccountManagementViewSet,
    ModeratorApproveCorrectionAPIView,
    ModeratorFlaggedReportsListAPIView,
    ModeratorReviewReportAPIView,
    PricecolLoginAPIView,
    PricecolTokenRefreshAPIView,
)
from catalog.views import (
    EstablishmentViewSet,
    ProductPresentationViewSet,
    ProductViewSet,
)
from pricing.views import PriceReportViewSet, ProductPriceComparisonAPIView

router = DefaultRouter()
router.register(r"establishments", EstablishmentViewSet, basename="establishment")
router.register(r"products", ProductViewSet, basename="product")
router.register(r"presentations", ProductPresentationViewSet, basename="presentation")
router.register(r"price-reports", PriceReportViewSet, basename="price-report")
router.register(
    r"merchant/correction-requests",
    MerchantCorrectionRequestViewSet,
    basename="merchant-correction",
)
router.register(
    r"moderation/accounts",
    ModeratorAccountManagementViewSet,
    basename="moderation-account",
)


def health_check(_request):
    """Healthcheck ligero para monitoreo de disponibilidad y contenedores (Fiabilidad - EC-04)."""
    return JsonResponse({"status": "ok", "service": "pricecol-api-backend", "version": "1.1.0"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/", health_check, name="api-health"),
    # Autenticación JWT y Perfiles de Actores (Sección 4.1 de la Guía)
    path("api/v1/auth/register/", ActorRegistrationAPIView.as_view(), name="auth-register"),
    path("api/v1/auth/login/", PricecolLoginAPIView.as_view(), name="auth-login"),
    path("api/v1/auth/refresh/", PricecolTokenRefreshAPIView.as_view(), name="auth-refresh"),
    path("api/v1/auth/me/", CurrentActorProfileAPIView.as_view(), name="auth-me"),
    # Endpoints de Moderador (Tabla 4.1: reportes dudosos y correcciones de comercios)
    path(
        "api/v1/moderation/flagged-reports/",
        ModeratorFlaggedReportsListAPIView.as_view(),
        name="moderation-flagged-reports",
    ),
    path(
        "api/v1/moderation/flagged-reports/<int:report_id>/review/",
        ModeratorReviewReportAPIView.as_view(),
        name="moderation-review-report",
    ),
    path(
        "api/v1/moderation/correction-requests/<int:correction_id>/approve/",
        ModeratorApproveCorrectionAPIView.as_view(),
        name="moderation-approve-correction",
    ),
    # Endpoint central de comparación neutral normalizada
    path(
        "api/v1/products/<int:product_id>/compare/",
        ProductPriceComparisonAPIView.as_view(),
        name="product-price-compare",
    ),
    path("api/v1/", include(router.urls)),
    # Documentación estándar OpenAPI 3 (Mínimo exigible de la Guía)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

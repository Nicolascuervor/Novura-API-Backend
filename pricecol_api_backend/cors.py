"""
Middleware ligero de CORS sin dependencias externas (`pricecol_api_backend/cors.py`).

Permite que `Novura-Frontend` consuma `/api/v1/` y `/media/` tanto si se despliega
detrás del mismo Nginx (mismo origen) como si se aloja en un dominio separado
(por ejemplo, Vercel o Netlify) declarando `DJANGO_CORS_ALLOWED_ORIGINS` en `.env`.
"""

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.cache import patch_vary_headers

CORS_ALLOW_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD"
CORS_ALLOW_HEADERS = "Authorization, Content-Type, Accept, Origin, If-None-Match, X-Requested-With"
CORS_EXPOSE_HEADERS = "ETag, X-Cache-Status, Cache-Control"


def _is_origin_allowed(origin: str) -> bool:
    allowed_origins: list[str] = list(getattr(settings, "CORS_ALLOWED_ORIGINS", []))
    if not allowed_origins:
        return False
    if "*" in allowed_origins:
        return True
    normalized = origin.rstrip("/")
    return any(candidate.rstrip("/") == normalized for candidate in allowed_origins)


class CorsHeadersMiddleware:
    """Agrega cabeceras CORS estrictas solo para orígenes explícitamente autorizados."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        origin = request.headers.get("Origin", "").strip()
        is_allowed = bool(origin) and _is_origin_allowed(origin)

        if request.method == "OPTIONS" and is_allowed:
            preflight = HttpResponse(status=204)
            self._apply_cors_headers(preflight, origin)
            preflight["Access-Control-Max-Age"] = "86400"
            return preflight

        response = self.get_response(request)
        if is_allowed:
            self._apply_cors_headers(response, origin)
        return response

    @staticmethod
    def _apply_cors_headers(response: HttpResponse, origin: str) -> None:
        response["Access-Control-Allow-Origin"] = origin
        response["Access-Control-Allow-Methods"] = CORS_ALLOW_METHODS
        response["Access-Control-Allow-Headers"] = CORS_ALLOW_HEADERS
        response["Access-Control-Expose-Headers"] = CORS_EXPOSE_HEADERS
        response["Access-Control-Allow-Credentials"] = "true"
        patch_vary_headers(response, ("Origin",))

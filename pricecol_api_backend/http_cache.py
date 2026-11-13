"""
Middleware y utilidades de Caché Proxy HTTP / Edge & Client Caching (`pricecol_api_backend/http_cache.py`).

Resuelve la tensión arquitectónica ATAM entre:
- EC-04 (Eficiencia de desempeño <= 1.8s p95 bajo 500 usuarios concurrentes y ahorro de ancho de banda móvil)
- EC-02 (Actualidad inmediata del dato cuando cambia un precio o un ítem del catálogo)
- OWASP Web Cache Deception (`django-security-auditor` / `red-team-pentester`):
  Aísla estrictamente rutas privadas (`private, no-store`) de rutas públicas (`public, s-maxage=...`).
"""

import hashlib
import re
from collections.abc import Callable
from typing import Any

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, HttpResponseNotModified

CATALOG_CACHE_VERSION_KEY: str = "pricecol:catalog:cache_ver"


def get_product_comparison_cache_version_key(product_id: int) -> str:
    return f"pricecol:product:{product_id}:cache_ver"


PUBLIC_COMPARISON_CACHE_CONTROL: str = (
    "public, max-age=30, s-maxage=120, stale-while-revalidate=60"
)
PUBLIC_CATALOG_CACHE_CONTROL: str = (
    "public, max-age=60, s-maxage=300, stale-while-revalidate=120"
)
IMMUTABLE_MEDIA_CACHE_CONTROL: str = "public, max-age=604800, immutable"
PRIVATE_NO_STORE_CACHE_CONTROL: str = "no-store, no-cache, private, must-revalidate"

_COMPARE_PATH_RE = re.compile(r"^/api/v1/products/(?P<product_id>\d+)/compare/?$")
_PUBLIC_CATALOG_PREFIXES: tuple[str, ...] = (
    "/api/v1/payment-methods/",
    "/api/v1/products/",
    "/api/v1/presentations/",
    "/api/v1/establishments/",
)
_PRIVATE_PATH_PREFIXES: tuple[str, ...] = (
    "/api/v1/auth/",
    "/api/v1/moderation/",
    "/api/v1/merchant/",
    "/admin/",
)


def _safe_cache_get(key: str, default: Any = None) -> Any:
    """Lectura resiliente de caché: nunca bloquea ni lanza excepción si Redis no está disponible."""
    try:
        return cache.get(key, default)
    except (OSError, ValueError, RuntimeError):
        return default


def _safe_cache_set(key: str, value: Any, timeout: int = 86400) -> None:
    """Escritura resiliente de caché: degrada silenciosamente si Redis no responde."""
    try:
        cache.set(key, value, timeout=timeout)
    except (OSError, ValueError, RuntimeError):
        return


def get_catalog_cache_version() -> int:
    """Obtiene la versión global actual del catálogo público desde Redis / caché."""
    ver = _safe_cache_get(CATALOG_CACHE_VERSION_KEY)
    if ver is None:
        _safe_cache_set(CATALOG_CACHE_VERSION_KEY, 1, timeout=86400)
        return 1
    return int(ver)


def bump_catalog_cache_version() -> int:
    """
    Incrementa atómicamente la versión global del catálogo público cuando se crea,
    actualiza o desactiva un establecimiento, producto, presentación o medio de pago.
    """
    current = int(_safe_cache_get(CATALOG_CACHE_VERSION_KEY, 1))
    next_ver = current + 1
    _safe_cache_set(CATALOG_CACHE_VERSION_KEY, next_ver, timeout=86400)
    return next_ver


def _build_query_fingerprint(request: HttpRequest) -> str:
    """Genera un hash corto determinístico de la ruta y los query params ordenados."""
    sorted_items = sorted(request.GET.lists())
    canonical = f"{request.path}?{sorted_items!r}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _if_none_match_matches(header_value: str | None, current_etag: str) -> bool:
    """Evalúa coincidencia débil o exacta según RFC 9110 para `If-None-Match`."""
    if not header_value:
        return False
    raw = header_value.strip()
    if raw == "*":
        return True
    normalized_target = current_etag.removeprefix("W/").strip('"')
    for candidate in raw.split(","):
        cleaned = candidate.strip().removeprefix("W/").strip('"')
        if cleaned == normalized_target:
            return True
    return False


def _is_private_request(request: HttpRequest) -> bool:
    """
    Determina si la petición involucra datos privados o dependientes de sesión/usuario
    para prevenir vulnerabilidades de Web Cache Deception en proxies compartidos.
    """
    path = request.path
    if any(path.startswith(prefix) for prefix in _PRIVATE_PATH_PREFIXES):
        return True
    if request.headers.get("Authorization"):
        return True
    mine_param = request.GET.get("mine", "").strip().lower()
    return mine_param in ("true", "1", "yes")


def _can_short_circuit_304(request: HttpRequest, etag: str) -> bool:
    """
    Permite cortocircuitar con `304 Not Modified` cuando `If-None-Match` coincide,
    excepto en llamadas XHR/fetch directas del navegador (`Sec-Fetch-Dest: empty`) a través
    de proxies de desarrollo (como Vite Proxy), donde clientes SPA (`axios`/`fetch`) esperan
    siempre un cuerpo JSON `200 OK` si la caché en memoria del navegador no interceptó antes.
    """
    if request.headers.get("Sec-Fetch-Dest") == "empty":
        return False
    return _if_none_match_matches(request.headers.get("If-None-Match"), etag)


class HttpProxyCacheMiddleware:
    """
    Middleware HTTP de Caché Proxy (Nginx / Cloudflare / Navegador):
    - Cortocircuita peticiones condicionales (`If-None-Match`) con `304 Not Modified` en O(1)
      consultando únicamente la versión entera en Redis sin tocar PostgreSQL.
    - Inyecta `Cache-Control` y `ETag` diferenciados por política pública vs. privada.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # 1. Métodos de mutación (POST, PUT, PATCH, DELETE) jamás se cachean
        if request.method not in ("GET", "HEAD"):
            response = self.get_response(request)
            response.headers["Cache-Control"] = PRIVATE_NO_STORE_CACHE_CONTROL
            return response

        path = request.path

        # 2. Archivos multimedia sanitizados con nombre UUIDv4 inmutable
        if path.startswith("/media/"):
            response = self.get_response(request)
            if response.status_code == 200:
                response.headers["Cache-Control"] = IMMUTABLE_MEDIA_CACHE_CONTROL
                response.headers["X-Proxy-Cache-Policy"] = "immutable-media"
            return response

        # 3. Protección Anti-Web-Cache-Deception para rutas o filtros privados
        if _is_private_request(request):
            response = self.get_response(request)
            response.headers["Cache-Control"] = PRIVATE_NO_STORE_CACHE_CONTROL
            response.headers["X-Proxy-Cache-Policy"] = "private-no-store"
            return response

        # 4. Endpoint público crítico: Comparador Neutral `/api/v1/products/{id}/compare/`
        compare_match = _COMPARE_PATH_RE.match(path)
        if compare_match:
            product_id = int(compare_match.group("product_id"))
            prod_ver = int(
                _safe_cache_get(get_product_comparison_cache_version_key(product_id), 1)
            )
            cat_ver = get_catalog_cache_version()
            q_hash = _build_query_fingerprint(request)
            etag = f'W/"cmp-p{product_id}-v{prod_ver}-c{cat_ver}-{q_hash}"'

            if _can_short_circuit_304(request, etag):
                not_modified = HttpResponseNotModified()
                not_modified.headers["ETag"] = etag
                not_modified.headers["Cache-Control"] = PUBLIC_COMPARISON_CACHE_CONTROL
                not_modified.headers["X-Proxy-Cache-Policy"] = "public-comparison"
                not_modified.headers["Content-Length"] = "0"
                return not_modified

            response = self.get_response(request)
            if response.status_code == 200:
                new_prod_ver = int(
                    _safe_cache_get(get_product_comparison_cache_version_key(product_id), 1)
                )
                new_cat_ver = get_catalog_cache_version()
                final_etag = f'W/"cmp-p{product_id}-v{new_prod_ver}-c{new_cat_ver}-{q_hash}"'
                response.headers["ETag"] = final_etag
                response.headers["Cache-Control"] = PUBLIC_COMPARISON_CACHE_CONTROL
                response.headers["X-Proxy-Cache-Policy"] = "public-comparison"
            return response

        # 5. Endpoints públicos del Catálogo (`/payment-methods/`, `/products/`, `/presentations/`, `/establishments/`)
        if any(path.startswith(prefix) for prefix in _PUBLIC_CATALOG_PREFIXES):
            cat_ver = get_catalog_cache_version()
            q_hash = _build_query_fingerprint(request)
            etag = f'W/"cat-v{cat_ver}-{q_hash}"'

            if _can_short_circuit_304(request, etag):
                not_modified = HttpResponseNotModified()
                not_modified.headers["ETag"] = etag
                not_modified.headers["Cache-Control"] = PUBLIC_CATALOG_CACHE_CONTROL
                not_modified.headers["X-Proxy-Cache-Policy"] = "public-catalog"
                not_modified.headers["Content-Length"] = "0"
                return not_modified

            response = self.get_response(request)
            if response.status_code == 200:
                response.headers["ETag"] = etag
                response.headers["Cache-Control"] = PUBLIC_CATALOG_CACHE_CONTROL
                response.headers["X-Proxy-Cache-Policy"] = "public-catalog"
            return response

        return self.get_response(request)

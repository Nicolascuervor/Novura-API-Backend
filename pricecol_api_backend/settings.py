"""
Django settings for pricecol_api_backend project.
Configurado para el Seminario Nuclear (Arquitectura de Software II y Modelos de Calidad)
y endurecido según `django-security-auditor` (OWASP Top 10: sin credenciales hardcodeadas y con Rate Limiting).
"""

import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_local_dotenv(dotenv_path: Path) -> None:
    """Carga automáticamente las variables de `.env` sin requerir comandos manuales en consola."""
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


_load_local_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "pricecol-fallback-ephemeral-test-key-do-not-use-in-prod",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() != "false"

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    # Pricecol modular apps (Core Nucleus + Profiles)
    "accounts.apps.AccountsConfig",
    "catalog.apps.CatalogConfig",
    "pricing.apps.PricingConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "pricecol_api_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "pricecol_api_backend.wsgi.application"

# Database Configuration (Lee automáticamente `.env` local; soporta PostgreSQL y fallback a SQLite en CI)
USE_POSTGRES = os.environ.get("USE_POSTGRES", "False").lower() == "true"

if USE_POSTGRES:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "pricecol_db"),
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Autenticación: login estándar por email + contraseña (la API), y username para el panel /admin/
AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmailAuthBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Hardening de Cabeceras y Cookies (OWASP Top 10 - `django-security-auditor`)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Cache Configuration (EC-04: Lectura intensiva y picos de 500 usuarios concurrentes)
# Soporta Redis distribuido (`USE_REDIS=True`) con fallback automático a `LocMemCache` en pruebas o desarrollo sin Redis.
USE_REDIS = os.environ.get("USE_REDIS", "False").lower() == "true"
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1")

if USE_REDIS:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "pricecol",
            "TIMEOUT": 120,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "pricecol-high-concurrency-cache",
            "TIMEOUT": 120,
        }
    }

# Celery & Background Tasks Configuration (EC-01 <= 15s, EC-02 Vigencia y Trazabilidad de Auditoría)
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
# Si no se fuerza worker separado (`CELERY_TASK_ALWAYS_EAGER=False`), ejecuta tareas de forma resiliente
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "True").lower() != "false"
CELERY_TASK_EAGER_PROPAGATES = True

# Django REST Framework, Throttling & OpenAPI 3 Configuration
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "600/minute",
        "user": "1200/minute",
        "auth_burst": "30/minute",
        "price_report": "60/minute",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=2),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Pricecol API - Plataforma Colaborativa de Comparación de Precios (Quindío)",
    "DESCRIPTION": (
        "API Backend del Núcleo para consulta, normalización por unidad de medida, "
        "gestión de perfiles de los 4 Actores (Consumidor, Reportante, Comercio, Moderador) y "
        "registro colaborativo de precios entre tiendas de barrio, minimercados y supermercados "
        "en Armenia y el departamento del Quindío. Diseñada bajo ISO/IEC 25010:2023 e ISO/IEC 25012."
    ),
    "VERSION": "1.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}

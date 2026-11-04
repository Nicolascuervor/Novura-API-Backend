"""
Permisos basados en roles de actores (RBAC) según la Tabla 4.1 de la Guía del Seminario Nuclear.
"""

from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from accounts.models import ActorRole


class IsAuthenticatedAndNotSuspended(permissions.BasePermission):
    """Exige cuenta activa y no suspendida por moderación."""

    message = "Debes iniciar sesión con una cuenta activa para realizar esta acción."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not (request.user and request.user.is_authenticated and request.user.is_active):
            return False
        profile = getattr(request.user, "profile", None)
        if profile and profile.is_suspended:
            self.message = "Tu cuenta ha sido suspendida por moderación debido a reportes anómalos."
            return False
        return True


class CanReportPricesPermission(permissions.BasePermission):
    """
    Tabla 4.1:
    - Consumidor: Puede consultar precios con o sin cuenta (GET, HEAD, OPTIONS).
    - Reportante / Comercio / Moderador: Usuario registrado con sesión iniciada que aporta precios (POST).
    """

    message = (
        "Para registrar precios debes iniciar sesión como Reportante o Comercio "
        "(POST /api/v1/auth/login/). Las consultas de precios son libres sin cuenta."
    )

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True

        if not (request.user and request.user.is_authenticated and request.user.is_active):
            return False

        profile = getattr(request.user, "profile", None)
        if profile is None:
            return True

        if profile.is_suspended:
            self.message = "Tu cuenta se encuentra suspendida por moderación."
            return False

        return profile.role in (
            ActorRole.REPORTER,
            ActorRole.MERCHANT,
            ActorRole.MODERATOR,
            ActorRole.CONSUMER,
        )


class IsMerchantActor(permissions.BasePermission):
    """Exige que el usuario autenticado tenga rol Comercio (MERCHANT) o Moderador."""

    message = "Esta acción es exclusiva para cuentas con perfil de Comercio (MERCHANT)."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not (request.user and request.user.is_authenticated and request.user.is_active):
            return False
        profile = getattr(request.user, "profile", None)
        if not profile or profile.is_suspended:
            return False
        return profile.role in (ActorRole.MERCHANT, ActorRole.MODERATOR)


class IsModeratorActor(permissions.BasePermission):
    """Exige que el usuario tenga el rol administrativo Moderador (MODERATOR) o sea superusuario."""

    message = "Acceso restringido exclusivamente al rol administrativo de Moderador."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not (request.user and request.user.is_authenticated and request.user.is_active):
            return False
        if request.user.is_superuser or request.user.is_staff:
            return True
        profile = getattr(request.user, "profile", None)
        return bool(profile and not profile.is_suspended and profile.role == ActorRole.MODERATOR)

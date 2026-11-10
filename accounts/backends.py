"""
Backend de autenticación por correo electrónico (estándar email + contraseña).
El `username` se conserva como nombre visible dentro de la app, pero ya no se usa para iniciar sesión.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.base_user import AbstractBaseUser
from django.http import HttpRequest

User = get_user_model()


class EmailAuthBackend(ModelBackend):
    """
    Autentica con `email` (insensible a mayúsculas) y contraseña.

    Seguridad (`django-security-auditor` / `red-team-pentester`):
    - Mitiga enumeración de cuentas por temporización: si el email no existe, igual se ejecuta
      el hasheo de la contraseña para que la respuesta tarde lo mismo.
    - Si por datos heredados existieran correos duplicados, se rechaza el login en vez de
      adivinar a qué cuenta entrar.
    - Respeta `is_active` mediante `user_can_authenticate`.
    """

    def authenticate(
        self,
        request: HttpRequest | None,
        email: str | None = None,
        password: str | None = None,
        **kwargs,
    ) -> AbstractBaseUser | None:
        if not email or not password:
            return None

        try:
            user = User.objects.get(email__iexact=email.strip())
        except User.DoesNotExist:
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

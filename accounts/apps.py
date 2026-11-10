from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Perfiles de Actores y Moderación"

    def ready(self) -> None:
        from django.contrib.auth import get_user_model
        from django.db.models.signals import pre_save

        from accounts.models import UserProfile
        from accounts.services import assign_encoded_id_on_pre_save

        user_model = get_user_model()
        pre_save.connect(
            assign_encoded_id_on_pre_save,
            sender=user_model,
            dispatch_uid="accounts.encode_user_id_pre_save",
        )
        pre_save.connect(
            assign_encoded_id_on_pre_save,
            sender=UserProfile,
            dispatch_uid="accounts.encode_user_profile_id_pre_save",
        )


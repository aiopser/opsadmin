from django.apps import AppConfig


class ProvisioningConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.provisioning"
    verbose_name = "资源申请与交付"

    def ready(self):
        from . import worker_health  # noqa: F401

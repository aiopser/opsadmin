from django.apps import AppConfig


class OpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ops"
    verbose_name = "Operations platform"

    def ready(self):
        from .tasklog import signal_handler  # noqa: F401

from django.apps import AppConfig


class OpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ops"
    # Keep the historical label so existing migration records remain valid
    # after moving the package from apps.ansible_platform to apps.ops.
    label = "ansible_platform"
    verbose_name = "Operations platform"

    def ready(self):
        from .tasklog import signal_handler  # noqa: F401

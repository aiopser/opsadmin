from django.apps import AppConfig


class JobsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.jobs"
    verbose_name = "Jobs"

    def ready(self):
        from . import alerts  # noqa: F401
        from . import worker_health  # noqa: F401

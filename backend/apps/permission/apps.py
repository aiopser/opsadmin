from django.apps import AppConfig


class PermissionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.permission"
    verbose_name = "权限系统"

    def ready(self):
        from apps.permission import signals

        signals.register_user_role_signal()

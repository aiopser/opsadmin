from django.contrib import admin

# Register your models here.
from . import models


@admin.register(models.Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("pk", "name", "is_system", "permission_custom")
    search_fields = ["pk", "name"]

    def permission_custom(self, obj):
        return ", ".join(obj.permission.values_list("code", flat=True))

    permission_custom.short_description = "Permissions"


@admin.register(models.Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "code",
        "name",
        "type",
        "path",
        "method",
        "is_system",
        "is_active",
    )
    search_fields = ["pk", "code", "name", "path", "method"]
    list_filter = ["type", "is_system", "is_active"]


@admin.register(models.Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ("pk", "path", "component", "name", "title")
    search_fields = ["pk", "title", "component", "path"]


@admin.register(models.PermissionAuditLog)
class PermissionAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "action",
        "target_type",
        "target_id",
        "actor_name",
        "created_at",
    )
    search_fields = ["pk", "target_type", "target_id", "actor_name", "target_repr"]
    list_filter = ["action", "target_type"]


@admin.register(models.PermissionAccessLog)
class PermissionAccessLogAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "actor_name",
        "method",
        "path",
        "status",
        "reason",
        "created_at",
    )
    search_fields = ["pk", "actor_name", "method", "path", "reason"]
    list_filter = ["status", "method"]

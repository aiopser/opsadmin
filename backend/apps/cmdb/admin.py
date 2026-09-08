from django.contrib import admin

from .models import (
    AssetHost,
    AssetSource,
    AssetSyncRecord,
    Business,
    CredentialRef,
    HostGroup,
    HostGroupMembership,
    HostTag,
    HostTagBinding,
    ServiceTreeNode,
)


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "updated_at")
    search_fields = ("code", "name")
    list_filter = ("is_active",)


@admin.register(AssetSource)
class AssetSourceAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "source_type", "is_active", "last_synced_at")
    search_fields = ("code", "name", "endpoint")
    list_filter = ("source_type", "is_active")


@admin.register(AssetSyncRecord)
class AssetSyncRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source",
        "status",
        "total_count",
        "created_count",
        "updated_count",
        "skipped_count",
        "created_at",
    )
    list_filter = ("status", "source")
    search_fields = ("task_id", "error_message")


@admin.register(ServiceTreeNode)
class ServiceTreeNodeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "node_type", "business", "parent", "is_active")
    search_fields = ("code", "name", "description")
    list_filter = ("node_type", "is_active", "business")




@admin.register(CredentialRef)
class CredentialRefAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "scope", "updated_at")
    search_fields = ("name", "secret_ref")
    list_filter = ("type", "scope")


@admin.register(AssetHost)
class AssetHostAdmin(admin.ModelAdmin):
    list_display = (
        "hostname",
        "primary_ip",
        "os_family",
        "environment",
        "default_gateway",
        "status",
    )
    search_fields = ("hostname", "primary_ip", "image_name", "app_code")
    list_filter = ("os_family", "environment", "default_gateway", "status")


admin.site.register(HostGroup)
admin.site.register(HostGroupMembership)
admin.site.register(HostTag)
admin.site.register(HostTagBinding)

from django.contrib import admin

from .models import (
    CommandAtom,
    CommandVersion,
    WorkflowNode,
    WorkflowTemplate,
    WorkflowVersion,
)


@admin.register(CommandAtom)
class CommandAtomAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "category", "status", "risk_level", "updated_at")
    search_fields = ("name", "code", "category")
    list_filter = ("status", "risk_level")


@admin.register(CommandVersion)
class CommandVersionAdmin(admin.ModelAdmin):
    list_display = ("command", "version", "status", "command_type", "published_at")
    search_fields = ("command__name", "command__code", "content")
    list_filter = ("status", "command_type")


@admin.register(WorkflowTemplate)
class WorkflowTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "status", "owner_team", "updated_at")
    search_fields = ("name", "code", "owner_team")
    list_filter = ("status",)


@admin.register(WorkflowVersion)
class WorkflowVersionAdmin(admin.ModelAdmin):
    list_display = ("workflow", "version", "status", "published_at")
    search_fields = ("workflow__name", "workflow__code")
    list_filter = ("status",)


@admin.register(WorkflowNode)
class WorkflowNodeAdmin(admin.ModelAdmin):
    list_display = ("workflow_version", "node_key", "name", "order_index")
    search_fields = ("node_key", "name")

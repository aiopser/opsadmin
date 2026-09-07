from django.contrib import admin

from .models import HostRunResult, JobEventLog, NodeRun, WorkflowRun


@admin.register(WorkflowRun)
class WorkflowRunAdmin(admin.ModelAdmin):
    list_display = ("id", "workflow_version", "status", "trigger_type", "worker_pool")
    list_filter = ("status", "trigger_type", "worker_pool")
    search_fields = ("failure_reason",)


@admin.register(NodeRun)
class NodeRunAdmin(admin.ModelAdmin):
    list_display = ("id", "workflow_run", "workflow_node", "status", "exit_code")
    list_filter = ("status",)


@admin.register(HostRunResult)
class HostRunResultAdmin(admin.ModelAdmin):
    list_display = ("id", "node_run", "hostname", "ip", "status", "changed", "rc")
    list_filter = ("status", "changed")
    search_fields = ("hostname", "ip")


@admin.register(JobEventLog)
class JobEventLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "workflow_run",
        "node_run",
        "host_id",
        "event_type",
        "created_at",
    )
    list_filter = ("event_type",)
    search_fields = ("message",)

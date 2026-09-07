from django.contrib import admin

from .models import DomainAuditEvent


@admin.register(DomainAuditEvent)
class DomainAuditEventAdmin(admin.ModelAdmin):
    list_display = ("id", "domain", "actor", "action", "resource_type", "resource_id", "ip_address", "created_at")
    list_filter = ("domain", "action", "resource_type")
    search_fields = ("resource_id", "user_agent")

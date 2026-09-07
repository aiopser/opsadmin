from django.conf import settings
from django.db import models

from common.models import StandardModelMixin


class DomainAuditEvent(StandardModelMixin):
    class Domain(models.TextChoices):
        OPS = "ops", "Ops system"
        TASK = "task", "Task system"
        AUTOMATION = "automation", "Automation resources"
        CMDB = "cmdb", "Asset management"
        SECURITY = "security", "Security"
        SYSTEM = "system", "System"

    domain = models.CharField(max_length=32, choices=Domain.choices, default=Domain.SYSTEM, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="domain_audit_events")
    action = models.CharField(max_length=64, db_index=True)
    resource_type = models.CharField(max_length=64, db_index=True)
    resource_id = models.CharField(max_length=64, blank=True, default="")
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    request_id = models.CharField(max_length=128, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "audit_center_event"
        ordering = ["-id"]

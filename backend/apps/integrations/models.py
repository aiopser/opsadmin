from django.conf import settings
from django.db import models
from common.models import StandardModelMixin


class JumpServerConnection(StandardModelMixin):
    name = models.CharField(max_length=128)
    endpoint = models.URLField()
    key_id = models.CharField(max_length=128)
    secret_encrypted = models.TextField(blank=True)
    org_id = models.CharField(max_length=64, blank=True)
    node_id = models.CharField(max_length=64)
    linux_platform = models.PositiveIntegerField(default=1)
    windows_platform = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)
    verify_tls = models.BooleanField(default=True)
    sync_interval_minutes = models.PositiveIntegerField(default=0)
    sync_actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    selected_host_ids = models.JSONField(default=list)
    last_sync_at = models.DateTimeField(null=True)


class JumpServerMapping(StandardModelMixin):
    connection = models.ForeignKey(
        JumpServerConnection, on_delete=models.PROTECT, related_name="mappings"
    )
    host = models.ForeignKey("cmdb.AssetHost", on_delete=models.PROTECT)
    external_id = models.UUIDField(unique=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "host"], name="unique_jms_host"
            )
        ]


class JumpServerSync(StandardModelMixin):
    connection = models.ForeignKey(
        JumpServerConnection, on_delete=models.PROTECT, related_name="runs"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    status = models.CharField(max_length=16, default="preview")
    snapshot = models.JSONField(default=list)
    connection_version = models.DateTimeField()
    expires_at = models.DateTimeField()
    error = models.TextField(blank=True)
    results = models.JSONField(default=list)
    task_id = models.CharField(max_length=128, blank=True)

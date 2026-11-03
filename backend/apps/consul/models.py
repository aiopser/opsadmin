from django.db import models
from django.conf import settings
import uuid
from common.models import StandardModelMixin


class ConsulTemplateFile(StandardModelMixin):
    """整文件托管的 consul-template 配置模板及其下发状态。"""

    class DeployStatus(models.TextChoices):
        PENDING = "pending", "待下发"
        SUCCESS = "success", "成功"
        FAILURE = "failure", "失败"

    name = models.CharField(max_length=128, unique=True)
    host = models.ForeignKey(
        "cmdb.AssetHost",
        on_delete=models.PROTECT,
        related_name="consul_template_files",
    )
    path = models.CharField(max_length=512)
    content = models.TextField(blank=True, default="")
    reload_command = models.CharField(
        max_length=512, blank=True, default="systemctl reload consul-template"
    )
    last_deploy_status = models.CharField(
        max_length=16,
        choices=DeployStatus.choices,
        default=DeployStatus.PENDING,
    )
    last_deploy_at = models.DateTimeField(null=True, blank=True)
    last_deploy_message = models.CharField(max_length=512, blank=True, default="")
    last_deploy_run = models.ForeignKey(
        "jobs.WorkflowRun", null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        db_table = "consul_template_file"
        ordering = ["id"]


class RemoteFileRead(StandardModelMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    host = models.ForeignKey("cmdb.AssetHost", on_delete=models.CASCADE)
    worker_pool = models.ForeignKey("jobs.WorkerPool", on_delete=models.PROTECT)
    template = models.ForeignKey(
        ConsulTemplateFile, null=True, on_delete=models.SET_NULL
    )
    template_revision = models.CharField(max_length=64, blank=True)
    target_fingerprint = models.CharField(max_length=64)
    path = models.CharField(max_length=512)
    status = models.CharField(max_length=16, default="queued", db_index=True)
    exists = models.BooleanField(null=True)
    checksum = models.CharField(max_length=64, blank=True)
    content_encrypted = models.TextField(blank=True)
    size = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=256, blank=True)
    expires_at = models.DateTimeField()


class ConsulConnection(StandardModelMixin):
    name = models.CharField(max_length=128, unique=True)
    endpoint = models.CharField(max_length=512)
    datacenter = models.CharField(max_length=128, blank=True, default="")
    token_encrypted = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    description = models.CharField(max_length=512, blank=True, default="")

    class Meta:
        db_table = "consul_connection"
        ordering = ["id"]

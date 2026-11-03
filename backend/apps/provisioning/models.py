from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
import uuid

from common.models import StandardModelMixin


class ResourceTemplate(StandardModelMixin):
    name = models.CharField(max_length=128)
    provider = models.CharField(
        max_length=16, choices=[("aliyun", "阿里云"), ("tencent", "腾讯云")]
    )
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)


class ResourceTemplateVersion(StandardModelMixin):
    template = models.ForeignKey(
        ResourceTemplate, on_delete=models.PROTECT, related_name="versions"
    )
    number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16, default="draft", choices=[("draft", "草稿"), ("published", "已发布")]
    )
    constraints = models.JSONField(default=dict)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["template", "number"], name="provision_template_version"
            )
        ]

    def save(self, *args, **kwargs):
        if (
            self.pk
            and type(self).objects.filter(pk=self.pk, status="published").exists()
        ):
            raise ValidationError("已发布的资源模板版本不可修改，请新建版本")
        return super().save(*args, **kwargs)


class ProvisioningCredential(StandardModelMixin):
    source = models.ForeignKey(
        "cmdb.AssetSource",
        on_delete=models.PROTECT,
        related_name="provisioning_credentials",
    )
    name = models.CharField(max_length=128)
    encrypted_secret = models.TextField()
    revision = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)


class ProvisioningRequest(StandardModelMixin):
    name = models.CharField(max_length=128)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="provisioning_requests",
    )
    version = models.ForeignKey(ResourceTemplateVersion, on_delete=models.PROTECT)
    credential = models.ForeignKey(ProvisioningCredential, on_delete=models.PROTECT)
    region = models.CharField(max_length=64)
    parameters = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=1)
    approval_status = models.CharField(max_length=24, default="pending")
    execution_status = models.CharField(max_length=24, default="not_started")
    inventory_status = models.CharField(max_length=24, default="not_started")
    # Default policy requires a different human approver, even for superusers.
    requires_approval = models.BooleanField(default=True)
    notification_snapshot = models.JSONField(default=dict, blank=True)
    active_state_version = models.ForeignKey(
        "ProvisioningStateVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="active_requests",
    )
    state_generation = models.PositiveIntegerField(default=0)


class ProvisioningPlan(StandardModelMixin):
    request = models.ForeignKey(
        ProvisioningRequest, on_delete=models.PROTECT, related_name="plans"
    )
    revision = models.PositiveIntegerField()
    status = models.CharField(max_length=24, default="queued")
    digest = models.CharField(max_length=64, blank=True)
    input_digest = models.CharField(max_length=64, blank=True)
    credential_revision = models.PositiveIntegerField()
    source_updated_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    artifact_key = models.CharField(max_length=128, blank=True)
    summary = models.JSONField(default=list)
    error_message = models.TextField(blank=True, default="")
    resource_snapshot = models.JSONField(default=dict, blank=True)
    execution_token = models.CharField(max_length=64, blank=True, default="")
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="confirmed_resource_plans",
    )


class ProvisioningApproval(StandardModelMixin):
    plan = models.ForeignKey(
        ProvisioningPlan, on_delete=models.PROTECT, related_name="approvals"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    digest = models.CharField(max_length=64)
    decision = models.CharField(
        max_length=16, choices=[("approved", "通过"), ("rejected", "拒绝")]
    )
    comment = models.CharField(max_length=500, blank=True, default="")


class ProvisioningAttempt(StandardModelMixin):
    plan = models.OneToOneField(
        ProvisioningPlan, on_delete=models.PROTECT, related_name="attempt"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    idempotency_key = models.CharField(max_length=128)
    status = models.CharField(max_length=24, default="queued")
    instance_ids = models.JSONField(default=list)
    asset_ids = models.JSONField(default=list)
    error_message = models.TextField(blank=True, default="")
    recovery_artifact_key = models.CharField(max_length=128, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    execution_token = models.CharField(max_length=64, blank=True, default="")
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    apply_started_at = models.DateTimeField(null=True, blank=True)
    reconciliation_token = models.CharField(max_length=64, blank=True, default="")


class ProvisioningArtifact(StandardModelMixin):
    request = models.ForeignKey(
        ProvisioningRequest, on_delete=models.PROTECT, related_name="artifacts"
    )
    attempt = models.ForeignKey(
        ProvisioningAttempt, null=True, on_delete=models.PROTECT
    )
    storage = models.CharField(max_length=16, default="main")
    purpose = models.CharField(max_length=16)
    key = models.CharField(max_length=64)
    digest = models.CharField(max_length=64)
    byte_size = models.PositiveBigIntegerField(default=0)
    key_id = models.CharField(max_length=64, blank=True)
    held = models.BooleanField(default=False)
    cleanup_status = models.CharField(max_length=16, default="retained")
    expires_at = models.DateTimeField(null=True, blank=True)


class ProvisioningStateVersion(StandardModelMixin):
    request = models.ForeignKey(
        ProvisioningRequest, on_delete=models.PROTECT, related_name="state_versions"
    )
    attempt = models.ForeignKey(ProvisioningAttempt, on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    lineage = models.CharField(max_length=128)
    serial = models.PositiveBigIntegerField()
    digest = models.CharField(max_length=64)
    primary_artifact = models.ForeignKey(
        ProvisioningArtifact, on_delete=models.PROTECT, related_name="primary_states"
    )
    backup_artifact = models.ForeignKey(
        ProvisioningArtifact,
        null=True,
        on_delete=models.PROTECT,
        related_name="backup_states",
    )
    protection_status = models.CharField(max_length=16, default="pending")
    verified_at = models.DateTimeField(null=True, blank=True)
    message = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["request", "version"], name="provision_state_version"
            )
        ]


class ProvisioningRestorePreview(StandardModelMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(ProvisioningRequest, on_delete=models.PROTECT)
    state_version = models.ForeignKey(
        ProvisioningStateVersion, on_delete=models.PROTECT
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    generation = models.PositiveIntegerField()
    source_updated_at = models.DateTimeField()
    digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=16, default="pending")


class ProvisioningWorker(StandardModelMixin):
    identity = models.CharField(max_length=128, unique=True)
    epoch = models.CharField(max_length=64)
    queues = models.JSONField(default=list)
    checks = models.JSONField(default=dict)
    last_seen_at = models.DateTimeField()


class ProvisioningResolutionPreview(StandardModelMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(ProvisioningRequest, on_delete=models.PROTECT)
    attempt = models.ForeignKey(ProvisioningAttempt, on_delete=models.PROTECT)
    state_version = models.ForeignKey(
        ProvisioningStateVersion, on_delete=models.PROTECT
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    generation = models.PositiveIntegerField()
    source_updated_at = models.DateTimeField()
    digest = models.CharField(max_length=64)
    evidence = models.JSONField(default=dict)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=16, default="pending")
    evidence_reference = models.CharField(max_length=300, blank=True, default="")
    comment = models.CharField(max_length=500, blank=True, default="")
    confirmed_at = models.DateTimeField(null=True, blank=True)


class ProvisioningHealthIncident(StandardModelMixin):
    fingerprint = models.CharField(max_length=128, unique=True)
    kind = models.CharField(max_length=32)
    status = models.CharField(max_length=16, default="open")
    message = models.CharField(max_length=300)
    notification_snapshot = models.JSONField(default=dict, blank=True)


class ProvisioningEvent(StandardModelMixin):
    request = models.ForeignKey(
        ProvisioningRequest, on_delete=models.PROTECT, related_name="events"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT
    )
    kind = models.CharField(max_length=32)
    message = models.CharField(max_length=500)
    plan = models.ForeignKey(ProvisioningPlan, null=True, on_delete=models.PROTECT)

import uuid
from django.conf import settings
from django.db import models
from common.models import StandardModelMixin


def service_id():
    return "devops-" + uuid.uuid4().hex


class MonitoringTarget(StandardModelMixin):
    class Kind(models.TextChoices):
        HOST = "host", "主机"
        MYSQL = "mysql", "MySQL"
        REDIS = "redis", "Redis"
        BLACKBOX = "blackbox", "站点探测"

    name = models.CharField(max_length=128)
    connection = models.ForeignKey(
        "consul.ConsulConnection",
        on_delete=models.PROTECT,
        related_name="monitoring_targets",
    )
    host = models.ForeignKey(
        "cmdb.AssetHost",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="monitoring_targets",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.HOST)
    address = models.CharField(max_length=255)
    port = models.PositiveIntegerField(default=9100)
    service_id = models.CharField(
        max_length=64, unique=True, default=service_id, editable=False
    )
    tags = models.JSONField(default=list, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    check_enabled = models.BooleanField(default=False)
    probe_target = models.CharField(max_length=2048, blank=True, default="")
    probe_module = models.CharField(max_length=128, blank=True, default="http_2xx")
    registered = models.BooleanField(default=False)
    registration_uncertain = models.BooleanField(default=False)
    synced_at = models.DateTimeField(null=True, blank=True)
    synced_revision = models.CharField(max_length=64, blank=True, default="")
    sync_interval_minutes = models.PositiveIntegerField(default=0)
    follow_host_address = models.BooleanField(default=False)
    address_source = models.CharField(
        max_length=16,
        default="internal",
        choices=[("internal", "内网 IP"), ("external", "外网 IP")],
    )
    auto_sync_actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="automatic_monitoring_targets",
    )
    last_auto_sync_at = models.DateTimeField(null=True, blank=True)
    next_auto_sync_at = models.DateTimeField(null=True, blank=True, db_index=True)
    enrollment_policy = models.ForeignKey(
        "monitoring.EnrollmentPolicy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_targets",
    )

    class Meta:
        db_table = "monitoring_target"
        ordering = ["id"]


class SyncRecord(StandardModelMixin):
    target = models.ForeignKey(
        MonitoringTarget,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sync_records",
    )
    target_name = models.CharField(max_length=128, blank=True, default="")
    trigger = models.CharField(
        max_length=16,
        default="manual",
        choices=[("manual", "手动"), ("batch", "批量接入"), ("automatic", "定时同步")],
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    operation = models.CharField(
        max_length=16, choices=[("register", "注册"), ("deregister", "注销")]
    )
    status = models.CharField(
        max_length=16,
        default="queued",
        choices=[
            ("queued", "排队中"),
            ("running", "同步中"),
            ("succeeded", "成功"),
            ("failed", "失败"),
        ],
    )
    error = models.CharField(max_length=512, blank=True, default="")
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "monitoring_sync_record"
        ordering = ["-id"]


class EnrollmentPolicy(StandardModelMixin):
    name = models.CharField(max_length=128, unique=True)
    connection = models.ForeignKey(
        "consul.ConsulConnection",
        on_delete=models.PROTECT,
        related_name="enrollment_policies",
    )
    scope = models.CharField(
        max_length=16, default="group", choices=[("group", "主机分组"), ("rule", "匹配规则")]
    )
    group = models.ForeignKey(
        "cmdb.HostGroup", null=True, blank=True, on_delete=models.SET_NULL
    )
    include_descendants = models.BooleanField(default=True)
    match_rule = models.JSONField(default=dict, blank=True)
    address_source = models.CharField(
        max_length=16,
        default="internal",
        choices=[("internal", "内网 IP"), ("external", "外网 IP")],
    )
    port = models.PositiveIntegerField(default=9100)
    interval_minutes = models.PositiveIntegerField(default=5)
    target_sync_interval_minutes = models.PositiveIntegerField(default=5)
    follow_host_address = models.BooleanField(default=True)
    is_active = models.BooleanField(default=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    next_run_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "monitoring_enrollment_policy"
        ordering = ["id"]


class EnrollmentRun(StandardModelMixin):
    policy = models.ForeignKey(
        EnrollmentPolicy, null=True, on_delete=models.SET_NULL, related_name="runs"
    )
    policy_name = models.CharField(max_length=128)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    trigger = models.CharField(
        max_length=16, default="manual", choices=[("manual", "手动"), ("automatic", "自动")]
    )
    status = models.CharField(
        max_length=16,
        default="queued",
        choices=[
            ("queued", "排队中"),
            ("running", "执行中"),
            ("succeeded", "已处理"),
            ("failed", "失败"),
        ],
    )
    plan_digest = models.CharField(max_length=64)
    summary = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=512, blank=True, default="")
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "monitoring_enrollment_run"
        ordering = ["-id"]

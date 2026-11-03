from django.conf import settings
from django.db import models
from django.utils import timezone

from common.models import StandardModelMixin
from apps.jobs.input_secrets import ProtectedDefinitionInputsMixin


def worker_execution_kinds():
    return ["workflow", "quick_command", "playbook", "module"]


class ExecutionRequestKey(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    key = models.CharField(max_length=128)
    path = models.CharField(max_length=255)
    request_hash = models.CharField(max_length=64)
    response_encrypted = models.TextField(blank=True, default="")
    status_code = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "key", "path"], name="unique_execution_request_key")]


class WorkerPool(StandardModelMixin):
    code = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=128)
    queue_name = models.CharField(max_length=128)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    concurrency_limit = models.IntegerField(default=5)
    execution_kinds = models.JSONField(default=worker_execution_kinds)
    region = models.CharField(max_length=64, blank=True, default="", db_index=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "jobs_worker_pool"
        ordering = ["code"]


class WorkflowRun(StandardModelMixin):
    class RunDomain(models.TextChoices):
        TASK = "task", "Task system"
        OPS = "ops", "Ops system"

    class ExecutionKind(models.TextChoices):
        WORKFLOW = "workflow", "Workflow"
        QUICK_COMMAND = "quick_command", "Quick command"
        PLAYBOOK = "playbook", "Playbook"
        MODULE = "module", "Module"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        WAITING = "waiting", "Waiting"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        TIMEOUT = "timeout", "Timeout"
        CANCEL_REQUESTED = "cancel_requested", "Cancel requested"
        CANCELED = "canceled", "Canceled"

    class TriggerType(models.TextChoices):
        MANUAL = "manual", "Manual"
        API = "api", "API"
        SCHEDULED = "scheduled", "Scheduled"

    workflow_version = models.ForeignKey(
        "automation.WorkflowVersion",
        on_delete=models.SET_NULL,
        related_name="runs",
        null=True,
        blank=True,
    )
    run_domain = models.CharField(
        max_length=16,
        choices=RunDomain.choices,
        default=RunDomain.TASK,
        db_index=True,
    )
    execution_kind = models.CharField(
        max_length=32,
        choices=ExecutionKind.choices,
        default=ExecutionKind.WORKFLOW,
        db_index=True,
    )
    # 运行显示名（快速执行等场景可由用户填写或自动生成）；空则回退到工作流模板名
    name = models.CharField(max_length=128, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    trigger_type = models.CharField(
        max_length=16,
        choices=TriggerType.choices,
        default=TriggerType.MANUAL,
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_workflow_runs",
    )
    ticket = models.ForeignKey(
        "jobs.WorkflowTaskTicket",
        on_delete=models.SET_NULL,
        related_name="runs",
        null=True,
        blank=True,
    )
    input_vars = models.JSONField(default=dict, blank=True)
    secret_input_vars_encrypted = models.TextField(blank=True, default="")
    context_vars = models.JSONField(default=dict, blank=True)
    graph_snapshot = models.JSONField(default=dict, blank=True)
    failure_alert = models.JSONField(default=dict, blank=True)
    failure_alert_context = models.JSONField(default=dict, blank=True)
    execution_settings = models.JSONField(default=dict, blank=True)
    target_snapshot = models.JSONField(default=list, blank=True)
    target_selector = models.JSONField(default=dict, blank=True)
    event_sequence = models.PositiveBigIntegerField(default=0)
    worker_pool = models.ForeignKey(
        "jobs.WorkerPool",
        on_delete=models.PROTECT,
        related_name="workflow_runs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, default="")
    celery_task_id = models.CharField(max_length=255, blank=True, default="")
    worker_name = models.CharField(max_length=255, blank=True, default="")
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    timeout_seconds = models.PositiveIntegerField(default=3600)
    queue_timeout_seconds = models.PositiveIntegerField(default=120)
    queue_deadline_at = models.DateTimeField(null=True, blank=True)
    workflow_deadline_at = models.DateTimeField(null=True, blank=True)
    cancel_requested_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "jobs_workflow_run"
        ordering = ["-id"]
        indexes = [
            models.Index(
                fields=["run_domain", "status"], name="jobs_run_domain_status_idx"
            ),
            models.Index(
                fields=["run_domain", "created_at"], name="jobs_run_domain_created_idx"
            ),
        ]


class WorkflowTaskTicket(ProtectedDefinitionInputsMixin, StandardModelMixin):
    """任务单：一次创建、可反复运行的任务定义（参考流程单概念）。"""

    class HostStrategy(models.TextChoices):
        PARALLEL = "parallel", "Parallel"
        SERIAL = "serial", "Serial"
        ROLLING = "rolling", "Rolling"

    name = models.CharField(max_length=128)
    failure_alert = models.JSONField(default=None, null=True, blank=True)
    workflow_version = models.ForeignKey(
        "automation.WorkflowVersion",
        on_delete=models.SET_NULL,
        related_name="task_tickets",
        null=True,
        blank=True,
    )
    input_vars = models.JSONField(default=dict, blank=True)
    secret_input_vars_encrypted = models.TextField(blank=True, default="")
    host_ids = models.JSONField(default=list, blank=True)
    group_ids = models.JSONField(default=list, blank=True)
    tag_ids = models.JSONField(default=list, blank=True)
    worker_pool = models.ForeignKey(
        "jobs.WorkerPool",
        on_delete=models.SET_NULL,
        related_name="task_tickets",
        null=True,
        blank=True,
    )
    gateway = models.ForeignKey(
        "jobs.Gateway",
        on_delete=models.PROTECT,
        related_name="task_tickets",
        null=True,
        blank=True,
    )
    host_strategy = models.CharField(
        max_length=16,
        choices=HostStrategy.choices,
        default=None, null=True, blank=True,
    )
    forks = models.PositiveIntegerField(default=None, null=True, blank=True)
    serial_batch = models.PositiveIntegerField(default=None, null=True, blank=True)
    max_fail_percentage = models.PositiveIntegerField(default=None, null=True, blank=True)
    timeout_seconds = models.PositiveIntegerField(default=None, null=True, blank=True)
    remark = models.CharField(max_length=255, blank=True, default="")
    run_count = models.PositiveIntegerField(default=0)
    last_run = models.ForeignKey(
        WorkflowRun,
        on_delete=models.SET_NULL,
        related_name="ticket_records",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_task_tickets",
    )

    class Meta:
        db_table = "jobs_workflow_task_ticket"
        ordering = ["-id"]


class ScheduledJob(ProtectedDefinitionInputsMixin, StandardModelMixin):
    class ScheduleType(models.TextChoices):
        PERIODIC = "periodic", "Recurring by cron expression"
        ONCE = "once", "Run a single time at run_at"

    class HostStrategy(models.TextChoices):
        PARALLEL = "parallel", "Parallel"
        SERIAL = "serial", "Serial"
        ROLLING = "rolling", "Rolling"

    class OverlapPolicy(models.TextChoices):
        SKIP = "skip", "Skip while previous run is active"
        ALLOW = "allow", "Allow overlapping runs"
        QUEUE = "queue", "Queue one catch-up dispatch"

    class MisfirePolicy(models.TextChoices):
        FIRE = "fire", "Fire late"
        SKIP = "skip", "Skip overdue occurrence"

    name = models.CharField(max_length=128)
    workflow_version = models.ForeignKey(
        "automation.WorkflowVersion",
        on_delete=models.SET_NULL,
        related_name="scheduled_jobs",
        null=True,
        blank=True,
    )
    worker_pool = models.ForeignKey(
        "jobs.WorkerPool",
        on_delete=models.PROTECT,
        related_name="scheduled_jobs",
    )
    gateway = models.ForeignKey(
        "jobs.Gateway",
        on_delete=models.PROTECT,
        related_name="scheduled_jobs",
        null=True,
        blank=True,
    )
    host_ids = models.JSONField(default=list, blank=True)
    group_ids = models.JSONField(default=list, blank=True)
    tag_ids = models.JSONField(default=list, blank=True)
    cron_expression = models.CharField(max_length=128, default="0 * * * *")
    timezone = models.CharField(max_length=64, default="Asia/Shanghai")
    # 调度类型：periodic 按 cron 循环触发；once 在 run_at 触发一次后自动停用。
    schedule_type = models.CharField(
        max_length=16,
        choices=ScheduleType.choices,
        default=ScheduleType.PERIODIC,
    )
    # 一次性任务的计划执行时间（应用侧按本地时区存储，写入 beat 时转 naive-UTC）。
    run_at = models.DateTimeField(null=True, blank=True)
    # 过期时间：周期性任务超过后停止调度，一次性任务超过后取消未执行的那一次。
    expires_at = models.DateTimeField(null=True, blank=True)
    remark = models.CharField(max_length=255, blank=True, default="")
    input_vars = models.JSONField(default=dict, blank=True)
    secret_input_vars_encrypted = models.TextField(blank=True, default="")
    host_strategy = models.CharField(
        max_length=16,
        choices=HostStrategy.choices,
        default=None, null=True, blank=True,
    )
    forks = models.PositiveIntegerField(default=None, null=True, blank=True)
    serial_batch = models.PositiveIntegerField(default=None, null=True, blank=True)
    max_fail_percentage = models.PositiveIntegerField(default=None, null=True, blank=True)
    timeout_seconds = models.PositiveIntegerField(default=None, null=True, blank=True)
    queue_timeout_seconds = models.PositiveIntegerField(default=120)
    enabled = models.BooleanField(default=True)
    # 调度策略：overlap 控制上次运行未结束时本次是否派发；misfire 控制
    # 错过调度窗口（beat 停机等）超过宽限期后补跑还是跳过。
    overlap_policy = models.CharField(
        max_length=16,
        choices=OverlapPolicy.choices,
        default=OverlapPolicy.SKIP,
    )
    misfire_policy = models.CharField(
        max_length=16,
        choices=MisfirePolicy.choices,
        default=MisfirePolicy.FIRE,
    )
    misfire_grace_seconds = models.PositiveIntegerField(default=3600)
    # queue 策略下：上次运行仍活跃时标记一次补投，待其结束后派发。
    pending_dispatch = models.BooleanField(default=False)
    # 最近一次跳过原因（overlap/misfire/派发被拒），成功派发后清空。
    last_skip_reason = models.CharField(max_length=255, blank=True, default="")
    next_run_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_workflow_run = models.ForeignKey(
        WorkflowRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scheduled_job_results",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_scheduled_jobs",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_scheduled_jobs",
    )

    class Meta:
        db_table = "jobs_scheduled_job"
        ordering = ["enabled", "next_run_at", "-id"]


class NodeRun(StandardModelMixin):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"
        IGNORED = "ignored", "Ignored"
        TIMEOUT = "timeout", "Timeout"
        CANCELED = "canceled", "Canceled"

    workflow_run = models.ForeignKey(
        WorkflowRun,
        on_delete=models.CASCADE,
        related_name="node_runs",
    )
    workflow_node = models.ForeignKey(
        "automation.WorkflowNode",
        on_delete=models.SET_NULL,
        related_name="node_runs",
        null=True,
        blank=True,
    )
    command_version = models.ForeignKey(
        "automation.CommandVersion",
        on_delete=models.SET_NULL,
        related_name="node_runs",
        null=True,
        blank=True,
    )
    node_key = models.CharField(max_length=64, blank=True, default="")
    node_name = models.CharField(max_length=128, blank=True, default="")
    node_type = models.CharField(max_length=32, blank=True, default="command")
    config_snapshot = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    input_vars = models.JSONField(default=dict, blank=True)
    output_vars = models.JSONField(default=dict, blank=True)
    # ansible-runner 原生控制台输出（PLAY/TASK/RECAP），脱敏截断后存储
    console_output = models.TextField(blank=True, default="")
    attempt_count = models.PositiveIntegerField(default=0)
    celery_task_id = models.CharField(max_length=255, blank=True, default="")
    queued_at = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    exit_code = models.IntegerField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, default="")

    class Meta:
        db_table = "jobs_node_run"
        ordering = ["workflow_run_id", "id"]


class NodeRunAttempt(StandardModelMixin):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        TIMEOUT = "timeout", "Timeout"
        CANCELED = "canceled", "Canceled"

    node_run = models.ForeignKey(
        NodeRun,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    attempt = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.QUEUED
    )
    celery_task_id = models.CharField(max_length=255, blank=True, default="")
    queue_name = models.CharField(max_length=64, blank=True, default="")
    worker_name = models.CharField(max_length=255, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    exit_code = models.IntegerField(null=True, blank=True)
    output_vars = models.JSONField(default=dict, blank=True)
    failure_reason = models.TextField(blank=True, default="")

    class Meta:
        db_table = "jobs_node_run_attempt"
        ordering = ["node_run_id", "attempt"]
        unique_together = ("node_run", "attempt")


class DispatchRecord(StandardModelMixin):
    """Broker publication ledger, created in the same transaction as its business row.

    Closes the window where the database has committed but the process died
    before the on_commit callback could publish to Celery: the scanner later
    picks up pending/failed records and re-publishes; worker-side attempt
    fencing keeps a republish safe if the broker actually accepted it.
    """

    class Kind(models.TextChoices):
        WORKFLOW = "workflow", "Workflow run"
        NODE = "node", "Node run"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending publication"
        SENT = "sent", "Published"
        FAILED = "failed", "Publication failed"
        STALE = "stale", "Stale (business row no longer dispatchable)"

    kind = models.CharField(max_length=16, choices=Kind.choices)
    workflow_run = models.ForeignKey(
        "jobs.WorkflowRun",
        on_delete=models.CASCADE,
        related_name="dispatch_records",
    )
    node_run = models.ForeignKey(
        NodeRun,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="dispatch_records",
    )
    attempt = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    delivery_attempts = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True, default="")
    last_error = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "jobs_dispatch_record"
        ordering = ["id"]
        indexes = [
            models.Index(
                fields=["status", "next_retry_at"], name="jobs_dispatch_retry_idx"
            ),
        ]


class HostRunResult(StandardModelMixin):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        OK = "ok", "Ok"
        CHANGED = "changed", "Changed"
        FAILED = "failed", "Failed"
        UNREACHABLE = "unreachable", "Unreachable"
        SKIPPED = "skipped", "Skipped"
        CANCELED = "canceled", "Canceled"

    node_run = models.ForeignKey(
        NodeRun,
        on_delete=models.CASCADE,
        related_name="host_results",
    )
    host_id = models.IntegerField(null=True, blank=True)
    hostname = models.CharField(max_length=128)
    host_key = models.CharField(max_length=140)
    last_sequence = models.PositiveBigIntegerField(default=0)
    attempt = models.ForeignKey(
        NodeRunAttempt, null=True, blank=True, on_delete=models.SET_NULL
    )
    ip = models.GenericIPAddressField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    stdout = models.TextField(blank=True, default="")
    stderr = models.TextField(blank=True, default="")
    raw_event_data = models.JSONField(default=dict, blank=True)
    changed = models.BooleanField(default=False)
    rc = models.IntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    @staticmethod
    def host_key_for(host_id, hostname):
        if host_id is not None:
            return f"id:{host_id}"
        return f"name:{hostname}"

    def save(self, *args, **kwargs):
        host_key = self.host_key_for(self.host_id, self.hostname)
        if self.host_key != host_key:
            self.host_key = host_key
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"host_key"}
        return super().save(*args, **kwargs)

    class Meta:
        db_table = "jobs_host_run_result"
        ordering = ["node_run_id", "hostname"]
        constraints = [
            models.UniqueConstraint(
                fields=["node_run", "host_key"],
                name="jobs_unique_node_host_key",
            ),
        ]


class JobEventLog(StandardModelMixin):
    sequence = models.PositiveBigIntegerField()
    event_key = models.CharField(max_length=256)
    attempt = models.ForeignKey(
        NodeRunAttempt, null=True, blank=True, on_delete=models.PROTECT
    )
    workflow_run = models.ForeignKey(
        WorkflowRun,
        on_delete=models.CASCADE,
        related_name="event_logs",
    )
    node_run = models.ForeignKey(
        NodeRun,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="event_logs",
    )
    host_id = models.IntegerField(null=True, blank=True)
    event_type = models.CharField(max_length=64)
    message = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "jobs_event_log"
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["workflow_run", "sequence"], name="jobs_event_run_sequence_uniq"
            ),
            models.UniqueConstraint(
                fields=["workflow_run", "event_key"], name="jobs_event_run_key_uniq"
            ),
        ]


class RunLogChunk(StandardModelMixin):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending storage write"
        ARCHIVED = "archived", "Archived"
        FAILED = "failed", "Storage write failed"

    workflow_run = models.ForeignKey(
        WorkflowRun, on_delete=models.CASCADE, related_name="log_chunks"
    )
    sequence = models.PositiveBigIntegerField()
    storage_name = models.CharField(max_length=256, blank=True, default="")
    byte_count = models.PositiveIntegerField()
    truncated = models.BooleanField(default=False)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ARCHIVED,
        db_index=True,
    )
    last_error = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["workflow_run", "sequence"], name="jobs_log_run_sequence_uniq"
            )
        ]


class RunLogArchiveRequest(StandardModelMixin):
    """Durable archive request staged inside the event transaction.

    The encrypted, redacted output and its byte reservation commit atomically
    with the event; a Celery worker performs the storage write afterwards so
    event producers never block on storage I/O.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        STORED = "stored", "Stored"
        FAILED = "failed", "Failed"

    workflow_run = models.ForeignKey(
        WorkflowRun, on_delete=models.CASCADE, related_name="log_archive_requests"
    )
    sequence = models.PositiveBigIntegerField()
    content_encrypted = models.TextField()
    reserved_bytes = models.PositiveIntegerField(default=0)
    content_truncated = models.BooleanField(default=False)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    retry_count = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_error_type = models.CharField(max_length=128, blank=True, default="")

    class Meta:
        db_table = "jobs_run_log_archive_request"
        constraints = [
            models.UniqueConstraint(
                fields=["workflow_run", "sequence"],
                name="jobs_archive_request_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at"], name="jobs_archive_due_idx"
            )
        ]


class ScheduledJobOutcome(StandardModelMixin):
    """One dispatch outcome row per scheduled occurrence (audit trail)."""

    class Outcome(models.TextChoices):
        DISPATCHED = "dispatched", "Dispatched"
        OVERLAP_SKIPPED = "overlap_skipped", "Overlap skipped"
        OVERLAP_QUEUED = "overlap_queued", "Overlap queued"
        MISFIRE_SKIPPED = "misfire_skipped", "Misfire skipped"
        EXPIRED = "expired", "Expired"
        INVALID = "invalid", "Invalid"

    scheduled_job = models.ForeignKey(
        ScheduledJob, on_delete=models.CASCADE, related_name="outcomes"
    )
    scheduled_for = models.DateTimeField()
    outcome = models.CharField(max_length=32, choices=Outcome.choices)
    workflow_run = models.ForeignKey(
        WorkflowRun,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="schedule_outcomes",
    )
    reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "jobs_scheduled_job_outcome"
        ordering = ["-scheduled_for", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["scheduled_job", "scheduled_for"],
                name="jobs_schedule_outcome_unique",
            )
        ]


class SecurityRule(StandardModelMixin):
    class MatchMode(models.TextChoices):
        CONTAINS = "contains", "Contains"
        EXACT = "exact", "Exact"
        REGEX = "regex", "Regex"
        PREFIX = "prefix", "Prefix"

    class RiskLevel(models.TextChoices):
        FATAL = "fatal", "Fatal"
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"

    pattern = models.CharField(max_length=255)
    match_mode = models.CharField(
        max_length=16,
        choices=MatchMode.choices,
        default=MatchMode.CONTAINS,
    )
    risk_level = models.CharField(
        max_length=16,
        choices=RiskLevel.choices,
        default=RiskLevel.HIGH,
    )
    description = models.TextField(blank=True, default="")
    blocked_count = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=True)

    def matches(self, command: str) -> bool:
        if not self.enabled or not command:
            return False
        if self.match_mode == self.MatchMode.EXACT:
            return command.strip() == self.pattern.strip()
        if self.match_mode == self.MatchMode.PREFIX:
            return command.strip().startswith(self.pattern)
        if self.match_mode == self.MatchMode.REGEX:
            import re

            try:
                return re.search(self.pattern, command) is not None
            except re.error:
                return False
        return self.pattern in command

    def __str__(self):
        return self.pattern

    class Meta:
        db_table = "jobs_security_rule"
        ordering = ["-id"]


class CommandIntercept(StandardModelMixin):
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="command_intercepts",
    )
    command = models.TextField()
    target_desc = models.CharField(max_length=255, blank=True, default="")
    rule = models.ForeignKey(
        SecurityRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="intercepts",
    )
    hit_pattern = models.CharField(max_length=255, blank=True, default="")
    risk_level = models.CharField(max_length=16, blank=True, default="")

    class Meta:
        db_table = "jobs_command_intercept"
        ordering = ["-id"]


class Gateway(StandardModelMixin):
    class AuthType(models.TextChoices):
        PASSWORD = "password", "Password"
        KEY = "key", "Key"

    class Status(models.TextChoices):
        NORMAL = "normal", "Normal"
        ABNORMAL = "abnormal", "Abnormal"

    name = models.CharField(max_length=128)
    address = models.CharField(max_length=255)
    cloud = models.CharField(max_length=64, blank=True, default="")
    auth_type = models.CharField(
        max_length=16,
        choices=AuthType.choices,
        default=AuthType.PASSWORD,
    )
    username = models.CharField(max_length=64, blank=True, default="")
    secret_encrypted = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.NORMAL,
    )
    last_tested_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "jobs_gateway"
        ordering = ["-id"]

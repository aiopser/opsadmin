from django.conf import settings
from django.db import models
from django.utils import timezone

from common.models import StandardModelMixin


class CommandAtom(StandardModelMixin):
    class ResourceKind(models.TextChoices):
        COMMAND = "command", "Command"
        SCRIPT = "script", "Script"
        PLAYBOOK = "playbook", "Playbook"
        MODULE = "module", "Ansible Module"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        DISABLED = "disabled", "Disabled"

    class RiskLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    name = models.CharField(max_length=128)
    code = models.CharField(max_length=128, unique=True, db_index=True)
    category = models.CharField(max_length=128, blank=True, default="")
    resource_kind = models.CharField(
        max_length=16,
        choices=ResourceKind.choices,
        default=ResourceKind.COMMAND,
        db_index=True,
    )
    description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    risk_level = models.CharField(
        max_length=16,
        choices=RiskLevel.choices,
        default=RiskLevel.LOW,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_command_atoms",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_command_atoms",
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "automation_command_atom"
        ordering = ["name", "id"]


class CommandVersion(StandardModelMixin):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class CommandType(models.TextChoices):
        LINUX_SHELL = "linux_shell", "Linux Shell"
        WINDOWS_POWERSHELL = "windows_powershell", "Windows PowerShell"
        PYTHON = "python", "Python"
        HTTP_REQUEST = "http_request", "HTTP Request"
        ANSIBLE_MODULE = "ansible_module", "Ansible Module"
        PLAYBOOK = "playbook", "Playbook"

    command = models.ForeignKey(
        CommandAtom,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version = models.IntegerField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    command_type = models.CharField(max_length=32, choices=CommandType.choices)
    content = models.TextField()
    argument_schema = models.JSONField(default=dict, blank=True)
    default_vars = models.JSONField(default=dict, blank=True)
    timeout_seconds = models.IntegerField(default=60)
    become_enabled = models.BooleanField(default=False)
    check_mode_supported = models.BooleanField(default=False)
    output_extractors = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_command_versions",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_command_versions",
    )
    published_at = models.DateTimeField(null=True, blank=True)

    def assert_mutable(self):
        if self.status == self.Status.PUBLISHED:
            raise ValueError("Published command versions are immutable")

    def publish(self, user):
        self.status = self.Status.PUBLISHED
        self.published_by = user
        self.published_at = timezone.now()
        self.save(
            update_fields=["status", "published_by", "published_at", "updated_at"]
        )

    def archive(self):
        self.status = self.Status.ARCHIVED
        self.save(update_fields=["status", "updated_at"])

    def __str__(self):
        return f"{self.command.code}@{self.version}"

    class Meta:
        db_table = "automation_command_version"
        ordering = ["command_id", "-version"]
        unique_together = ("command", "version")


class WorkflowTemplate(StandardModelMixin):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        DISABLED = "disabled", "Disabled"

    name = models.CharField(max_length=128)
    code = models.CharField(max_length=128, unique=True, db_index=True)
    description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    owner_team = models.CharField(max_length=128, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_workflow_templates",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_workflow_templates",
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "automation_workflow_template"
        ordering = ["name", "id"]


class WorkflowVersion(StandardModelMixin):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class EditorMode(models.TextChoices):
        STEPS = "steps", "Steps"
        BPMN = "bpmn", "BPMN"

    workflow = models.ForeignKey(
        WorkflowTemplate,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version = models.IntegerField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    input_schema = models.JSONField(default=dict, blank=True)
    global_vars = models.JSONField(default=dict, blank=True)
    target_selector_schema = models.JSONField(default=dict, blank=True)
    editor_mode = models.CharField(
        max_length=16,
        choices=EditorMode.choices,
        default=EditorMode.STEPS,
    )
    bpmn_xml = models.TextField(blank=True, default="")
    graph_snapshot = models.JSONField(default=dict, blank=True)
    validation_report = models.JSONField(default=list, blank=True)
    published_hash = models.CharField(max_length=64, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_workflow_versions",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_workflow_versions",
    )
    published_at = models.DateTimeField(null=True, blank=True)

    def assert_mutable(self):
        if self.status != self.Status.DRAFT:
            raise ValueError("Only draft workflow versions can be modified")

    def publish(self, user):
        self.status = self.Status.PUBLISHED
        self.published_by = user
        self.published_at = timezone.now()
        self.save(
            update_fields=["status", "published_by", "published_at", "updated_at"]
        )

    def archive(self):
        self.status = self.Status.ARCHIVED
        self.save(update_fields=["status", "updated_at"])

    def __str__(self):
        return f"{self.workflow.code}@{self.version}"

    class Meta:
        db_table = "automation_workflow_version"
        ordering = ["workflow_id", "-version"]
        unique_together = ("workflow", "version")


class WorkflowNode(StandardModelMixin):
    class NodeType(models.TextChoices):
        START = "start", "Start"
        END = "end", "End"
        COMMAND = "command", "Command"
        SCRIPT = "script", "Script"
        PLAYBOOK = "playbook", "Playbook"
        MODULE = "module", "Ansible Module"
        API = "api", "API"
        JENKINS = "jenkins", "Jenkins"
        NOTIFY = "notify", "Notification"
        PARALLEL_GATEWAY = "parallel_gateway", "Parallel Gateway"
        PARALLEL_JOIN = "parallel_join", "Parallel Join"

    class FailurePolicy(models.TextChoices):
        STOP = "stop", "Stop workflow"
        IGNORE = "ignore", "Ignore and continue"
        RETRY = "retry", "Retry"

    class ConditionPolicy(models.TextChoices):
        ALWAYS = "always", "Always"
        ON_SUCCESS = "on_success", "On Success"
        ON_FAILURE = "on_failure", "On Failure"
        EXPRESSION = "expression", "Expression"

    workflow_version = models.ForeignKey(
        WorkflowVersion,
        on_delete=models.CASCADE,
        related_name="nodes",
    )
    node_key = models.CharField(max_length=64)
    name = models.CharField(max_length=128)
    command_version = models.ForeignKey(
        CommandVersion,
        on_delete=models.SET_NULL,
        related_name="workflow_nodes",
        null=True,
        blank=True,
    )
    node_type = models.CharField(
        max_length=32,
        choices=NodeType.choices,
        default=NodeType.COMMAND,
    )
    resource_type = models.CharField(max_length=32, blank=True, default="")
    resource_id = models.PositiveBigIntegerField(null=True, blank=True)
    config = models.JSONField(default=dict, blank=True)
    input_schema = models.JSONField(default=list, blank=True)
    output_schema = models.JSONField(default=list, blank=True)
    retry_policy = models.JSONField(default=dict, blank=True)
    failure_policy = models.CharField(
        max_length=16,
        choices=FailurePolicy.choices,
        default=FailurePolicy.STOP,
    )
    order_index = models.IntegerField(default=1)
    input_mapping = models.JSONField(default=dict, blank=True)
    condition_policy = models.CharField(
        max_length=16,
        choices=ConditionPolicy.choices,
        default=ConditionPolicy.ALWAYS,
    )
    condition_expression = models.TextField(blank=True, default="")
    on_success_next = models.CharField(max_length=64, blank=True, default="")
    on_failure_next = models.CharField(max_length=64, blank=True, default="")
    timeout_seconds = models.IntegerField(default=60)
    continue_on_error = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.workflow_version}:{self.node_key}"

    class Meta:
        db_table = "automation_workflow_node"
        ordering = ["workflow_version_id", "order_index", "id"]
        unique_together = ("workflow_version", "node_key")


class WorkflowEdge(StandardModelMixin):
    workflow_version = models.ForeignKey(
        WorkflowVersion,
        on_delete=models.CASCADE,
        related_name="edges",
    )
    edge_key = models.CharField(max_length=64)
    source_node = models.ForeignKey(
        WorkflowNode,
        on_delete=models.CASCADE,
        related_name="outgoing_edges",
    )
    target_node = models.ForeignKey(
        WorkflowNode,
        on_delete=models.CASCADE,
        related_name="incoming_edges",
    )
    condition_expression = models.TextField(blank=True, default="")
    is_default = models.BooleanField(default=False)
    order_index = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "automation_workflow_edge"
        ordering = ["workflow_version_id", "order_index", "id"]
        unique_together = ("workflow_version", "edge_key")


class ApiEndpoint(StandardModelMixin):
    class BodyType(models.TextChoices):
        NONE = "none", "None"
        JSON = "json", "JSON"
        FORM = "form", "Form"
        RAW = "raw", "Raw"

    class AuthType(models.TextChoices):
        NONE = "none", "None"
        BASIC = "basic", "Basic"
        BEARER = "bearer", "Bearer"
        API_KEY = "api_key", "API key"

    name = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")
    method = models.CharField(max_length=16, default="GET")
    url = models.URLField(max_length=2048)
    query_params = models.JSONField(default=list, blank=True)
    headers = models.JSONField(default=list, blank=True)
    cookies = models.JSONField(default=list, blank=True)
    body_type = models.CharField(
        max_length=16,
        choices=BodyType.choices,
        default=BodyType.NONE,
    )
    body = models.TextField(blank=True, default="")
    auth_type = models.CharField(
        max_length=16,
        choices=AuthType.choices,
        default=AuthType.NONE,
    )
    username = models.CharField(max_length=255, blank=True, default="")
    secret_encrypted = models.TextField(blank=True, default="")
    api_key_name = models.CharField(max_length=255, blank=True, default="")
    api_key_location = models.CharField(max_length=16, blank=True, default="header")
    success_rules = models.JSONField(default=dict, blank=True)
    output_extractors = models.JSONField(default=list, blank=True)
    timeout_seconds = models.PositiveIntegerField(default=30)
    verify_ssl = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_api_endpoints",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_api_endpoints",
    )

    class Meta:
        db_table = "automation_api_endpoint"
        ordering = ["name", "id"]


class JenkinsServer(StandardModelMixin):
    name = models.CharField(max_length=128)
    base_url = models.URLField(max_length=2048)
    username = models.CharField(max_length=255, blank=True, default="")
    token_encrypted = models.TextField(blank=True, default="")
    verify_ssl = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_jenkins_servers",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_jenkins_servers",
    )

    class Meta:
        db_table = "automation_jenkins_server"
        ordering = ["name", "id"]


class JenkinsJob(StandardModelMixin):
    server = models.ForeignKey(
        JenkinsServer, on_delete=models.CASCADE, related_name="jobs"
    )
    name = models.CharField(max_length=512)
    url = models.URLField(max_length=2048, blank=True, default="")
    color = models.CharField(max_length=32, blank=True, default="")
    parameters = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "automation_jenkins_job"
        ordering = ["server_id", "name"]
        unique_together = ("server", "name")


class JenkinsBuild(StandardModelMixin):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        ABORTED = "aborted", "Aborted"

    job = models.ForeignKey(JenkinsJob, on_delete=models.PROTECT, related_name="builds")
    workflow_run = models.ForeignKey(
        "jobs.WorkflowRun",
        on_delete=models.SET_NULL,
        related_name="jenkins_builds",
        null=True,
        blank=True,
    )
    node_run = models.ForeignKey(
        "jobs.NodeRun",
        on_delete=models.SET_NULL,
        related_name="jenkins_builds",
        null=True,
        blank=True,
    )
    build_number = models.PositiveIntegerField(null=True, blank=True)
    queue_url = models.URLField(max_length=2048, blank=True, default="")
    build_url = models.URLField(max_length=2048, blank=True, default="")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.QUEUED
    )
    result = models.CharField(max_length=32, blank=True, default="")
    parameters = models.JSONField(default=dict, blank=True)
    console_output = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "automation_jenkins_build"
        ordering = ["-id"]


class NotificationChannel(StandardModelMixin):
    class ChannelType(models.TextChoices):
        WEBHOOK = "webhook", "Webhook"
        WECOM = "wecom", "WeCom"
        DINGTALK = "dingtalk", "DingTalk"
        EMAIL = "email", "Email"

    name = models.CharField(max_length=128)
    channel_type = models.CharField(max_length=16, choices=ChannelType.choices)
    config = models.JSONField(default=dict, blank=True)
    secret_encrypted = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_notification_channels",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_notification_channels",
    )

    class Meta:
        db_table = "automation_notification_channel"
        ordering = ["name", "id"]


class NotificationTemplate(StandardModelMixin):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=128, unique=True, db_index=True)
    description = models.TextField(blank=True, default="")
    channel = models.ForeignKey(
        NotificationChannel,
        on_delete=models.PROTECT,
        related_name="templates",
    )
    subject_template = models.CharField(max_length=255, blank=True, default="")
    body_template = models.TextField()
    receiver_template = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_notification_templates",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_notification_templates",
    )

    class Meta:
        db_table = "automation_notification_template"
        ordering = ["name", "id"]


class NotificationRecord(StandardModelMixin):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.SET_NULL,
        related_name="records",
        null=True,
        blank=True,
    )
    channel = models.ForeignKey(
        NotificationChannel,
        on_delete=models.SET_NULL,
        related_name="records",
        null=True,
        blank=True,
    )
    workflow_run = models.ForeignKey(
        "jobs.WorkflowRun",
        on_delete=models.SET_NULL,
        related_name="notification_records",
        null=True,
        blank=True,
    )
    node_run = models.ForeignKey(
        "jobs.NodeRun",
        on_delete=models.SET_NULL,
        related_name="notification_records",
        null=True,
        blank=True,
    )
    subject = models.CharField(max_length=255, blank=True, default="")
    body = models.TextField(blank=True, default="")
    receivers = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True, default="")
    failure_reason = models.TextField(blank=True, default="")
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "automation_notification_record"
        ordering = ["-id"]



from apps.automation.module_fields import module_name_for
from django.db import transaction
from django.utils import timezone
from types import SimpleNamespace

import re

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .schema_serializers import ScheduleOutcomeSummarySerializer

from apps.automation.models import (
    CommandAtom,
    CommandVersion,
    WorkflowTemplate,
    WorkflowVersion,
)
from apps.cmdb.crypto import encrypt_secret
from apps.cmdb.models import AssetHost
from apps.jobs.models import WorkerPool
from apps.jobs.confirmation import request_config
from apps.cmdb.targets import (
    normalize_target_selector,
    resolve_targets,
    target_snapshot_fingerprint,
)
from .worker_pools import resolve_worker_pool
from apps.ops.workflow.events import normalize_runner_event
from common.api.serializers import StandardModelSerializer

from .models import (
    CommandIntercept,
    Gateway,
    HostRunResult,
    JobEventLog,
    NodeRun,
    NodeRunAttempt,
    ScheduledJob,
    SecurityRule,
    WorkflowRun,
    WorkflowTaskTicket,
)
from .cron import CronExpressionError, next_cron_time
from .quick_commands import (
    QUICK_WORKFLOWS,
    is_quick_command_workflow_version,
    quick_command_risk_level,
)
from .security import CommandBlockedError, check_command
from apps.jobs.application.runs import (
    InvalidQuickCommand,
    create_quick_command_run,
    create_workflow_run_from_selector,
)
from apps.jobs.execution.plan_builder import (
    INTERNAL_INPUT_VAR_KEYS,
    InvalidSourcePlaybook,
    build_source_playbook,
    _validate_version_arguments,
    resolve_module_arguments,
    serialize_module_args,
)
from common.workflow.node_types import ANSIBLE_NODE_TYPES


def validate_ansible_extra_vars(values):
    reserved = INTERNAL_INPUT_VAR_KEYS | {
        "extra_vars",
        "check_mode",
        "source_module_version_id",
        "bypass_host_gateway",
    }
    invalid = sorted(reserved.intersection(values))
    if invalid:
        raise serializers.ValidationError("以下名称由执行平台管理，请使用对应配置项：" + "、".join(invalid))
    return values


def validate_quick_resource_variables(serializer, attrs, source):
    if (
        source is not None
        and source.command_type != CommandVersion.CommandType.ANSIBLE_MODULE
    ):
        values = {
            **(source.default_vars or {}),
            **(attrs.get("inputVars") or {}),
            **attrs.get("extraVars", {}),
        }
        try:
            _validate_version_arguments(source, values)
        except ValueError as exc:
            raise serializers.ValidationError({"extraVars": str(exc)}) from exc
    if quick_command_risk_level(
        source
    ) == CommandAtom.RiskLevel.HIGH and not serializer._user_has_permission(
        "automation.command:execute_high_risk"
    ):
        raise serializers.ValidationError(
            {"extraVars": "High-risk command execution permission is required"}
        )


def _validate_definition_selector(serializer, attrs):
    selector = normalize_target_selector(
        **{
            field: attrs.get(field, getattr(serializer.instance, field, [])) or []
            for field in ("host_ids", "group_ids", "tag_ids")
        }
    )
    targets = (
        resolve_targets(
            actor=getattr(serializer.context.get("request"), "user", None),
            host_ids=selector["hostIds"],
            group_ids=selector["groupIds"],
            tag_ids=selector["tagIds"],
        )
        if any(selector.values())
        else []
    )
    for field, key in (
        ("host_ids", "hostIds"),
        ("group_ids", "groupIds"),
        ("tag_ids", "tagIds"),
    ):
        attrs[field] = selector[key]
    return targets


class WorkflowRunSerializer(StandardModelSerializer):

    failureAlert = serializers.JSONField(source="failure_alert", read_only=True)
    targetSelector = serializers.JSONField(source="target_selector", read_only=True)
    archiveStatus = serializers.SerializerMethodField()
    workflowVersionId = serializers.IntegerField(
        source="workflow_version_id", allow_null=True, read_only=True
    )
    runDomain = serializers.CharField(source="run_domain", read_only=True)
    executionKind = serializers.CharField(source="execution_kind", read_only=True)
    name = serializers.CharField(read_only=True, default="")
    triggerType = serializers.CharField(source="trigger_type", read_only=True)
    scheduledJobId = serializers.SerializerMethodField()
    scheduledJobName = serializers.SerializerMethodField()

    triggeredById = serializers.IntegerField(
        source="triggered_by_id", allow_null=True, read_only=True
    )
    ticketId = serializers.IntegerField(
        source="ticket_id", allow_null=True, read_only=True
    )
    ticketName = serializers.CharField(
        source="ticket.name", read_only=True, allow_null=True, default=None
    )
    inputVars = serializers.JSONField(source="input_vars", read_only=True)
    contextVars = serializers.JSONField(source="context_vars", read_only=True)
    graphSnapshot = serializers.JSONField(source="graph_snapshot", read_only=True)
    executionSettings = serializers.JSONField(
        source="execution_settings", read_only=True
    )
    targetSnapshot = serializers.JSONField(source="target_snapshot", read_only=True)
    eventSequence = serializers.IntegerField(source="event_sequence", read_only=True)
    workerPoolId = serializers.IntegerField(source="worker_pool_id", read_only=True)
    startedAt = serializers.DateTimeField(
        source="started_at", allow_null=True, read_only=True
    )
    finishedAt = serializers.DateTimeField(
        source="finished_at", allow_null=True, read_only=True
    )
    durationMs = serializers.IntegerField(
        source="duration_ms", allow_null=True, read_only=True
    )
    failureReason = serializers.CharField(source="failure_reason", read_only=True)
    celeryTaskId = serializers.CharField(source="celery_task_id", read_only=True)
    workerName = serializers.CharField(source="worker_name", read_only=True)
    heartbeatAt = serializers.DateTimeField(
        source="heartbeat_at", allow_null=True, read_only=True
    )
    timeoutSeconds = serializers.IntegerField(source="timeout_seconds", read_only=True)
    queueTimeoutSeconds = serializers.IntegerField(
        source="queue_timeout_seconds", read_only=True
    )
    queueDeadlineAt = serializers.DateTimeField(
        source="queue_deadline_at", allow_null=True, read_only=True
    )
    workflowDeadlineAt = serializers.DateTimeField(
        source="workflow_deadline_at", allow_null=True, read_only=True
    )
    cancelRequestedAt = serializers.DateTimeField(
        source="cancel_requested_at", allow_null=True, read_only=True
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = WorkflowRun
        fields = [
            "id",
            "name",
            "workflowVersionId",
            "runDomain",
            "executionKind",
            "status",
            "triggerType",
            "scheduledJobId",
            "scheduledJobName",
            "triggeredById",
            "ticketId",
            "ticketName",
            "inputVars",
            "contextVars",
            "graphSnapshot",
            "failureAlert",
            "executionSettings",
            "targetSnapshot",
            "targetSelector",
            "eventSequence",
            "workerPoolId",
            "startedAt",
            "finishedAt",
            "durationMs",
            "failureReason",
            "celeryTaskId",
            "workerName",
            "heartbeatAt",
            "timeoutSeconds",
            "queueTimeoutSeconds",
            "queueDeadlineAt",
            "workflowDeadlineAt",
            "cancelRequestedAt",
            "archiveStatus",
            "createdAt",
            "updatedAt",
        ]

    def get_scheduledJobId(self, obj) -> int | None:
        return (obj.input_vars or {}).get("scheduled_job_id")

    def get_scheduledJobName(self, obj) -> str:
        return (obj.input_vars or {}).get("scheduled_job_name", "")

    def get_archiveStatus(self, instance) -> str:
        statuses = set(instance.log_archive_requests.values_list("status", flat=True))
        if "failed" in statuses:
            return "failed"
        if statuses & {"pending", "processing"}:
            return "pending"
        return "stored" if statuses else "none"

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop("secret_input_vars_encrypted", None)
        representation["workflowName"] = (
            instance.name
            or (
                instance.workflow_version.workflow.name
                if instance.workflow_version
                else None
            )
            or (instance.input_vars or {}).get("name")
            or "Ansible task"
        )
        representation["workflowVersion"] = (
            instance.workflow_version.version if instance.workflow_version else None
        )
        representation["workerPoolName"] = (
            instance.worker_pool.name if instance.worker_pool else ""
        )
        representation["triggeredByName"] = (
            instance.triggered_by.username if instance.triggered_by else ""
        )
        representation["targetCount"] = len(instance.target_snapshot or [])
        representation["failedHostCount"] = HostRunResult.objects.filter(
            node_run__workflow_run=instance,
            status__in=(HostRunResult.Status.FAILED, HostRunResult.Status.UNREACHABLE),
        ).count()
        return representation


class WorkflowRunCreateSerializer(serializers.Serializer):
    allow_reserved_quick_workflow = False
    workflowVersionId = serializers.IntegerField()
    hostIds = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        allow_empty=True,
    )
    groupIds = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        allow_empty=True,
    )
    tagIds = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        allow_empty=True,
    )
    inputVars = serializers.JSONField(required=False, default=dict)
    workerPoolId = serializers.IntegerField(required=False)
    gatewayId = serializers.IntegerField(required=False, allow_null=True)
    hostStrategy = serializers.ChoiceField(
        choices=("parallel", "serial", "rolling"), required=False, allow_null=True
    )
    forks = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=100
    )
    serialBatch = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    maxFailPercentage = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=100
    )
    timeoutSeconds = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=86400
    )
    queueTimeoutSeconds = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=3600,
    )
    checkMode = serializers.BooleanField(required=False)
    expectedTargetIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False
    )
    expectedTargetFingerprint = serializers.CharField(
        required=False, min_length=64, max_length=64
    )
    expectedConfirmationFingerprint = serializers.CharField(
        required=False, min_length=64, max_length=64
    )

    def _execution_input_vars(self):
        values = self.validated_data
        mapping = {
            "hostStrategy": "host_strategy",
            "checkMode": "check_mode",
            "forks": "ansible_forks",
            "serialBatch": "serial_batch",
            "maxFailPercentage": "max_fail_percentage",
            "gatewayId": "gateway_id",
        }
        return {
            target: values[source]
            for source, target in mapping.items()
            if source in values
        }

    @staticmethod
    def _validate_input_vars(workflow_version, input_vars):
        schema = workflow_version.input_schema or []
        if isinstance(schema, dict):
            schema = schema.get("fields") or []
        if not isinstance(schema, list):
            raise serializers.ValidationError(
                {"inputVars": "Workflow input schema must be a field list"}
            )

        values = dict(input_vars or {})
        if {"gateway_id", "bypass_host_gateway"} & values.keys():
            raise serializers.ValidationError({"inputVars": "网关只能通过独立的连接网关字段配置"})
        errors = {}
        for field in schema:
            if not isinstance(field, dict):
                continue
            name = str(field.get("name") or "").strip()
            if not name:
                continue
            if name not in values and "default" in field:
                values[name] = field.get("default")
            value = values.get(name)
            if field.get("required") and value in (None, "", []):
                errors[name] = "This field is required"
                continue
            if value is None:
                continue
            field_type = field.get("type") or "string"
            if field_type == "number" and not isinstance(value, (int, float)):
                errors[name] = "A number is required"
            elif field_type == "boolean" and not isinstance(value, bool):
                errors[name] = "A boolean is required"
            elif field_type == "multiselect" and not isinstance(value, list):
                errors[name] = "A list is required"
            elif field_type in {
                "string",
                "text",
                "secret",
                "select",
                "host",
            } and not isinstance(value, (str, int, float)):
                errors[name] = "A scalar value is required"
        if errors:
            raise serializers.ValidationError({"inputVars": errors})
        return values

    def _user_has_permission(self, code):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if getattr(user, "is_superuser", False):
            return True
        if not getattr(user, "is_authenticated", False):
            return False
        return user.role.filter(
            permission__code=code, permission__is_active=True
        ).exists()

    def _validate_high_risk_permission(self, workflow_version):
        has_high_risk_node = workflow_version.nodes.filter(
            command_version__command__risk_level=CommandAtom.RiskLevel.HIGH,
        ).exists()
        if has_high_risk_node and not self._user_has_permission(
            "automation.command:execute_high_risk"
        ):
            raise serializers.ValidationError(
                {"workflowVersionId": ("流程版本包含高危命令，当前用户缺少高危命令执行权限")}
            )

    def validate(self, attrs):
        if "bypassHostGateway" in self.initial_data:
            raise serializers.ValidationError({"bypassHostGateway": "请使用连接网关字段；留空即直连"})
        try:
            workflow_version = WorkflowVersion.objects.select_related("workflow").get(
                id=attrs["workflowVersionId"]
            )
        except WorkflowVersion.DoesNotExist as exc:
            raise serializers.ValidationError({"workflowVersionId": "流程版本不存在"}) from exc

        if workflow_version.status != WorkflowVersion.Status.PUBLISHED:
            raise serializers.ValidationError({"workflowVersionId": "只能执行已发布的流程版本"})
        if (
            is_quick_command_workflow_version(workflow_version)
            and not self.allow_reserved_quick_workflow
        ):
            raise serializers.ValidationError(
                {
                    "workflowVersionId": "Reserved quick-command workflows cannot be run directly"
                }
            )
        self._validate_high_risk_permission(workflow_version)
        attrs["inputVars"] = self._validate_input_vars(
            workflow_version,
            attrs.get("inputVars") or {},
        )

        selector = normalize_target_selector(
            host_ids=attrs.get("hostIds") or [],
            group_ids=attrs.get("groupIds") or [],
            tag_ids=attrs.get("tagIds") or [],
        )
        targets = (
            resolve_targets(
                actor=getattr(self.context.get("request"), "user", None),
                host_ids=selector["hostIds"],
                group_ids=selector["groupIds"],
                tag_ids=selector["tagIds"],
            )
            if any(selector.values())
            else []
        )
        attrs["target_selector"] = selector
        attrs["hostIds"] = [target["host_id"] for target in targets]
        attrs["target_preview"] = targets
        if not targets and any(
            node.get("type") in ANSIBLE_NODE_TYPES
            for node in (workflow_version.graph_snapshot or {}).get("nodes", [])
        ):
            raise serializers.ValidationError({"hostIds": "流程包含主机执行步骤，请选择目标主机"})

        worker_pool_id = attrs.get("workerPoolId")
        # 仅显式选择池时提前校验；未选时传 None，由 _persist_run 按目标地域自动路由。
        worker_pool = (
            resolve_worker_pool(
                actor=getattr(self.context.get("request"), "user", None),
                pool_id=worker_pool_id,
                execution_kind="workflow",
            )
            if worker_pool_id is not None
            else None
        )

        gateway_id = attrs.get("gatewayId")
        if gateway_id:
            try:
                gateway = Gateway.objects.get(id=gateway_id)
            except Gateway.DoesNotExist as exc:
                raise serializers.ValidationError({"gatewayId": "所选网关不存在"}) from exc
            if gateway.status != Gateway.Status.NORMAL:
                raise serializers.ValidationError(
                    {"gatewayId": f"网关「{gateway.name}」状态异常，请先测试连接"}
                )
            if any(target["connection_type"] != "ssh" for target in targets):
                raise serializers.ValidationError({"gatewayId": "连接网关仅支持 SSH 主机"})

        attrs["workflow_version"] = workflow_version
        attrs["worker_pool"] = worker_pool
        return attrs

    def save(self, **kwargs):
        request = self.context.get("request")
        selector = self.validated_data["target_selector"]
        return create_workflow_run_from_selector(
            workflow_version=self.validated_data["workflow_version"],
            host_ids=selector["hostIds"],
            group_ids=selector["groupIds"],
            tag_ids=selector["tagIds"],
            input_vars={
                **(self.validated_data.get("inputVars") or {}),
                **self._execution_input_vars(),
            },
            worker_pool=self.validated_data["worker_pool"],
            triggered_by=getattr(request, "user", None),
            timeout_seconds=self.validated_data.get("timeoutSeconds"),
            queue_timeout_seconds=self.validated_data.get("queueTimeoutSeconds"),
            expected_target_ids=self.validated_data.get("expectedTargetIds"),
            expected_target_fingerprint=self.validated_data.get(
                "expectedTargetFingerprint"
            ),
            expected_confirmation_fingerprint=self.validated_data.get(
                "expectedConfirmationFingerprint"
            ),
            confirmation_config=request_config(self.initial_data, self.validated_data),
        )


class DefinitionInputsSerializerMixin:
    def to_representation(self, instance):
        data = super().to_representation(instance)
        from apps.jobs.input_secrets import _workflow_input_fields, REDACTED_VALUE

        key = "inputVars" if "inputVars" in data else "input_vars"
        values = dict(data.get(key) or {})
        for field in _workflow_input_fields(instance.workflow_version):
            if (
                isinstance(field, dict)
                and field.get("type") == "secret"
                and values.get(field.get("name")) not in (None, "")
            ):
                values[field["name"]] = REDACTED_VALUE
        data[key] = values
        data.pop("secret_input_vars_encrypted", None)
        return data

    def protected_inputs(self, attrs, workflow_version):
        from apps.jobs.input_secrets import (
            definition_input_values,
            protect_workflow_inputs,
        )
        from apps.jobs.application.authorization import authorize_execution

        values = definition_input_values(
            self.instance,
            workflow_version,
            attrs.get("input_vars") if "input_vars" in attrs else None,
        )
        values = WorkflowRunCreateSerializer._validate_input_vars(
            workflow_version, values
        )
        authorize_execution(
            actor=getattr(self.context.get("request"), "user", None),
            graph_snapshot=workflow_version.graph_snapshot,
            input_vars=values,
        )
        (
            attrs["input_vars"],
            attrs["secret_input_vars_encrypted"],
        ) = protect_workflow_inputs(workflow_version, values)
        return attrs


class ScheduledJobSerializer(DefinitionInputsSerializerMixin, StandardModelSerializer):
    expectedTargetIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        write_only=True,
    )
    expectedTargetFingerprint = serializers.CharField(
        required=False,
        min_length=64,
        max_length=64,
        write_only=True,
    )
    host_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False
    )
    group_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False
    )
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False
    )
    lastOutcome = serializers.SerializerMethodField()

    @extend_schema_field(ScheduleOutcomeSummarySerializer(allow_null=True))
    def get_lastOutcome(self, obj):
        outcome = obj.outcomes.first()
        if not outcome:
            return None
        return {
            "outcome": outcome.outcome,
            "reason": outcome.reason,
            "scheduledFor": outcome.scheduled_for,
            "runId": outcome.workflow_run_id,
        }

    worker_pool = serializers.PrimaryKeyRelatedField(
        queryset=WorkerPool.objects.filter(is_active=True),
        required=False,
    )
    gateway = serializers.PrimaryKeyRelatedField(
        queryset=Gateway.objects.filter(status=Gateway.Status.NORMAL),
        required=False,
        allow_null=True,
    )
    workflowName = serializers.CharField(
        source="workflow_version.workflow.name", read_only=True
    )
    workflowVersion = serializers.IntegerField(
        source="workflow_version.version", read_only=True
    )
    workerPoolName = serializers.CharField(source="worker_pool.name", read_only=True)
    lastRunId = serializers.IntegerField(source="last_workflow_run_id", read_only=True)
    lastRunStatus = serializers.CharField(
        source="last_workflow_run.status", read_only=True, allow_null=True
    )

    class Meta:
        model = ScheduledJob
        exclude = ("secret_input_vars_encrypted",)
        read_only_fields = (
            "created_by",
            "updated_by",
            "last_workflow_run",
            "last_workflow_run_id",
        )

    def validate(self, attrs):
        if "bypass_host_gateway" in self.initial_data:
            raise serializers.ValidationError(
                {"bypass_host_gateway": "请使用连接网关字段；留空即直连"}
            )
        attrs = super().validate(attrs)
        instance = self.instance
        schedule_type = attrs.get(
            "schedule_type",
            getattr(instance, "schedule_type", ScheduledJob.ScheduleType.PERIODIC),
        )
        now = timezone.now()
        if schedule_type == ScheduledJob.ScheduleType.ONCE:
            run_at = attrs.get("run_at", getattr(instance, "run_at", None))
            if run_at is None:
                raise serializers.ValidationError({"run_at": "一次性任务必须填写执行时间"})
            enabling_once = attrs.get(
                "enabled", getattr(instance, "enabled", True)
            ) and (
                instance is None
                or not instance.enabled
                or instance.schedule_type != ScheduledJob.ScheduleType.ONCE
            )
            if run_at <= now and (
                run_at != getattr(instance, "run_at", None) or enabling_once
            ):
                raise serializers.ValidationError({"run_at": "执行时间必须晚于当前时间"})
        else:
            expression = attrs.get(
                "cron_expression", getattr(instance, "cron_expression", "")
            )
            try:
                next_cron_time(
                    expression,
                    attrs.get(
                        "timezone", getattr(instance, "timezone", "Asia/Shanghai")
                    ),
                )
            except CronExpressionError as exc:
                raise serializers.ValidationError(
                    {"cron_expression": str(exc)}
                ) from exc
        expires_at = attrs.get("expires_at", getattr(instance, "expires_at", None))
        if expires_at is not None:
            if (
                expires_at != getattr(instance, "expires_at", None)
                and expires_at <= now
            ):
                raise serializers.ValidationError({"expires_at": "过期时间必须晚于当前时间"})
            if schedule_type == ScheduledJob.ScheduleType.ONCE:
                run_at = attrs.get("run_at", getattr(instance, "run_at", None))
                if run_at is not None and expires_at <= run_at:
                    raise serializers.ValidationError({"expires_at": "过期时间必须晚于执行时间"})
        input_vars = attrs.get("input_vars", getattr(self.instance, "input_vars", {}))
        if not isinstance(input_vars, dict):
            raise serializers.ValidationError({"input_vars": "流程参数必须是 JSON 对象"})
        for field in (
            "forks",
            "serial_batch",
            "timeout_seconds",
            "queue_timeout_seconds",
        ):
            value = attrs.get(field, getattr(self.instance, field, None))
            if value is not None and int(value) <= 0:
                raise serializers.ValidationError({field: "必须大于 0"})
        max_fail_percentage = attrs.get(
            "max_fail_percentage",
            getattr(self.instance, "max_fail_percentage", 0),
        )
        if max_fail_percentage is not None and not 0 <= int(max_fail_percentage) <= 100:
            raise serializers.ValidationError({"max_fail_percentage": "必须在 0 到 100 之间"})
        workflow_version = attrs.get(
            "workflow_version",
            getattr(self.instance, "workflow_version", None),
        )
        if (
            workflow_version is None
            or workflow_version.status != WorkflowVersion.Status.PUBLISHED
        ):
            raise serializers.ValidationError({"workflow_version": "只能调度已发布的流程版本"})
        self.protected_inputs(attrs, workflow_version)

        worker_pool = attrs.get(
            "worker_pool",
            getattr(self.instance, "worker_pool", None),
        )
        if worker_pool is None:
            worker_pool = WorkerPool.objects.filter(
                is_default=True,
                is_active=True,
            ).first()
            if worker_pool is not None:
                attrs["worker_pool"] = worker_pool
        if worker_pool is None or not worker_pool.is_active:
            raise serializers.ValidationError({"worker_pool": "Worker 池不存在或未启用"})

        targets = _validate_definition_selector(self, attrs)
        gateway = attrs.get("gateway", getattr(self.instance, "gateway", None))
        if gateway and gateway.status != Gateway.Status.NORMAL:
            raise serializers.ValidationError({"gateway": "连接网关已不可用"})
        if gateway and any(target["connection_type"] != "ssh" for target in targets):
            raise serializers.ValidationError({"gateway": "连接网关仅支持 SSH 主机"})
        expected_ids = attrs.pop("expectedTargetIds", None)
        expected_fingerprint = attrs.pop("expectedTargetFingerprint", None)
        if expected_ids is not None and sorted(set(expected_ids)) != [
            target["host_id"] for target in targets
        ]:
            raise serializers.ValidationError(
                {"expectedTargetIds": "目标主机发生变化，请重新预览后确认"}
            )
        if (
            expected_fingerprint is not None
            and expected_fingerprint != target_snapshot_fingerprint(targets)
        ):
            raise serializers.ValidationError(
                {"expectedTargetFingerprint": "目标连接信息发生变化，请重新预览后确认"}
            )
        return attrs

    def validate_host_ids(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("目标主机必须是 ID 列表")
        try:
            return sorted({int(host_id) for host_id in value})
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError("目标主机 ID 必须是整数") from exc


class WorkflowTaskTicketSerializer(
    DefinitionInputsSerializerMixin, StandardModelSerializer
):
    """任务单：保存一次可反复运行的任务定义，等价于 run-create 的执行参数快照。"""

    hostStrategy = serializers.ChoiceField(
        source="host_strategy",
        choices=("parallel", "serial", "rolling"),
        required=False,
        default=None,
        allow_null=True,
    )
    failureAlert = serializers.JSONField(
        source="failure_alert", required=False, allow_null=True
    )

    def validate_failureAlert(self, value):
        from apps.automation.failure_alerts import validate_failure_alert

        return validate_failure_alert(value)

    groupIds = serializers.ListField(
        source="group_ids", child=serializers.IntegerField(min_value=1), required=False
    )
    tagIds = serializers.ListField(
        source="tag_ids", child=serializers.IntegerField(min_value=1), required=False
    )
    hostIds = serializers.ListField(
        source="host_ids",
        child=serializers.IntegerField(),
        required=False,
        default=list,
        allow_empty=True,
    )
    workerPoolId = serializers.IntegerField(
        source="worker_pool_id", required=False, allow_null=True
    )
    gatewayId = serializers.IntegerField(
        source="gateway_id", required=False, allow_null=True
    )
    inputVars = serializers.JSONField(source="input_vars", required=False, default=dict)
    forks = serializers.IntegerField(
        required=False, min_value=1, max_value=100, default=None, allow_null=True
    )
    serialBatch = serializers.IntegerField(
        source="serial_batch",
        required=False,
        min_value=1,
        default=None,
        allow_null=True,
    )
    maxFailPercentage = serializers.IntegerField(
        source="max_fail_percentage",
        required=False,
        min_value=0,
        max_value=100,
        default=None,
        allow_null=True,
    )
    timeoutSeconds = serializers.IntegerField(
        source="timeout_seconds",
        required=False,
        min_value=1,
        max_value=86400,
        default=None,
        allow_null=True,
    )
    workflowVersionId = serializers.IntegerField(
        source="workflow_version_id", required=False, allow_null=True
    )
    workflowName = serializers.CharField(
        source="workflow_version.workflow.name",
        read_only=True,
        allow_null=True,
        default=None,
    )
    workflowVersion = serializers.IntegerField(
        source="workflow_version.version", read_only=True, allow_null=True, default=None
    )
    workerPoolName = serializers.CharField(
        source="worker_pool.name", read_only=True, allow_null=True, default=None
    )
    gatewayName = serializers.CharField(
        source="gateway.name", read_only=True, allow_null=True, default=None
    )
    runCount = serializers.IntegerField(source="run_count", read_only=True)
    lastRunId = serializers.IntegerField(
        source="last_run_id", read_only=True, allow_null=True
    )
    lastRunStatus = serializers.CharField(
        source="last_run.status", read_only=True, allow_null=True, default=None
    )
    lastRunStartedAt = serializers.DateTimeField(
        source="last_run.started_at", read_only=True, allow_null=True, default=None
    )
    createdByName = serializers.CharField(
        source="created_by.username", read_only=True, allow_null=True, default=None
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = WorkflowTaskTicket
        fields = (
            "id",
            "name",
            "remark",
            "workflowVersionId",
            "workflowName",
            "workflowVersion",
            "inputVars",
            "hostIds",
            "groupIds",
            "tagIds",
            "workerPoolId",
            "workerPoolName",
            "gatewayId",
            "gatewayName",
            "hostStrategy",
            "forks",
            "serialBatch",
            "maxFailPercentage",
            "timeoutSeconds",
            "failureAlert",
            "runCount",
            "lastRunId",
            "lastRunStatus",
            "lastRunStartedAt",
            "createdByName",
            "createdAt",
            "updatedAt",
        )
        read_only_fields = ("run_count", "last_run", "created_by", "updated_by")

    def _resolve_workflow_version(self, attrs):
        workflow_version_id = attrs.get(
            "workflow_version_id",
            getattr(self.instance, "workflow_version_id", None),
        )
        if workflow_version_id is None:
            raise serializers.ValidationError({"workflowVersionId": "请选择流程版本"})
        try:
            workflow_version = WorkflowVersion.objects.select_related("workflow").get(
                id=workflow_version_id
            )
        except WorkflowVersion.DoesNotExist as exc:
            raise serializers.ValidationError({"workflowVersionId": "流程版本不存在"}) from exc
        if workflow_version.status != WorkflowVersion.Status.PUBLISHED:
            raise serializers.ValidationError({"workflowVersionId": "只能选择已发布的流程版本"})
        if workflow_version.workflow.status != WorkflowTemplate.Status.PUBLISHED:
            raise serializers.ValidationError(
                {"workflowVersionId": "流程模板未启用，不能创建或编辑任务单"}
            )
        return workflow_version

    def validate(self, attrs):
        if "bypassHostGateway" in self.initial_data:
            raise serializers.ValidationError({"bypassHostGateway": "请使用连接网关字段；留空即直连"})
        attrs = super().validate(attrs)
        workflow_version = self._resolve_workflow_version(attrs)
        # 写库统一走 FK 对象，避免 attname 与 field name 同时入库冲突
        attrs.pop("workflow_version_id", None)
        attrs["workflow_version"] = workflow_version
        self.protected_inputs(attrs, workflow_version)
        targets = _validate_definition_selector(self, attrs)
        worker_pool_id = attrs.get("worker_pool_id")
        if worker_pool_id is not None:
            try:
                WorkerPool.objects.get(id=worker_pool_id)
            except WorkerPool.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"workerPoolId": "所选 Worker 池不存在"}
                ) from exc
        gateway_id = attrs.get("gateway_id")
        if gateway_id is not None:
            try:
                gateway = Gateway.objects.get(id=gateway_id)
            except Gateway.DoesNotExist as exc:
                raise serializers.ValidationError({"gatewayId": "所选网关不存在"}) from exc
            if gateway.status != Gateway.Status.NORMAL:
                raise serializers.ValidationError({"gatewayId": "连接网关已不可用"})
            if any(target["connection_type"] != "ssh" for target in targets):
                raise serializers.ValidationError({"gatewayId": "连接网关仅支持 SSH 主机"})
        return attrs


class QuickCommandRunCreateSerializer(WorkflowRunCreateSerializer):
    extraVars = serializers.DictField(
        child=serializers.JSONField(),
        required=False,
        default=dict,
        validators=[validate_ansible_extra_vars],
    )
    allow_reserved_quick_workflow = True
    workflowVersionId = None
    inputVars = None
    commandType = serializers.ChoiceField(choices=tuple(QUICK_WORKFLOWS))
    commandContent = serializers.CharField(allow_blank=False, trim_whitespace=False)
    sourceCommandVersionId = serializers.IntegerField(required=False, allow_null=True)
    gatewayId = serializers.IntegerField(required=False, allow_null=True)
    name = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=128,
        trim_whitespace=True,
    )

    def validate(self, attrs):
        source_version = None
        command_content = attrs["commandContent"]
        # 危险命令黑名单拦截（命中即记录拦截事件并拒绝下发）
        try:
            check_command(
                command_content,
                operator=getattr(self.context.get("request"), "user", None),
            )
        except CommandBlockedError as exc:
            raise serializers.ValidationError({"commandContent": str(exc)}) from exc
        source_version_id = attrs.get("sourceCommandVersionId")
        if source_version_id is not None:
            try:
                source_version = CommandVersion.objects.select_related("command").get(
                    id=source_version_id,
                    status=CommandVersion.Status.PUBLISHED,
                    command__status=CommandAtom.Status.PUBLISHED,
                )
            except CommandVersion.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {
                        "sourceCommandVersionId": "Command version does not exist or is not published"
                    }
                ) from exc
            if source_version.command_type != attrs["commandType"]:
                raise serializers.ValidationError(
                    {
                        "sourceCommandVersionId": "Command version type does not match commandType"
                    }
                )
            if source_version.content != command_content:
                raise serializers.ValidationError(
                    {
                        "commandContent": "Command content does not match source command version"
                    }
                )
        validate_quick_resource_variables(self, attrs, source_version)
        risk_level = quick_command_risk_level(source_version)

        gateway_id = attrs.get("gatewayId")
        if gateway_id:
            try:
                gateway = Gateway.objects.get(id=gateway_id)
            except Gateway.DoesNotExist as exc:
                raise serializers.ValidationError({"gatewayId": "所选网关不存在"}) from exc
            if gateway.status != Gateway.Status.NORMAL:
                raise serializers.ValidationError(
                    {"gatewayId": f"网关「{gateway.name}」状态异常，请先测试连接"}
                )
        if risk_level == CommandAtom.RiskLevel.HIGH and not self._user_has_permission(
            "automation.command:execute_high_risk"
        ):
            raise serializers.ValidationError(
                {"commandContent": "High-risk command execution permission is required"}
            )

        selector_attrs = super().validate(
            {
                **attrs,
                "workflowVersionId": self._quick_workflow_version_id(
                    attrs["commandType"]
                ),
            }
        )
        expected_os_family = (
            AssetHost.OSFamily.WINDOWS
            if attrs["commandType"] == CommandVersion.CommandType.WINDOWS_POWERSHELL
            else AssetHost.OSFamily.LINUX
        )
        if (
            AssetHost.objects.filter(
                id__in=selector_attrs["hostIds"],
            )
            .exclude(os_family=expected_os_family)
            .exists()
        ):
            label = (
                "Windows"
                if expected_os_family == AssetHost.OSFamily.WINDOWS
                else "Linux"
            )
            raise serializers.ValidationError({"hostIds": f"该命令类型只能选择 {label} 主机"})
        selector_attrs["source_command_version"] = source_version
        return selector_attrs

    @staticmethod
    def _quick_workflow_version_id(command_type):
        from .quick_commands import ensure_quick_command_workflows

        return ensure_quick_command_workflows()[command_type].id

    def save(self, **kwargs):
        request = self.context.get("request")
        extra_input_vars = {}
        if self.validated_data.get("gatewayId"):
            extra_input_vars["gateway_id"] = self.validated_data["gatewayId"]
        extra_input_vars.update(self._execution_input_vars())
        try:
            return create_quick_command_run(
                command_type=self.validated_data["commandType"],
                command_content=self.validated_data["commandContent"],
                host_ids=self.validated_data["hostIds"],
                worker_pool=self.validated_data["worker_pool"],
                triggered_by=getattr(request, "user", None),
                source_command_version_id=getattr(
                    self.validated_data["source_command_version"], "id", None
                ),
                extra_vars=self.validated_data.get("extraVars"),
                can_execute_high_risk=self._user_has_permission(
                    "automation.command:execute_high_risk"
                ),
                extra_input_vars=extra_input_vars or None,
                timeout_seconds=self.validated_data.get("timeoutSeconds"),
                name=self.validated_data.get("name"),
                expected_target_ids=self.validated_data.get("expectedTargetIds"),
                expected_target_fingerprint=self.validated_data.get(
                    "expectedTargetFingerprint"
                ),
                expected_confirmation_fingerprint=self.validated_data.get(
                    "expectedConfirmationFingerprint"
                ),
                confirmation_config=request_config(
                    self.initial_data, self.validated_data
                ),
            )
        except InvalidQuickCommand as exc:
            raise serializers.ValidationError(
                {"commandContent": "Command source or permission is no longer valid"}
            ) from exc


class NodeRunSerializer(StandardModelSerializer):
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    workflowRun = serializers.IntegerField(source="workflow_run_id", read_only=True)
    workflowNode = serializers.IntegerField(
        source="workflow_node_id", allow_null=True, read_only=True
    )
    commandVersion = serializers.IntegerField(
        source="command_version_id", allow_null=True, read_only=True
    )
    nodeKey = serializers.CharField(source="node_key", read_only=True)
    nodeName = serializers.CharField(source="node_name", read_only=True)
    nodeType = serializers.CharField(source="node_type", read_only=True)
    configSnapshot = serializers.JSONField(source="config_snapshot", read_only=True)
    inputVars = serializers.JSONField(source="input_vars", read_only=True)
    outputVars = serializers.JSONField(source="output_vars", read_only=True)
    attemptCount = serializers.IntegerField(source="attempt_count", read_only=True)
    celeryTaskId = serializers.CharField(source="celery_task_id", read_only=True)
    queuedAt = serializers.DateTimeField(
        source="queued_at", allow_null=True, read_only=True
    )
    heartbeatAt = serializers.DateTimeField(
        source="heartbeat_at", allow_null=True, read_only=True
    )
    startedAt = serializers.DateTimeField(
        source="started_at", allow_null=True, read_only=True
    )
    finishedAt = serializers.DateTimeField(
        source="finished_at", allow_null=True, read_only=True
    )
    durationMs = serializers.IntegerField(
        source="duration_ms", allow_null=True, read_only=True
    )
    exitCode = serializers.IntegerField(
        source="exit_code", allow_null=True, read_only=True
    )
    failureReason = serializers.CharField(source="failure_reason", read_only=True)
    consoleOutput = serializers.CharField(source="console_output", read_only=True)

    class Meta:
        model = NodeRun
        fields = [
            "id",
            "workflowRun",
            "workflowNode",
            "commandVersion",
            "nodeKey",
            "nodeName",
            "nodeType",
            "configSnapshot",
            "status",
            "inputVars",
            "outputVars",
            "attemptCount",
            "celeryTaskId",
            "queuedAt",
            "heartbeatAt",
            "startedAt",
            "finishedAt",
            "durationMs",
            "exitCode",
            "failureReason",
            "consoleOutput",
            "createdAt",
            "updatedAt",
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["nodeKey"] = instance.node_key or (
            instance.workflow_node.node_key if instance.workflow_node else ""
        )
        representation["nodeName"] = instance.node_name or (
            instance.workflow_node.name if instance.workflow_node else ""
        )
        command_version = instance.command_version
        representation["commandName"] = (
            command_version.command.name if command_version else ""
        )
        return representation


class NodeRunAttemptSerializer(StandardModelSerializer):
    class Meta:
        model = NodeRunAttempt
        fields = "__all__"


class HostRunResultSerializer(StandardModelSerializer):
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    nodeRun = serializers.IntegerField(source="node_run_id", read_only=True)
    hostId = serializers.IntegerField(source="host_id", allow_null=True, read_only=True)
    hostKey = serializers.CharField(source="host_key", read_only=True)
    lastSequence = serializers.IntegerField(source="last_sequence", read_only=True)
    attemptId = serializers.IntegerField(
        source="attempt_id", allow_null=True, read_only=True
    )
    rawEventData = serializers.JSONField(source="raw_event_data", read_only=True)
    exitCode = serializers.IntegerField(source="rc", read_only=True)
    startedAt = serializers.DateTimeField(
        source="started_at", allow_null=True, read_only=True
    )
    finishedAt = serializers.DateTimeField(
        source="finished_at", allow_null=True, read_only=True
    )

    class Meta:
        model = HostRunResult
        fields = [
            "id",
            "nodeRun",
            "hostId",
            "hostKey",
            "lastSequence",
            "attemptId",
            "hostname",
            "ip",
            "status",
            "stdout",
            "stderr",
            "rawEventData",
            "changed",
            "exitCode",
            "startedAt",
            "finishedAt",
            "createdAt",
            "updatedAt",
        ]


class HostRunResultSummarySerializer(HostRunResultSerializer):
    """Host list projection; output and raw runner events are fetched on demand."""

    class Meta(HostRunResultSerializer.Meta):
        fields = [
            "id",
            "hostname",
            "ip",
            "status",
            "changed",
            "exitCode",
            "startedAt",
            "finishedAt",
        ]


class JobEventLogSerializer(StandardModelSerializer):
    eventKey = serializers.CharField(source="event_key", read_only=True)
    attemptId = serializers.IntegerField(
        source="attempt_id", allow_null=True, read_only=True
    )
    workflowRun = serializers.IntegerField(source="workflow_run_id", read_only=True)
    nodeRun = serializers.IntegerField(
        source="node_run_id", allow_null=True, read_only=True
    )
    hostId = serializers.IntegerField(source="host_id", allow_null=True, read_only=True)
    eventType = serializers.CharField(source="event_type", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = JobEventLog
        fields = [
            "id",
            "sequence",
            "eventKey",
            "attemptId",
            "workflowRun",
            "nodeRun",
            "hostId",
            "eventType",
            "message",
            "payload",
            "createdAt",
            "updatedAt",
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        payload = instance.payload or {}
        raw_event = payload.get("runner_event") or {
            "event": instance.event_type,
            "event_data": payload.get("event_data") or {},
        }
        normalized = normalize_runner_event(raw_event)
        representation["normalizedEventType"] = (
            normalized.event_type if normalized else instance.event_type
        )
        representation["runnerEvent"] = raw_event
        return representation


class SecurityRuleSerializer(StandardModelSerializer):
    class Meta:
        model = SecurityRule
        fields = "__all__"

    def validate_pattern(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("规则内容不能为空")
        return value

    def validate(self, attrs):
        match_mode = attrs.get("match_mode", getattr(self.instance, "match_mode", ""))
        pattern = attrs.get("pattern", getattr(self.instance, "pattern", ""))
        if match_mode == SecurityRule.MatchMode.REGEX and pattern:
            import re

            try:
                re.compile(pattern)
            except re.error as exc:
                raise serializers.ValidationError(
                    {"pattern": f"正则表达式不合法: {exc}"}
                ) from exc
        return attrs


class CommandInterceptSerializer(StandardModelSerializer):
    operatorName = serializers.CharField(
        source="operator.username", read_only=True, default=""
    )

    class Meta:
        model = CommandIntercept
        fields = "__all__"


class GatewaySerializer(StandardModelSerializer):
    secret = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )

    class Meta:
        model = Gateway
        fields = (
            "id",
            "name",
            "address",
            "cloud",
            "auth_type",
            "username",
            "secret",
            "status",
            "last_tested_at",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        if "network" in self.initial_data:
            raise serializers.ValidationError({"network": "网关不按网段自动匹配，请在运行时显式选择"})
        return super().validate(attrs)

    def create(self, validated_data):
        secret = validated_data.pop("secret", "")
        validated_data["secret_encrypted"] = encrypt_secret(secret)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        secret = validated_data.pop("secret", None)
        if secret:
            validated_data["secret_encrypted"] = encrypt_secret(secret)
        return super().update(instance, validated_data)


class _QuickShellRunCreateSerializer(WorkflowRunCreateSerializer):
    """复用快速命令执行链创建基于 shell 通道的运行。"""

    allow_reserved_quick_workflow = True
    workflowVersionId = None
    gatewayId = serializers.IntegerField(required=False, allow_null=True)
    # 运行显示名：用户可选填写；留空由 create_quick_command_run 自动生成
    name = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=128,
        trim_whitespace=True,
    )

    @staticmethod
    def _quick_workflow_version_id():
        from .quick_commands import ensure_quick_command_workflows

        return ensure_quick_command_workflows()[
            CommandVersion.CommandType.LINUX_SHELL
        ].id

    def validate(self, attrs):
        gateway_id = attrs.get("gatewayId")
        if gateway_id:
            try:
                gateway = Gateway.objects.get(id=gateway_id)
            except Gateway.DoesNotExist as exc:
                raise serializers.ValidationError({"gatewayId": "所选网关不存在"}) from exc
            if gateway.status != Gateway.Status.NORMAL:
                raise serializers.ValidationError(
                    {"gatewayId": f"网关「{gateway.name}」状态异常，请先测试连接"}
                )
        return super().validate(attrs)

    def _gateway_extra_vars(self):
        gateway_id = self.validated_data.get("gatewayId")
        values = self._execution_input_vars()
        if gateway_id:
            values["gateway_id"] = gateway_id
        return values


class PlaybookRunCreateSerializer(_QuickShellRunCreateSerializer):
    playbookContent = serializers.CharField(trim_whitespace=False)
    playbookVersionId = serializers.IntegerField(required=False, allow_null=True)
    extraVars = serializers.DictField(
        child=serializers.JSONField(),
        required=False,
        default=dict,
        validators=[validate_ansible_extra_vars],
    )
    playbookName = serializers.CharField(required=False, allow_blank=True, default="")
    inputVars = serializers.DictField(
        child=serializers.JSONField(), required=False, default=dict
    )

    def validate(self, attrs):
        source = None
        if attrs.get("playbookVersionId"):
            source = (
                CommandVersion.objects.select_related("command")
                .filter(
                    pk=attrs["playbookVersionId"],
                    status="published",
                    command__status="published",
                    command__resource_kind="playbook",
                    command_type=CommandVersion.CommandType.PLAYBOOK,
                )
                .first()
            )
            if source is None:
                raise serializers.ValidationError(
                    {"playbookVersionId": "Playbook 版本不存在、未发布或已停用"}
                )
            if source.content != attrs["playbookContent"]:
                raise serializers.ValidationError(
                    {"playbookContent": "内容与所选资源版本不一致，请重新选择版本或切换为在线编写"}
                )
        validate_quick_resource_variables(self, attrs, source)
        try:
            build_source_playbook(
                SimpleNamespace(
                    input_vars={
                        "execution_source": "playbook",
                        "playbook_content": attrs["playbookContent"],
                    }
                )
            )
        except InvalidSourcePlaybook as exc:
            raise serializers.ValidationError(
                {"playbookContent": f"Playbook 内容无法执行: {exc}"}
            ) from exc
        selector_attrs = super().validate(
            {**attrs, "workflowVersionId": self._quick_workflow_version_id()}
        )
        selector_attrs["playbook_version"] = source
        return selector_attrs

    def save(self, **kwargs):
        request = self.context.get("request")
        return create_quick_command_run(
            command_type=CommandVersion.CommandType.LINUX_SHELL,
            command_content="ansible-playbook playbook.yml",
            resource_version=self.validated_data.get("playbook_version"),
            extra_vars=self.validated_data.get("extraVars"),
            host_ids=self.validated_data["hostIds"],
            worker_pool=self.validated_data["worker_pool"],
            triggered_by=getattr(request, "user", None),
            can_execute_high_risk=self._user_has_permission(
                "automation.command:execute_high_risk"
            ),
            extra_input_vars={
                **(self.validated_data.get("inputVars") or {}),
                "execution_source": "playbook",
                "playbook_name": self.validated_data.get("playbookName") or "Playbook",
                "playbook_content": self.validated_data["playbookContent"],
                **self._gateway_extra_vars(),
            },
            name=self.validated_data.get("name"),
            expected_target_ids=self.validated_data.get("expectedTargetIds"),
            expected_target_fingerprint=self.validated_data.get(
                "expectedTargetFingerprint"
            ),
            expected_confirmation_fingerprint=self.validated_data.get(
                "expectedConfirmationFingerprint"
            ),
            confirmation_config=request_config(self.initial_data, self.validated_data),
        )


class ModuleRunCreateSerializer(_QuickShellRunCreateSerializer):
    extraVars = serializers.DictField(
        child=serializers.JSONField(),
        required=False,
        default=dict,
        validators=[validate_ansible_extra_vars],
    )
    moduleVersionId = serializers.IntegerField(required=False)
    moduleName = serializers.CharField(required=False, trim_whitespace=True)
    moduleArgs = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )

    FREE_FORM_MODULES = frozenset({"shell", "command", "script", "raw"})

    _MODULE_NAME_PATTERN = re.compile(
        r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*){0,4}$"
    )

    def _validate_module_name(self, module_name):
        module = module_name.strip()
        if not module:
            raise serializers.ValidationError({"moduleName": "请填写 Module 名称"})
        if not self._MODULE_NAME_PATTERN.match(module):
            raise serializers.ValidationError(
                {"moduleName": "Module 名称格式不合法，示例：shell 或 ansible.builtin.yum"}
            )
        return module

    def _validate_module_args(self, module, module_args):
        if (
            module.rsplit(".", 1)[-1] in self.FREE_FORM_MODULES
            and not module_args.strip()
        ):
            raise serializers.ValidationError({"moduleArgs": "命令内容不能为空"})
        if module_args.strip():
            try:
                check_command(
                    module_args,
                    operator=getattr(self.context.get("request"), "user", None),
                )
            except CommandBlockedError as exc:
                raise serializers.ValidationError({"moduleArgs": str(exc)}) from exc
            if module.rsplit(".", 1)[
                -1
            ] not in self.FREE_FORM_MODULES or module_args.lstrip().startswith("{"):
                try:
                    resolve_module_arguments(module, module_args)
                except ValueError as exc:
                    raise serializers.ValidationError(
                        {"moduleArgs": "模块参数格式不正确，请使用 JSON 对象或 key=value，参数名不能重复"}
                    ) from exc
        return module_args

    def validate(self, attrs):
        module_version_id = attrs.get("moduleVersionId")
        module_name = attrs.get("moduleName", "").strip()
        if not module_version_id and not module_name:
            raise serializers.ValidationError("请提供 moduleVersionId 或 moduleName")
        if module_version_id and module_name:
            raise serializers.ValidationError("moduleVersionId 与 moduleName 只能二选一")
        if module_version_id:
            try:
                module_version = CommandVersion.objects.select_related("command").get(
                    id=module_version_id,
                    status=CommandVersion.Status.PUBLISHED,
                    command__status=CommandAtom.Status.PUBLISHED,
                    command__resource_kind=CommandAtom.ResourceKind.MODULE,
                    command_type=CommandVersion.CommandType.ANSIBLE_MODULE,
                )
            except CommandVersion.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"moduleVersionId": "Module 资源不存在、未发布或已停用"}
                ) from exc
            module = module_name_for(module_version)
            default_args = (module_version.default_vars or {}).get("module_args", "")
            if isinstance(default_args, dict):
                default_args = serialize_module_args(default_args)
        else:
            module_version = None
            module = self._validate_module_name(module_name)
            default_args = ""
        module_args = self._validate_module_args(
            module, attrs.get("moduleArgs", str(default_args or ""))
        )
        validate_quick_resource_variables(self, attrs, module_version)
        selector_attrs = super().validate(
            {**attrs, "workflowVersionId": self._quick_workflow_version_id()}
        )
        selector_attrs["module"] = module
        selector_attrs["moduleArgs"] = module_args
        selector_attrs["module_version"] = module_version
        return selector_attrs

    def save(self, **kwargs):
        request = self.context.get("request")
        module = self.validated_data["module"]
        module_args = self.validated_data["moduleArgs"]
        if module.rsplit(".", 1)[-1] in self.FREE_FORM_MODULES:
            command_content = module_args
        else:
            command_content = f"ansible all -m {module} -a '{module_args}'"
        module_version = self.validated_data["module_version"]
        extra_input_vars = {
            "execution_source": "module",
            "module": module,
            "module_args": module_args,
            **self._gateway_extra_vars(),
        }
        if module_version is not None:
            extra_input_vars["source_module_version_id"] = module_version.id
        return create_quick_command_run(
            command_type=CommandVersion.CommandType.LINUX_SHELL,
            command_content=command_content,
            resource_version=module_version,
            extra_vars=self.validated_data.get("extraVars"),
            host_ids=self.validated_data["hostIds"],
            worker_pool=self.validated_data["worker_pool"],
            triggered_by=getattr(request, "user", None),
            can_execute_high_risk=self._user_has_permission(
                "automation.command:execute_high_risk"
            ),
            extra_input_vars=extra_input_vars,
            name=self.validated_data.get("name"),
            expected_target_ids=self.validated_data.get("expectedTargetIds"),
            expected_target_fingerprint=self.validated_data.get(
                "expectedTargetFingerprint"
            ),
            expected_confirmation_fingerprint=self.validated_data.get(
                "expectedConfirmationFingerprint"
            ),
            confirmation_config=request_config(self.initial_data, self.validated_data),
        )


class WorkerPoolSerializer(StandardModelSerializer):
    queueName = serializers.CharField(source="queue_name")
    isDefault = serializers.BooleanField(source="is_default", required=False)
    isActive = serializers.BooleanField(source="is_active", required=False)
    concurrencyLimit = serializers.IntegerField(
        source="concurrency_limit", required=False
    )
    executionKinds = serializers.ListField(source="execution_kinds", required=False)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = WorkerPool
        fields = [
            "id",
            "code",
            "name",
            "queueName",
            "isDefault",
            "isActive",
            "concurrencyLimit",
            "executionKinds",
            "region",
            "createdAt",
            "updatedAt",
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        queue_name = str(
            attrs.get("queue_name", getattr(self.instance, "queue_name", "")) or ""
        ).strip()
        concurrency_limit = attrs.get(
            "concurrency_limit",
            getattr(self.instance, "concurrency_limit", 0),
        )
        if not queue_name:
            raise serializers.ValidationError({"queue_name": "队列名称不能为空"})
        if int(concurrency_limit or 0) <= 0:
            raise serializers.ValidationError({"concurrency_limit": "并发限制必须大于 0"})
        attrs["queue_name"] = queue_name
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        if not WorkerPool.objects.filter(is_default=True, is_active=True).exists():
            validated_data["is_default"] = True
            validated_data["is_active"] = True
        instance = super().create(validated_data)
        if instance.is_default:
            WorkerPool.objects.exclude(pk=instance.pk).update(is_default=False)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        updated = super().update(instance, validated_data)
        if updated.is_default:
            WorkerPool.objects.exclude(pk=updated.pk).update(is_default=False)
        elif not WorkerPool.objects.filter(is_default=True, is_active=True).exists():
            updated.is_default = True
            updated.is_active = True
            updated.save(update_fields=("is_default", "is_active", "updated_at"))
        return updated

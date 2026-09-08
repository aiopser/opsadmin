from types import SimpleNamespace

from rest_framework import serializers

from apps.automation.models import CommandAtom, CommandVersion, WorkflowVersion
from apps.cmdb.crypto import encrypt_secret
from apps.cmdb.models import AssetHost, HostTagBinding, WorkerPool
from apps.cmdb.targets import resolve_targets
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
)
from .cron import CronExpressionError, next_cron_time
from .quick_commands import (
    QUICK_WORKFLOWS,
    is_quick_command_workflow_version,
    quick_command_risk_level,
)
from .security import CommandBlockedError, check_command
from .services import (
    InvalidQuickCommand,
    InvalidSourcePlaybook,
    InvalidTargetHosts,
    build_source_playbook,
    create_quick_command_run,
    create_workflow_run_from_host_ids,
)


class WorkflowRunSerializer(StandardModelSerializer):
    class Meta:
        model = WorkflowRun
        fields = "__all__"

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop("secret_input_vars_encrypted", None)
        representation["workflowName"] = (
            instance.workflow_version.workflow.name
            if instance.workflow_version
            else ((instance.input_vars or {}).get("name") or "Ansible task")
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
    hostStrategy = serializers.ChoiceField(
        choices=("parallel", "serial", "rolling"),
        required=False,
    )
    forks = serializers.IntegerField(required=False, min_value=1, max_value=100)
    serialBatch = serializers.IntegerField(required=False, min_value=1)
    maxFailPercentage = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=100,
    )
    timeoutSeconds = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=86400,
    )
    queueTimeoutSeconds = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=3600,
    )
    bypassHostGateway = serializers.BooleanField(required=False, default=False)

    def _execution_input_vars(self):
        values = self.validated_data
        mapping = {
            "hostStrategy": "host_strategy",
            "forks": "ansible_forks",
            "serialBatch": "serial_batch",
            "maxFailPercentage": "max_fail_percentage",
            "bypassHostGateway": "bypass_host_gateway",
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
                {"workflowVersionId": ("工作流包含高危命令，当前用户缺少高危命令执行权限")}
            )

    def validate(self, attrs):
        try:
            workflow_version = WorkflowVersion.objects.select_related("workflow").get(
                id=attrs["workflowVersionId"]
            )
        except WorkflowVersion.DoesNotExist as exc:
            raise serializers.ValidationError(
                {"workflowVersionId": "工作流版本不存在"}
            ) from exc

        if workflow_version.status != WorkflowVersion.Status.PUBLISHED:
            raise serializers.ValidationError({"workflowVersionId": "只能执行已发布的工作流版本"})
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

        host_ids = set(attrs.get("hostIds") or [])
        group_ids = attrs.get("groupIds") or []
        tag_ids = attrs.get("tagIds") or []
        if tag_ids:
            host_ids.update(
                HostTagBinding.objects.filter(tag_id__in=tag_ids).values_list(
                    "host_id",
                    flat=True,
                )
            )
        targets = resolve_targets(
            actor=getattr(self.context.get("request"), "user", None),
            host_ids=host_ids, group_ids=group_ids,
        )
        attrs["hostIds"] = [target["host_id"] for target in targets]

        worker_pool_id = attrs.get("workerPoolId")
        if worker_pool_id:
            try:
                worker_pool = WorkerPool.objects.get(id=worker_pool_id, is_active=True)
            except WorkerPool.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"workerPoolId": "Worker 池不存在或未启用"}
                ) from exc
        else:
            worker_pool = WorkerPool.objects.filter(
                is_default=True,
                is_active=True,
            ).first()
            if not worker_pool:
                raise serializers.ValidationError({"workerPoolId": "未配置默认 Worker 池"})

        attrs["workflow_version"] = workflow_version
        attrs["worker_pool"] = worker_pool
        return attrs

    def save(self, **kwargs):
        request = self.context.get("request")
        try:
            return create_workflow_run_from_host_ids(
                workflow_version=self.validated_data["workflow_version"],
                host_ids=self.validated_data["hostIds"],
                input_vars={
                    **(self.validated_data.get("inputVars") or {}),
                    **self._execution_input_vars(),
                },
                worker_pool=self.validated_data["worker_pool"],
                triggered_by=getattr(request, "user", None),
                timeout_seconds=self.validated_data.get("timeoutSeconds"),
                queue_timeout_seconds=self.validated_data.get("queueTimeoutSeconds"),
            )
        except InvalidTargetHosts as exc:
            raise serializers.ValidationError(
                {"hostIds": "One or more target hosts are missing or inactive"}
            ) from exc


class ScheduledJobSerializer(StandardModelSerializer):
    worker_pool = serializers.PrimaryKeyRelatedField(
        queryset=WorkerPool.objects.filter(is_active=True),
        required=False,
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
        fields = "__all__"
        read_only_fields = (
            "created_by",
            "updated_by",
            "last_workflow_run",
            "last_workflow_run_id",
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        expression = attrs.get(
            "cron_expression", getattr(self.instance, "cron_expression", "")
        )
        timezone_name = attrs.get(
            "timezone", getattr(self.instance, "timezone", "Asia/Shanghai")
        )
        try:
            next_cron_time(expression, timezone_name)
        except CronExpressionError as exc:
            raise serializers.ValidationError({"cron_expression": str(exc)}) from exc
        input_vars = attrs.get("input_vars", getattr(self.instance, "input_vars", {}))
        if not isinstance(input_vars, dict):
            raise serializers.ValidationError({"input_vars": "流程参数必须是 JSON 对象"})
        for field in ("forks", "serial_batch", "timeout_seconds", "queue_timeout_seconds"):
            value = attrs.get(field, getattr(self.instance, field, None))
            if value is not None and int(value) <= 0:
                raise serializers.ValidationError({field: "必须大于 0"})
        max_fail_percentage = attrs.get(
            "max_fail_percentage",
            getattr(self.instance, "max_fail_percentage", 0),
        )
        if not 0 <= int(max_fail_percentage) <= 100:
            raise serializers.ValidationError(
                {"max_fail_percentage": "必须在 0 到 100 之间"}
            )
        workflow_version = attrs.get(
            "workflow_version",
            getattr(self.instance, "workflow_version", None),
        )
        if (
            workflow_version is None
            or workflow_version.status != WorkflowVersion.Status.PUBLISHED
        ):
            raise serializers.ValidationError({"workflow_version": "只能调度已发布的工作流版本"})
        attrs["input_vars"] = WorkflowRunCreateSerializer._validate_input_vars(
            workflow_version,
            input_vars,
        )

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

        host_ids = (
            attrs.get(
                "host_ids",
                getattr(self.instance, "host_ids", None),
            )
            or []
        )
        if not host_ids:
            raise serializers.ValidationError({"host_ids": "至少选择一台目标主机"})
        active_host_ids = set(
            AssetHost.objects.filter(
                id__in=host_ids,
                status=AssetHost.HostStatus.ACTIVE,
            ).values_list("id", flat=True)
        )
        if active_host_ids != set(host_ids):
            raise serializers.ValidationError({"host_ids": "存在无效或未启用的目标主机"})
        return attrs

    def validate_host_ids(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError("至少选择一台目标主机")
        try:
            return sorted({int(host_id) for host_id in value})
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError("目标主机 ID 必须是整数") from exc


class QuickCommandRunCreateSerializer(WorkflowRunCreateSerializer):
    allow_reserved_quick_workflow = True
    workflowVersionId = None
    inputVars = None
    commandType = serializers.ChoiceField(choices=tuple(QUICK_WORKFLOWS))
    commandContent = serializers.CharField(allow_blank=False, trim_whitespace=False)
    sourceCommandVersionId = serializers.IntegerField(required=False, allow_null=True)
    gatewayId = serializers.IntegerField(required=False, allow_null=True)

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
                can_execute_high_risk=self._user_has_permission(
                    "automation.command:execute_high_risk"
                ),
                extra_input_vars=extra_input_vars or None,
            )
        except InvalidTargetHosts as exc:
            raise serializers.ValidationError(
                {"hostIds": "One or more target hosts are missing or inactive"}
            ) from exc
        except InvalidQuickCommand as exc:
            raise serializers.ValidationError(
                {"commandContent": "Command source or permission is no longer valid"}
            ) from exc


class NodeRunSerializer(StandardModelSerializer):
    class Meta:
        model = NodeRun
        fields = "__all__"

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
    class Meta:
        model = HostRunResult
        fields = "__all__"


class JobEventLogSerializer(StandardModelSerializer):
    class Meta:
        model = JobEventLog
        fields = "__all__"

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        payload = instance.payload or {}
        raw_event = payload.get("runner_event") or {
            "event": instance.event_type,
            "event_data": payload.get("event_data") or {},
        }
        normalized = normalize_runner_event(raw_event)
        representation["normalized_event_type"] = (
            normalized.event_type if normalized else instance.event_type
        )
        representation["runner_event"] = raw_event
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
            "network",
            "auth_type",
            "username",
            "secret",
            "status",
            "last_tested_at",
            "created_at",
            "updated_at",
        )

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
    playbookContent = serializers.CharField()
    playbookName = serializers.CharField(required=False, allow_blank=True, default="")
    inputVars = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs):
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
        return selector_attrs

    def save(self, **kwargs):
        request = self.context.get("request")
        try:
            return create_quick_command_run(
                command_type=CommandVersion.CommandType.LINUX_SHELL,
                command_content="ansible-playbook playbook.yml",
                host_ids=self.validated_data["hostIds"],
                worker_pool=self.validated_data["worker_pool"],
                triggered_by=getattr(request, "user", None),
                can_execute_high_risk=self._user_has_permission(
                    "automation.command:execute_high_risk"
                ),
                extra_input_vars={
                    **(self.validated_data.get("inputVars") or {}),
                    "execution_source": "playbook",
                    "playbook_name": self.validated_data.get("playbookName")
                    or "Playbook",
                    "playbook_content": self.validated_data["playbookContent"],
                    **self._gateway_extra_vars(),
                },
            )
        except InvalidTargetHosts as exc:
            raise serializers.ValidationError(
                {"hostIds": "One or more target hosts are missing or inactive"}
            ) from exc


class ModuleRunCreateSerializer(_QuickShellRunCreateSerializer):
    moduleVersionId = serializers.IntegerField()
    moduleArgs = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=False,
    )

    FREE_FORM_MODULES = frozenset({"shell", "command", "script", "raw"})

    def validate(self, attrs):
        try:
            module_version = CommandVersion.objects.select_related("command").get(
                id=attrs["moduleVersionId"],
                status=CommandVersion.Status.PUBLISHED,
                command__status=CommandAtom.Status.PUBLISHED,
                command__resource_kind=CommandAtom.ResourceKind.MODULE,
                command_type=CommandVersion.CommandType.ANSIBLE_MODULE,
            )
        except CommandVersion.DoesNotExist as exc:
            raise serializers.ValidationError(
                {"moduleVersionId": "Module 资源不存在、未发布或已停用"}
            ) from exc
        module = module_version.content.strip()
        module_short_name = module.rsplit(".", 1)[-1]
        default_args = (module_version.default_vars or {}).get("module_args", "")
        if isinstance(default_args, dict):
            default_args = " ".join(
                f"{key}={value}" for key, value in default_args.items()
            )
        module_args = attrs.get("moduleArgs") or str(default_args or "")
        if module_short_name in self.FREE_FORM_MODULES and not module_args.strip():
            raise serializers.ValidationError({"moduleArgs": "命令内容不能为空"})
        if module_args.strip():
            try:
                check_command(
                    module_args,
                    operator=getattr(self.context.get("request"), "user", None),
                )
            except CommandBlockedError as exc:
                raise serializers.ValidationError({"moduleArgs": str(exc)}) from exc
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
        try:
            return create_quick_command_run(
                command_type=CommandVersion.CommandType.LINUX_SHELL,
                command_content=command_content,
                host_ids=self.validated_data["hostIds"],
                worker_pool=self.validated_data["worker_pool"],
                triggered_by=getattr(request, "user", None),
                can_execute_high_risk=self._user_has_permission(
                    "automation.command:execute_high_risk"
                ),
                extra_input_vars={
                    "execution_source": "module",
                    "module": module,
                    "module_args": module_args,
                    "source_module_version_id": self.validated_data["module_version"].id,
                    **self._gateway_extra_vars(),
                },
            )
        except InvalidTargetHosts as exc:
            raise serializers.ValidationError(
                {"hostIds": "One or more target hosts are missing or inactive"}
            ) from exc

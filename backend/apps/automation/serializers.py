from common.workflow.node_types import NodeType
import re

import yaml
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.cmdb.crypto import encrypt_secret, mask_secret
from common.api.serializers import StandardModelSerializer

from .models import (
    ApiEndpoint,
    CommandAtom,
    CommandVersion,
    JenkinsServer,
    JenkinsBuild,
    JenkinsJob,
    NotificationChannel,
    NotificationRecord,
    NotificationTemplate,
    WorkflowEdge,
    WorkflowNode,
    WorkflowTemplate,
    WorkflowVersion,
)


class AutomationTemplateSerializer(serializers.Serializer):
    """Common read model for executable command and workflow versions."""

    def to_representation(self, instance):
        if isinstance(instance, CommandVersion):
            return {
                "id": instance.id,
                "templateId": instance.command_id,
                "templateType": "command",
                "name": instance.command.name,
                "code": instance.command.code,
                "description": instance.command.description,
                "version": instance.version,
                "versionStatus": instance.status,
                "publishedAt": instance.published_at,
                "riskLevel": instance.command.risk_level,
                "resourceKind": instance.command.resource_kind,
                "commandType": instance.command_type,
                "argumentSchema": instance.argument_schema,
                "defaultVars": instance.default_vars,
                "timeoutSeconds": instance.timeout_seconds,
                "becomeEnabled": instance.become_enabled,
                "checkModeSupported": instance.check_mode_supported,
                "outputExtractors": instance.output_extractors,
            }
        return {
            "id": instance.id,
            "templateId": instance.workflow_id,
            "templateType": "workflow",
            "name": instance.workflow.name,
            "code": instance.workflow.code,
            "description": instance.workflow.description,
            "version": instance.version,
            "versionStatus": instance.status,
            "publishedAt": instance.published_at,
            "inputSchema": instance.input_schema,
            "globalVars": instance.global_vars,
            "targetSelectorSchema": instance.target_selector_schema,
        }


class AnsibleNodeResourceCreateSerializer(serializers.Serializer):
    resourceKind = serializers.ChoiceField(choices=CommandAtom.ResourceKind.choices)
    name = serializers.CharField(max_length=128)
    code = serializers.RegexField(r"^[A-Za-z][A-Za-z0-9_.-]*$", max_length=128)
    category = serializers.CharField(max_length=128, required=False, allow_blank=True)
    riskLevel = serializers.ChoiceField(
        choices=CommandAtom.RiskLevel.choices,
        default=CommandAtom.RiskLevel.LOW,
    )
    description = serializers.CharField(required=False, allow_blank=True)
    commandType = serializers.ChoiceField(choices=CommandVersion.CommandType.choices)
    content = serializers.CharField()
    argumentSchema = serializers.DictField(required=False, default=dict)
    defaultVars = serializers.DictField(required=False, default=dict)
    outputExtractors = serializers.ListField(required=False, default=list)
    timeoutSeconds = serializers.IntegerField(min_value=1, max_value=86400, default=60)
    becomeEnabled = serializers.BooleanField(default=False)
    checkModeSupported = serializers.BooleanField(default=False)
    publish = serializers.BooleanField(default=True)

    def validate(self, attrs):
        allowed_types = {
            CommandAtom.ResourceKind.COMMAND: {
                CommandVersion.CommandType.LINUX_SHELL,
                CommandVersion.CommandType.WINDOWS_POWERSHELL,
            },
            CommandAtom.ResourceKind.SCRIPT: {
                CommandVersion.CommandType.LINUX_SHELL,
                CommandVersion.CommandType.WINDOWS_POWERSHELL,
                CommandVersion.CommandType.PYTHON,
            },
            CommandAtom.ResourceKind.PLAYBOOK: {CommandVersion.CommandType.PLAYBOOK},
            CommandAtom.ResourceKind.MODULE: {
                CommandVersion.CommandType.ANSIBLE_MODULE
            },
        }
        if attrs["commandType"] not in allowed_types[attrs["resourceKind"]]:
            raise serializers.ValidationError({"commandType": "执行类型与节点资源类型不匹配"})
        if CommandAtom.objects.filter(code=attrs["code"]).exists():
            raise serializers.ValidationError({"code": "资源编码已经存在"})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        should_publish = validated_data.pop("publish")
        command = CommandAtom.objects.create(
            name=validated_data["name"],
            code=validated_data["code"],
            category=validated_data.get("category", ""),
            resource_kind=validated_data["resourceKind"],
            description=validated_data.get("description", ""),
            risk_level=validated_data["riskLevel"],
            status=(
                CommandAtom.Status.PUBLISHED
                if should_publish
                else CommandAtom.Status.DRAFT
            ),
            created_by=user,
            updated_by=user,
        )
        version = CommandVersion.objects.create(
            command=command,
            version=1,
            status=(
                CommandVersion.Status.PUBLISHED
                if should_publish
                else CommandVersion.Status.DRAFT
            ),
            command_type=validated_data["commandType"],
            content=validated_data["content"],
            argument_schema=validated_data.get("argumentSchema", {}),
            default_vars=validated_data.get("defaultVars", {}),
            output_extractors=validated_data.get("outputExtractors", []),
            timeout_seconds=validated_data["timeoutSeconds"],
            become_enabled=validated_data["becomeEnabled"],
            check_mode_supported=validated_data["checkModeSupported"],
            created_by=user,
            published_by=user if should_publish else None,
            published_at=timezone.now() if should_publish else None,
        )
        return command, version


class CommandAtomSerializer(StandardModelSerializer):
    class Meta:
        model = CommandAtom
        fields = "__all__"

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["latestVersion"] = (
            instance.versions.order_by("-version")
            .values_list("version", flat=True)
            .first()
        )
        representation["publishedVersion"] = (
            instance.versions.filter(status=CommandVersion.Status.PUBLISHED)
            .values_list("version", flat=True)
            .first()
        )
        representation["versionCount"] = getattr(
            instance, "version_count", instance.versions.count()
        )
        representation["runCount"] = getattr(instance, "run_count", 0)
        representation["lastRunAt"] = getattr(instance, "last_run_at", None)
        latest = instance.versions.order_by("-version").first()
        representation["nodeCount"] = latest.workflow_nodes.count() if latest else 0
        return representation


class CommandVersionSerializer(StandardModelSerializer):
    class Meta:
        model = CommandVersion
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        command = attrs.get("command") or getattr(self.instance, "command", None)
        command_type = attrs.get(
            "command_type", getattr(self.instance, "command_type", None)
        )
        allowed_types = {
            CommandAtom.ResourceKind.COMMAND: {
                CommandVersion.CommandType.LINUX_SHELL,
                CommandVersion.CommandType.WINDOWS_POWERSHELL,
            },
            CommandAtom.ResourceKind.SCRIPT: {
                CommandVersion.CommandType.LINUX_SHELL,
                CommandVersion.CommandType.WINDOWS_POWERSHELL,
                CommandVersion.CommandType.PYTHON,
            },
            CommandAtom.ResourceKind.PLAYBOOK: {
                CommandVersion.CommandType.PLAYBOOK,
            },
            CommandAtom.ResourceKind.MODULE: {
                CommandVersion.CommandType.ANSIBLE_MODULE,
            },
        }
        if command and command_type not in allowed_types[command.resource_kind]:
            raise serializers.ValidationError({"command_type": "执行类型与节点资源分类不匹配"})
        content = str(
            attrs.get("content", getattr(self.instance, "content", "")) or ""
        ).strip()
        if not content:
            raise serializers.ValidationError({"content": "执行内容不能为空"})

        argument_schema = attrs.get(
            "argument_schema", getattr(self.instance, "argument_schema", {})
        )
        default_vars = attrs.get(
            "default_vars", getattr(self.instance, "default_vars", {})
        )
        output_extractors = attrs.get(
            "output_extractors", getattr(self.instance, "output_extractors", [])
        )
        timeout_seconds = attrs.get(
            "timeout_seconds", getattr(self.instance, "timeout_seconds", 60)
        )
        if not isinstance(argument_schema, dict):
            raise serializers.ValidationError(
                {"argument_schema": "参数 Schema 必须是 JSON 对象"}
            )
        if not isinstance(default_vars, dict):
            raise serializers.ValidationError({"default_vars": "默认变量必须是 JSON 对象"})
        if not isinstance(output_extractors, list):
            raise serializers.ValidationError(
                {"output_extractors": "输出提取规则必须是 JSON 数组"}
            )
        for index, extractor in enumerate(output_extractors):
            if (
                not isinstance(extractor, dict)
                or not str(extractor.get("name") or "").strip()
            ):
                raise serializers.ValidationError(
                    {"output_extractors": f"第 {index + 1} 条提取规则缺少 name"}
                )
            pattern = str(extractor.get("pattern") or "")
            if not pattern:
                raise serializers.ValidationError(
                    {"output_extractors": f"第 {index + 1} 条提取规则缺少 pattern"}
                )
            try:
                re.compile(pattern)
            except re.error as exc:
                raise serializers.ValidationError(
                    {"output_extractors": f"第 {index + 1} 条正则表达式无效：{exc}"}
                ) from exc
        if int(timeout_seconds or 0) <= 0:
            raise serializers.ValidationError({"timeout_seconds": "执行超时必须大于 0"})

        if command and command.resource_kind == CommandAtom.ResourceKind.PLAYBOOK:
            try:
                plays = yaml.safe_load(content)
            except yaml.YAMLError as exc:
                raise serializers.ValidationError(
                    {"content": f"Playbook YAML 解析失败：{exc}"}
                ) from exc
            if isinstance(plays, dict):
                plays = [plays]
            if (
                not isinstance(plays, list)
                or not plays
                or not all(isinstance(play, dict) for play in plays)
            ):
                raise serializers.ValidationError(
                    {"content": "Playbook 必须是非空的 play 列表"}
                )
        if command and command.resource_kind == CommandAtom.ResourceKind.MODULE:
            if not re.fullmatch(r"[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*", content):
                raise serializers.ValidationError(
                    {"content": "请输入合法的 Ansible Module 名称"}
                )
            module_args = default_vars.get("module_args", {})
            if not isinstance(module_args, (dict, str)):
                raise serializers.ValidationError(
                    {"default_vars": "module_args 必须是 JSON 对象或参数字符串"}
                )
        return attrs

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["commandName"] = (
            instance.command.name if instance.command else ""
        )
        representation["commandCode"] = (
            instance.command.code if instance.command else ""
        )
        representation["commandDescription"] = (
            instance.command.description if instance.command else ""
        )
        representation["commandCategory"] = (
            instance.command.category if instance.command else ""
        )
        representation["resourceKind"] = (
            instance.command.resource_kind if instance.command else "command"
        )
        return representation


class WorkflowTemplateSerializer(StandardModelSerializer):
    class Meta:
        model = WorkflowTemplate
        fields = "__all__"

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["latestVersion"] = (
            instance.versions.order_by("-version")
            .values_list("version", flat=True)
            .first()
        )
        representation["publishedVersion"] = (
            instance.versions.filter(status=WorkflowVersion.Status.PUBLISHED)
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
        )
        representation["draftVersion"] = (
            instance.versions.filter(status=WorkflowVersion.Status.DRAFT)
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
        )
        return representation


class WorkflowVersionSerializer(StandardModelSerializer):
    """Full camelCase contract: input and output both use camelCase keys."""

    editorMode = serializers.ChoiceField(
        source="editor_mode", choices=WorkflowVersion.EditorMode.choices, required=False
    )
    inputSchema = serializers.JSONField(source="input_schema", required=False)
    globalVars = serializers.JSONField(source="global_vars", required=False)
    targetSelectorSchema = serializers.JSONField(
        source="target_selector_schema", required=False
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    graphSnapshot = serializers.JSONField(source="graph_snapshot", read_only=True)
    validationReport = serializers.JSONField(source="validation_report", read_only=True)
    publishedHash = serializers.CharField(source="published_hash", read_only=True)
    createdBy = serializers.PrimaryKeyRelatedField(source="created_by", read_only=True)
    publishedBy = serializers.PrimaryKeyRelatedField(source="published_by", read_only=True)
    publishedAt = serializers.DateTimeField(source="published_at", read_only=True)

    def validate(self, attrs):
        if any(key in self.initial_data for key in ("bpmnXml", "bpmn_xml")):
            raise serializers.ValidationError(
                "BPMN XML is not supported; submit the graph protocol"
            )
        return super().validate(attrs)

    class Meta:
        model = WorkflowVersion
        fields = [
            "id", "createdAt", "updatedAt", "workflow", "version", "status",
            "inputSchema", "globalVars", "targetSelectorSchema", "editorMode",
            "graphSnapshot", "validationReport", "publishedHash", "createdBy",
            "publishedBy", "publishedAt",
        ]
        read_only_fields = (
            "status",
            "graphSnapshot",
            "validationReport",
            "publishedHash",
            "createdBy",
            "publishedBy",
            "publishedAt",
        )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["workflowName"] = (
            instance.workflow.name if instance.workflow else ""
        )
        representation["workflowCode"] = (
            instance.workflow.code if instance.workflow else ""
        )
        return representation


class WorkflowNodeSerializer(StandardModelSerializer):
    class Meta:
        model = WorkflowNode
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        node_type = attrs.get("node_type", getattr(self.instance, "node_type", ""))
        config = attrs.get("config", getattr(self.instance, "config", {})) or {}
        if node_type not in {
            NodeType.COMMAND,
            NodeType.SCRIPT,
            NodeType.PLAYBOOK,
            NodeType.MODULE,
        }:
            return attrs
        if not isinstance(config, dict):
            raise serializers.ValidationError({"config": "节点配置必须是 JSON 对象"})
        strategy = config.get("hostStrategy", "parallel")
        if strategy not in {"parallel", "serial", "rolling"}:
            raise serializers.ValidationError(
                {"config": "hostStrategy 必须是 parallel、serial 或 rolling"}
            )
        try:
            invalid_positive = next(
                (
                    key
                    for key in ("forks", "serialBatch")
                    if key in config and int(config[key]) <= 0
                ),
                None,
            )
            max_fail_percentage = int(config.get("maxFailPercentage", 0))
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError({"config": "执行策略数值参数必须是整数"}) from exc
        if invalid_positive:
            raise serializers.ValidationError({"config": f"{invalid_positive} 必须大于 0"})
        if not 0 <= max_fail_percentage <= 100:
            raise serializers.ValidationError(
                {"config": "maxFailPercentage 必须在 0 到 100 之间"}
            )
        return attrs

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["commandName"] = (
            instance.command_version.command.name if instance.command_version else ""
        )
        return representation


class WorkflowEdgeSerializer(StandardModelSerializer):
    class Meta:
        model = WorkflowEdge
        fields = "__all__"


class EncryptedResourceSerializer(StandardModelSerializer):
    secret = serializers.CharField(write_only=True, required=False, allow_blank=True)

    secret_model_field = "secret_encrypted"

    def create(self, validated_data):
        secret = validated_data.pop("secret", "")
        if secret:
            validated_data[self.secret_model_field] = encrypt_secret(secret)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        secret = validated_data.pop("secret", None)
        if secret:
            validated_data[self.secret_model_field] = encrypt_secret(secret)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop(self.secret_model_field, None)
        representation["secret"] = mask_secret(
            getattr(instance, self.secret_model_field, "")
        )
        return representation


class ApiEndpointSerializer(EncryptedResourceSerializer):
    class Meta:
        model = ApiEndpoint
        fields = "__all__"
        extra_kwargs = {"secret_encrypted": {"write_only": True}}

    def validate_method(self, value):
        method = str(value or "").upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
            raise serializers.ValidationError("不支持的 HTTP 方法")
        return method

    def validate_output_extractors(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("输出提取规则必须是数组")
        names = set()
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                raise serializers.ValidationError(f"第 {index + 1} 条输出提取规则格式错误")
            name = str(item.get("name") or "").strip()
            path = str(item.get("path") or "").strip()
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
                raise serializers.ValidationError(f"第 {index + 1} 条变量名不合法")
            if not path:
                raise serializers.ValidationError(f"第 {index + 1} 条响应路径不能为空")
            if name in names:
                raise serializers.ValidationError(f"输出变量 {name} 重复")
            names.add(name)
        return value


class JenkinsServerSerializer(EncryptedResourceSerializer):
    secret_model_field = "token_encrypted"

    class Meta:
        model = JenkinsServer
        fields = "__all__"
        extra_kwargs = {"token_encrypted": {"write_only": True}}


class JenkinsJobSerializer(StandardModelSerializer):
    serverName = serializers.CharField(source="server.name", read_only=True)

    class Meta:
        model = JenkinsJob
        fields = "__all__"


class JenkinsBuildSerializer(StandardModelSerializer):
    jobName = serializers.CharField(source="job.name", read_only=True)
    serverName = serializers.CharField(source="job.server.name", read_only=True)
    workflowRunId = serializers.IntegerField(source="workflow_run_id", read_only=True)
    nodeRunId = serializers.IntegerField(source="node_run_id", read_only=True)

    class Meta:
        model = JenkinsBuild
        fields = "__all__"


class NotificationChannelSerializer(EncryptedResourceSerializer):
    class Meta:
        model = NotificationChannel
        fields = "__all__"
        extra_kwargs = {"secret_encrypted": {"write_only": True}}


class NotificationTemplateSerializer(StandardModelSerializer):
    channelName = serializers.CharField(source="channel.name", read_only=True)
    channelType = serializers.CharField(source="channel.channel_type", read_only=True)

    class Meta:
        model = NotificationTemplate
        fields = "__all__"
        read_only_fields = ("created_by", "updated_by")


class NotificationRecordSerializer(StandardModelSerializer):
    templateName = serializers.CharField(source="template.name", read_only=True)
    channelName = serializers.CharField(source="channel.name", read_only=True)
    workflowRunId = serializers.IntegerField(source="workflow_run_id", read_only=True)
    nodeRunId = serializers.IntegerField(source="node_run_id", read_only=True)

    class Meta:
        model = NotificationRecord
        fields = "__all__"

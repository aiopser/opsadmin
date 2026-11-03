from .module_fields import legacy_parameter_docs, module_name_for, parameter_docs_for
from common.workflow.node_types import NodeType
import re
import yaml
from urllib.parse import urlparse
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.cmdb.crypto import encrypt_secret, mask_secret
from common.api.serializers import StandardModelSerializer

from .models import (
    ApiEndpoint,
    CommandAtom,
    CommandVersion,
    GitRepository,
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


class ModuleParameterDocSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField()


@extend_schema_field(ModuleParameterDocSerializer(many=True))
class ModuleParameterDocsField(serializers.JSONField):
    """Document note rows without coercing their runtime JSON values."""


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
                "moduleName": module_name_for(instance)
                if instance.command_type == "ansible_module"
                else "",
                "parameterDocs": parameter_docs_for(instance)
                if instance.command_type == "ansible_module"
                else [],
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
    content = serializers.CharField(required=False, allow_blank=True, default="")
    moduleName = serializers.CharField(required=False, allow_blank=True, max_length=255)
    parameterDocs = ModuleParameterDocsField(required=False)
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
        if attrs["resourceKind"] == CommandAtom.ResourceKind.MODULE:
            if (
                attrs.get("moduleName")
                and attrs["content"].strip()
                and attrs["moduleName"] != attrs["content"].strip()
            ):
                raise serializers.ValidationError(
                    {"content": "Module 请使用 moduleName，不要传入其他正文"}
                )
            module_name = str(attrs.get("moduleName") or attrs["content"]).strip()
            if not re.fullmatch(r"[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*", module_name):
                raise serializers.ValidationError(
                    {"moduleName": "请输入合法的 Ansible Module 名称"}
                )
            attrs["moduleName"] = module_name
            attrs["parameterDocs"] = CommandVersionSerializer._module_notes(
                attrs.get(
                    "parameterDocs",
                    legacy_parameter_docs(attrs.get("argumentSchema", {})),
                ),
                "parameterDocs",
            )
        elif attrs.get("moduleName") or attrs.get("parameterDocs"):
            raise serializers.ValidationError({"moduleName": "仅 Module 资源使用模块名称与参数说明"})
        elif not attrs["content"].strip():
            raise serializers.ValidationError({"content": "执行内容不能为空"})
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
            content=""
            if validated_data["resourceKind"] == "module"
            else validated_data["content"],
            module_name=validated_data.get("moduleName", ""),
            parameter_docs=validated_data.get("parameterDocs", []),
            argument_schema={}
            if validated_data["resourceKind"] == "module"
            else validated_data.get("argumentSchema", {}),
            default_vars={}
            if validated_data["resourceKind"] == "module"
            else validated_data.get("defaultVars", {}),
            output_extractors=[]
            if validated_data["resourceKind"] == "module"
            else validated_data.get("outputExtractors", []),
            timeout_seconds=60
            if validated_data["resourceKind"] == "module"
            else validated_data["timeoutSeconds"],
            become_enabled=validated_data["resourceKind"] != "module"
            and validated_data["becomeEnabled"],
            check_mode_supported=validated_data["resourceKind"] != "module"
            and validated_data["checkModeSupported"],
            created_by=user,
            published_by=user if should_publish else None,
            published_at=timezone.now() if should_publish else None,
        )
        return command, version


class CommandAtomSerializer(StandardModelSerializer):
    publishedModuleName = serializers.CharField(read_only=True, allow_null=True)
    createdByName = serializers.CharField(
        source="created_by.username", read_only=True, allow_null=True, default=None
    )

    class Meta:
        model = CommandAtom
        fields = "__all__"

    def validate_code(self, value):
        # 编码是业务唯一标识与审计锚点，资源发布后锁定不可修改
        if (
            self.instance is not None
            and self.instance.status != CommandAtom.Status.DRAFT
            and value != self.instance.code
        ):
            raise serializers.ValidationError("资源已发布，编码不可修改")
        return value

    def validate_status(self, value):
        if self.instance is None or value == self.instance.status:
            return value
        if (
            value == CommandAtom.Status.DRAFT
            and self.instance.status != CommandAtom.Status.DRAFT
        ):
            raise serializers.ValidationError("已发布或停用的资源不能退回草稿状态")
        if (
            value == CommandAtom.Status.PUBLISHED
            and not self.instance.versions.filter(
                status=CommandVersion.Status.PUBLISHED
            ).exists()
        ):
            raise serializers.ValidationError("资源没有已发布版本，不能启用")
        return value

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["latestVersion"] = (
            instance.versions.order_by("-version")
            .values_list("version", flat=True)
            .first()
        )
        published = (
            instance.versions.filter(status=CommandVersion.Status.PUBLISHED)
            .order_by("-version")
            .first()
        )
        representation["publishedVersion"] = published.version if published else None
        draft = (
            instance.versions.filter(status=CommandVersion.Status.DRAFT)
            .order_by("-version")
            .first()
        )
        representation["draftVersion"] = draft.version if draft else None
        representation["publishedContent"] = published.content if published else None
        representation["publishedModuleName"] = (
            module_name_for(published)
            if published and instance.resource_kind == "module"
            else None
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
    parameter_docs = ModuleParameterDocsField(required=False)

    class Meta:
        model = CommandVersion
        fields = "__all__"

    @staticmethod
    def _module_notes(value, field="parameter_docs"):
        if not isinstance(value, list):
            raise serializers.ValidationError({field: "参数说明必须是列表"})
        notes = []
        names = set()
        for row in value:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("name"), str)
                or not isinstance(row.get("description"), str)
            ):
                raise serializers.ValidationError({field: "请填写参数名和参数说明"})
            name, description = row["name"].strip(), row["description"].strip()
            if not name or not description:
                raise serializers.ValidationError({field: "请填写参数名和参数说明"})
            if name in names:
                raise serializers.ValidationError({field: f"参数名「{name}」重复"})
            names.add(name)
            notes.append({"name": name, "description": description})
        return notes

    def validate(self, attrs):
        attrs = super().validate(attrs)
        status = attrs.get("status")
        if status is not None and status != CommandVersion.Status.DRAFT:
            raise serializers.ValidationError({"status": "请通过发布或归档操作变更版本状态"})
        if self.instance is not None:
            if "command" in attrs and attrs["command"].pk != self.instance.command_id:
                raise serializers.ValidationError({"command": "版本所属资源不可修改"})
            if "version" in attrs and attrs["version"] != self.instance.version:
                raise serializers.ValidationError({"version": "版本号不可修改"})
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
        if command_type != CommandVersion.CommandType.ANSIBLE_MODULE and not content:
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
            if "module_name" in attrs:
                module_name = str(attrs["module_name"] or "").strip()
            elif "content" in attrs:
                module_name = content
            else:
                module_name = module_name_for(self.instance)
            if not re.fullmatch(r"[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*", module_name):
                raise serializers.ValidationError(
                    {"module_name": "请输入合法的 Ansible Module 名称"}
                )
            if (
                "module_name" in attrs
                and content
                and content != module_name
                and "content" in attrs
            ):
                raise serializers.ValidationError(
                    {"content": "Module 请使用 module_name，不要传入其他正文"}
                )
            if "parameter_docs" in attrs:
                notes = self._module_notes(attrs["parameter_docs"])
            elif "x-module-parameter-docs" in argument_schema:
                notes = self._module_notes(
                    argument_schema["x-module-parameter-docs"], "argument_schema"
                )
            elif self.instance is not None:
                notes = parameter_docs_for(self.instance)
            else:
                notes = legacy_parameter_docs(argument_schema)
            module_args = default_vars.get("module_args", {})
            if not isinstance(module_args, (dict, str)):
                raise serializers.ValidationError(
                    {"default_vars": "module_args 必须是 JSON 对象或参数字符串"}
                )
            attrs.update(
                module_name=module_name,
                parameter_docs=notes,
                content="",
                argument_schema={},
            )
            attrs.update(
                default_vars={},
                output_extractors=[],
                timeout_seconds=60,
                become_enabled=False,
                check_mode_supported=False,
            )
        elif attrs.get("module_name") or attrs.get("parameter_docs"):
            raise serializers.ValidationError({"module_name": "仅 Module 资源使用模块名称与参数说明"})
        return attrs

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.command_type == CommandVersion.CommandType.ANSIBLE_MODULE:
            representation["module_name"] = module_name_for(instance)
            representation["parameter_docs"] = parameter_docs_for(instance)
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
    failureAlert = serializers.JSONField(source="failure_alert", required=False)

    def validate_failureAlert(self, value):
        from .failure_alerts import validate_failure_alert

        return validate_failure_alert(value) or {}

    class Meta:
        model = WorkflowTemplate
        exclude = ("failure_alert",)

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
    targetSelectorSchema = serializers.JSONField(
        source="target_selector_schema", required=False
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    graphSnapshot = serializers.JSONField(source="graph_snapshot", read_only=True)
    validationReport = serializers.JSONField(source="validation_report", read_only=True)
    publishedHash = serializers.CharField(source="published_hash", read_only=True)
    createdBy = serializers.PrimaryKeyRelatedField(source="created_by", read_only=True)
    publishedBy = serializers.PrimaryKeyRelatedField(
        source="published_by", read_only=True
    )
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
            "id",
            "createdAt",
            "updatedAt",
            "workflow",
            "version",
            "status",
            "inputSchema",
            "targetSelectorSchema",
            "editorMode",
            "graphSnapshot",
            "validationReport",
            "publishedHash",
            "createdBy",
            "publishedBy",
            "publishedAt",
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
        if node_type == NodeType.PLAYBOOK and config.get(
            "hostPolicy", "native"
        ) not in {"native", "platform"}:
            raise serializers.ValidationError(
                {"config": "hostPolicy 必须是 native 或 platform"}
            )
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


class GitRepositorySerializer(EncryptedResourceSerializer):
    secret_model_field = "token_encrypted"

    class Meta:
        model = GitRepository
        fields = "__all__"
        extra_kwargs = {"token_encrypted": {"write_only": True}}

    def validate_repo_url(self, value):
        url = str(value or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise serializers.ValidationError("仓库地址必须是 http(s) 地址")
        return url


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
    signing_secret = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )

    class Meta:
        model = NotificationChannel
        fields = "__all__"
        extra_kwargs = {
            "secret_encrypted": {"write_only": True},
            "signing_secret_encrypted": {"write_only": True},
        }

    def create(self, validated_data):
        signing_secret = validated_data.pop("signing_secret", "")
        if signing_secret:
            validated_data["signing_secret_encrypted"] = encrypt_secret(signing_secret)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        signing_secret = validated_data.pop("signing_secret", None)
        if signing_secret:
            validated_data["signing_secret_encrypted"] = encrypt_secret(signing_secret)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop("signing_secret_encrypted", None)
        representation["hasSigningSecret"] = bool(instance.signing_secret_encrypted)
        return representation

    def validate_config(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("渠道配置必须是对象")
        if "webhook" in value:
            raise serializers.ValidationError("通知地址请填写到加密地址字段")
        if "payload" in value and not isinstance(value["payload"], dict):
            raise serializers.ValidationError("Webhook 请求体必须是 JSON 对象")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        channel_type = attrs.get(
            "channel_type", getattr(self.instance, "channel_type", None)
        )
        signing_secret = attrs.get("signing_secret")
        if signing_secret and channel_type not in {
            NotificationChannel.ChannelType.DINGTALK,
            NotificationChannel.ChannelType.FEISHU,
        }:
            raise serializers.ValidationError({"signing_secret": "仅钉钉、飞书群机器人支持签名密钥"})
        if channel_type != NotificationChannel.ChannelType.EMAIL:
            secret = attrs.get("secret")
            if not secret and not getattr(self.instance, "secret_encrypted", ""):
                raise serializers.ValidationError({"secret": "请填写通知地址"})
            if secret:
                parsed = urlparse(secret)
                if parsed.scheme != "https" or not parsed.netloc:
                    raise serializers.ValidationError({"secret": "通知地址必须是 HTTPS URL"})
        else:
            config = attrs.get("config") or getattr(self.instance, "config", None) or {}
            from_email = config.get("fromEmail") if isinstance(config, dict) else None
            if from_email:
                from django.core.exceptions import (
                    ValidationError as DjangoValidationError,
                )
                from django.core.validators import validate_email

                try:
                    validate_email(from_email)
                except DjangoValidationError:
                    raise serializers.ValidationError(
                        {"config": "发件人地址格式不合法"}
                    ) from None
        return attrs


class NotificationPreviewSerializer(serializers.Serializer):
    scenario = serializers.ChoiceField(
        choices=("failure", "workflow", "asset_sync", "provisioning", "security"),
        default="failure",
    )
    workflowVersionId = serializers.IntegerField(
        min_value=1, required=False, allow_null=True
    )
    subjectTemplate = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=10000,
        trim_whitespace=False,
    )
    bodyTemplate = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=30000,
        trim_whitespace=False,
    )
    receiverTemplate = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=10000,
        trim_whitespace=False,
    )
    sampleContext = serializers.JSONField(required=False, default=dict)

    def validate_sampleContext(self, value):
        import json

        if not isinstance(value, dict) or len(json.dumps(value)) > 32768:
            raise serializers.ValidationError("测试数据必须是32KB以内的JSON对象")
        return value


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

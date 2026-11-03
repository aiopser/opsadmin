"""Documentation-only DTOs for custom automation APIView payloads."""

from drf_spectacular.utils import PolymorphicProxySerializer
from rest_framework import serializers

from .email_settings import PROTOCOLS
from .models import CommandAtom, CommandVersion
from .node_resources import NODE_RESOURCE_TYPES
from .notification_apps import PROVIDERS
from .notification_history import MAX_RETENTION_DAYS, MIN_RETENTION_DAYS
from .serializers import (
    CommandAtomSerializer,
    CommandVersionSerializer,
    ModuleParameterDocSerializer,
)


class AutomationTemplateBaseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    templateId = serializers.IntegerField()
    name = serializers.CharField()
    code = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    version = serializers.IntegerField()
    versionStatus = serializers.ChoiceField(choices=CommandVersion.Status.choices)
    publishedAt = serializers.DateTimeField(allow_null=True)


class CommandTemplateReadSerializer(AutomationTemplateBaseSerializer):
    moduleName = serializers.CharField(allow_blank=True)
    parameterDocs = ModuleParameterDocSerializer(many=True)
    templateType = serializers.ChoiceField(choices=("command",))
    riskLevel = serializers.ChoiceField(choices=CommandAtom.RiskLevel.choices)
    resourceKind = serializers.ChoiceField(choices=CommandAtom.ResourceKind.choices)
    commandType = serializers.ChoiceField(choices=CommandVersion.CommandType.choices)
    argumentSchema = serializers.JSONField()
    defaultVars = serializers.JSONField()
    timeoutSeconds = serializers.IntegerField()
    becomeEnabled = serializers.BooleanField()
    checkModeSupported = serializers.BooleanField()
    outputExtractors = serializers.JSONField()


class WorkflowTemplateReadSerializer(AutomationTemplateBaseSerializer):
    templateType = serializers.ChoiceField(choices=("workflow",))
    inputSchema = serializers.JSONField()
    targetSelectorSchema = serializers.JSONField()


automation_template_list = PolymorphicProxySerializer(
    component_name="ExecutableAutomationTemplate",
    serializers={
        "command": CommandTemplateReadSerializer,
        "workflow": WorkflowTemplateReadSerializer,
    },
    resource_type_field_name="templateType",
    many=True,
)


class NodeResourceBaseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    resourceKey = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)


class AnsibleNodeResourceReadSerializer(NodeResourceBaseSerializer):
    moduleName = serializers.CharField(allow_blank=True)
    parameterDocs = ModuleParameterDocSerializer(many=True)
    nodeType = serializers.ChoiceField(choices=CommandAtom.ResourceKind.choices)
    resourceType = serializers.ChoiceField(choices=("command_version",))
    code = serializers.CharField()
    version = serializers.IntegerField()
    riskLevel = serializers.ChoiceField(choices=CommandAtom.RiskLevel.choices)
    timeoutSeconds = serializers.IntegerField()
    argumentSchema = serializers.JSONField()
    defaultVars = serializers.JSONField()
    checkModeSupported = serializers.BooleanField()
    becomeEnabled = serializers.BooleanField()


class ApiNodeResourceReadSerializer(NodeResourceBaseSerializer):
    nodeType = serializers.ChoiceField(choices=("api",))
    resourceType = serializers.ChoiceField(choices=("api_endpoint",))
    summary = serializers.CharField()
    timeoutSeconds = serializers.IntegerField()


class JenkinsNodeResourceReadSerializer(NodeResourceBaseSerializer):
    nodeType = serializers.ChoiceField(choices=("jenkins",))
    resourceType = serializers.ChoiceField(choices=("jenkins_job",))
    summary = serializers.CharField()
    argumentSchema = serializers.JSONField()


class NotificationNodeResourceReadSerializer(NodeResourceBaseSerializer):
    nodeType = serializers.ChoiceField(choices=("notify",))
    resourceType = serializers.ChoiceField(choices=("notification_template",))
    summary = serializers.CharField()


class NodeResourceRouteQuerySerializer(serializers.Serializer):
    kind = serializers.ChoiceField(
        choices=CommandAtom.ResourceKind.choices, required=False
    )


class NodeResourceTypeSerializer(serializers.Serializer):
    nodeType = serializers.ChoiceField(
        choices=[item[0] for item in NODE_RESOURCE_TYPES]
    )
    name = serializers.CharField()
    resourceType = serializers.ChoiceField(
        choices=tuple(dict.fromkeys(item[2] for item in NODE_RESOURCE_TYPES))
    )
    requiresResource = serializers.BooleanField()
    resourceCount = serializers.IntegerField(min_value=0)
    createRoute = serializers.CharField()
    createRouteQuery = NodeResourceRouteQuerySerializer()


class NodeResourceCatalogSerializer(serializers.Serializer):
    types = NodeResourceTypeSerializer(many=True)
    resources = PolymorphicProxySerializer(
        component_name="AutomationNodeResource",
        serializers={
            "command_version": AnsibleNodeResourceReadSerializer,
            "api_endpoint": ApiNodeResourceReadSerializer,
            "jenkins_job": JenkinsNodeResourceReadSerializer,
            "notification_template": NotificationNodeResourceReadSerializer,
        },
        resource_type_field_name="resourceType",
        many=True,
    )


class NodeResourceCreatedSerializer(serializers.Serializer):
    resource = CommandAtomSerializer()
    version = CommandVersionSerializer()


class EmailConnectionInputSerializer(serializers.Serializer):
    protocol = serializers.ChoiceField(
        choices=PROTOCOLS, required=False, default="smtp"
    )
    host = serializers.CharField()
    port = serializers.IntegerField(min_value=1, max_value=65535)
    timeout = serializers.IntegerField(min_value=0, max_value=3600)
    username = serializers.CharField(required=False, allow_blank=True)
    useTls = serializers.BooleanField(required=False, default=False)
    password = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
        help_text="留空时使用已保存的密码。",
    )


class EmailSettingsInputSerializer(EmailConnectionInputSerializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    fromEmail = serializers.CharField(help_text="发送邮箱，必须包含 @。")
    titlePrefix = serializers.CharField(required=False, allow_blank=True)


class EmailSettingsReadSerializer(serializers.Serializer):
    name = serializers.CharField(allow_blank=True)
    description = serializers.CharField(allow_blank=True)
    fromEmail = serializers.CharField(allow_blank=True)
    titlePrefix = serializers.CharField(allow_blank=True)
    protocol = serializers.ChoiceField(choices=PROTOCOLS)
    host = serializers.CharField(allow_blank=True)
    port = serializers.IntegerField(min_value=1, max_value=65535)
    timeout = serializers.IntegerField(min_value=0, max_value=3600)
    useTls = serializers.BooleanField()
    username = serializers.CharField(allow_blank=True)
    hasPassword = serializers.BooleanField()
    configured = serializers.BooleanField()


class EmailTestRecipientSerializer(serializers.Serializer):
    recipient = serializers.CharField(help_text="收件人邮箱，必须包含 @。")


class NotificationConnectionResultSerializer(serializers.Serializer):
    connected = serializers.BooleanField()


class NotificationHistorySettingsSerializer(serializers.Serializer):
    retentionDays = serializers.IntegerField(
        min_value=MIN_RETENTION_DAYS, max_value=MAX_RETENTION_DAYS
    )


class NotificationHistoryPurgeInputSerializer(serializers.Serializer):
    retentionDays = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=MIN_RETENTION_DAYS,
        max_value=MAX_RETENTION_DAYS,
        help_text="省略或传 null 时使用已保存的保留天数。",
    )
    dryRun = serializers.BooleanField(required=False, default=False)


class NotificationHistoryPurgeResultSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    deleted = serializers.IntegerField(min_value=0)
    dryRun = serializers.BooleanField()


class NotificationAppReadSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=PROVIDERS)
    appId = serializers.CharField(allow_blank=True)
    agentId = serializers.CharField(allow_blank=True)
    apiBase = serializers.CharField()
    hasSecret = serializers.BooleanField()
    configured = serializers.BooleanField()


class NotificationAppConnectionInputSerializer(serializers.Serializer):
    appId = serializers.CharField()
    apiBase = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="HTTP(S) API 地址，留空时使用该应用的默认地址。",
    )
    appSecret = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
        help_text="留空时使用已保存的 Secret；首次配置必须提供。",
    )


class WecomSettingsInputSerializer(NotificationAppConnectionInputSerializer):
    agentId = serializers.CharField()


class DingtalkSettingsInputSerializer(NotificationAppConnectionInputSerializer):
    agentId = serializers.CharField(required=False, allow_blank=True)

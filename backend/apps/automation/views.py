from common.workflow.node_types import NodeType
from common.workflow.node_types import CONTROL_NODE_TYPES
from common.workflow.schema import validate_graph
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Count, Max, Q
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view

import json
import os
import shutil
import subprocess
import tempfile
from urllib.parse import quote, urlsplit, urlunsplit

from common.api.responses import api_error_response, api_ok_response
from common.api.schema import api_envelope_serializer
from common.api.viewsets import StandardModelViewSet
from apps.audit_center.services import create_domain_audit_event
from apps.cmdb.crypto import decrypt_secret

import logging

logger = logging.getLogger(__name__)

from .audit import build_automation_audit_snapshot
from .email_settings import (
    check_email_connection,
    get_email_settings,
    save_email_settings,
    send_test_email,
)
from .notification_apps import (
    PROVIDER_DINGTALK,
    PROVIDER_FEISHU,
    PROVIDER_WECOM,
    check_app_connection,
    get_app_settings,
    save_app_settings,
)
from .notification_history import (
    get_history_settings,
    parse_retention_days,
    purge_notification_history,
    save_history_settings,
)
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
from .serializers import (
    ApiEndpointSerializer,
    AnsibleNodeResourceCreateSerializer,
    AutomationTemplateSerializer,
    CommandAtomSerializer,
    CommandVersionSerializer,
    GitRepositorySerializer,
    JenkinsServerSerializer,
    JenkinsBuildSerializer,
    JenkinsJobSerializer,
    NotificationChannelSerializer,
    NotificationRecordSerializer,
    NotificationPreviewSerializer,
    NotificationTemplateSerializer,
    WorkflowEdgeSerializer,
    WorkflowNodeSerializer,
    WorkflowTemplateSerializer,
    WorkflowVersionSerializer,
)
from .node_resources import node_resource_catalog
from .schema_serializers import (
    DingtalkSettingsInputSerializer,
    EmailConnectionInputSerializer,
    EmailSettingsInputSerializer,
    EmailSettingsReadSerializer,
    EmailTestRecipientSerializer,
    NodeResourceCatalogSerializer,
    NodeResourceCreatedSerializer,
    NotificationAppConnectionInputSerializer,
    NotificationAppReadSerializer,
    NotificationConnectionResultSerializer,
    NotificationHistoryPurgeInputSerializer,
    NotificationHistoryPurgeResultSerializer,
    NotificationHistorySettingsSerializer,
    WecomSettingsInputSerializer,
    automation_template_list,
)
from .workflow_graph import (
    replace_graph,
    serialize_graph,
)


_EMAIL_SETTINGS_RESPONSE = api_envelope_serializer(
    "NotificationEmailSettingsResponse", EmailSettingsReadSerializer
)
_NOTIFICATION_CONNECTION_RESPONSE = api_envelope_serializer(
    "NotificationConnectionResultResponse", NotificationConnectionResultSerializer
)
_NOTIFICATION_HISTORY_SETTINGS_RESPONSE = api_envelope_serializer(
    "NotificationHistorySettingsResponse", NotificationHistorySettingsSerializer
)
_NOTIFICATION_APP_SETTINGS_RESPONSE = api_envelope_serializer(
    "NotificationAppSettingsResponse", NotificationAppReadSerializer
)


class AutomationTemplateView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter("type", str, enum=["command", "workflow"]),
            OpenApiParameter(
                "resource_kind", str, enum=CommandAtom.ResourceKind.values
            ),
        ],
        responses=api_envelope_serializer(
            "AutomationTemplateListResponse", automation_template_list
        ),
    )
    def get(self, request):
        template_type = request.query_params.get("type")
        resource_kind = request.query_params.get("resource_kind")
        templates = []
        if template_type in (None, "", "command"):
            command_versions = (
                CommandVersion.objects.select_related("command")
                .filter(
                    status=CommandVersion.Status.PUBLISHED,
                    command__status=CommandAtom.Status.PUBLISHED,
                )
                .order_by("command__name", "-version", "id")
            )
            if resource_kind:
                command_versions = command_versions.filter(
                    command__resource_kind=resource_kind
                )
            templates.extend(command_versions)
        if template_type in (None, "", "workflow"):
            templates.extend(
                WorkflowVersion.objects.select_related("workflow")
                .filter(
                    status=WorkflowVersion.Status.PUBLISHED,
                    workflow__status=WorkflowTemplate.Status.PUBLISHED,
                )
                .order_by("workflow__name", "-version", "id")
            )
        serializer = AutomationTemplateSerializer(templates, many=True)
        return api_ok_response(serializer.data)


class NodeResourceView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                "node_type",
                str,
                enum=[*CommandAtom.ResourceKind.values, "api", "jenkins", "notify"],
            )
        ],
        responses=api_envelope_serializer(
            "NodeResourceCatalogResponse", NodeResourceCatalogSerializer
        ),
    )
    def get(self, request):
        return api_ok_response(
            node_resource_catalog(request.query_params.get("node_type") or "")
        )

    @extend_schema(
        request=AnsibleNodeResourceCreateSerializer,
        responses=api_envelope_serializer(
            "NodeResourceCreatedResponse", NodeResourceCreatedSerializer
        ),
    )
    def post(self, request):
        serializer = AnsibleNodeResourceCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        command, version = serializer.save()
        return api_ok_response(
            {
                "resource": CommandAtomSerializer(command).data,
                "version": CommandVersionSerializer(version).data,
            }
        )


class AutomationAuditModelViewSet(StandardModelViewSet):
    audit_action_prefix = ""
    audit_resource_type = ""

    def _create_audit_event(self, request, action, instance, before=None, after=None):
        create_domain_audit_event(
            actor=request.user,
            action=f"{self.audit_action_prefix}.{action}",
            resource_type=self.audit_resource_type,
            resource_id=instance.id,
            before=before or {},
            after=after or {},
            request=request,
        )

    def perform_create(self, serializer, request=None):
        super().perform_create(serializer, request=request)
        self._create_audit_event(
            request,
            "create",
            serializer.instance,
            after=build_automation_audit_snapshot(serializer.instance),
        )

    def perform_update(self, serializer, request=None):
        instance = serializer.instance
        before = build_automation_audit_snapshot(instance)
        super().perform_update(serializer, request=request)
        self._create_audit_event(
            request,
            "update",
            serializer.instance,
            before=before,
            after=build_automation_audit_snapshot(serializer.instance),
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        before = build_automation_audit_snapshot(instance)
        response = super().destroy(request, *args, **kwargs)
        if not getattr(instance, "is_system", False):
            self._create_audit_event(request, "delete", instance, before=before)
        return response


class CommandAtomViewSet(AutomationAuditModelViewSet):
    audit_action_prefix = "automation.command"
    audit_resource_type = "command"
    queryset = CommandAtom.objects.select_related("created_by", "updated_by").all()
    serializer_class = CommandAtomSerializer
    ordering_fields = ("id", "name", "code", "updated_at")
    filterset_fields = ("status", "risk_level", "category", "resource_kind")
    search_fields = ("name", "code", "category", "description")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # 业务层保护：检查是否有流程节点引用了该命令的版本
        if WorkflowNode.objects.filter(command_version__command=instance).exists():
            return api_error_response("该命令已被流程节点引用，无法删除。可将其状态设为「停用」。")
        before = build_automation_audit_snapshot(instance)
        try:
            response = super().destroy(request, *args, **kwargs)
        except ProtectedError as exc:
            logger.warning("Command %s delete blocked: %s", instance.id, exc)
            return api_error_response("该命令存在关联数据无法删除，可将其状态设为「停用」。")
        if not getattr(instance, "is_system", False):
            self._create_audit_event(request, "delete", instance, before=before)
        return response

    @action(methods=["GET", "POST"], detail=True, url_path="versions")
    @transaction.atomic
    def versions(self, request, pk=None):
        command = self.get_object()
        if request.method == "GET":
            serializer = CommandVersionSerializer(
                command.versions.select_related(
                    "command", "created_by", "published_by"
                ),
                many=True,
            )
            return api_ok_response(serializer.data)

        command = CommandAtom.objects.select_for_update().get(pk=command.pk)
        latest = command.versions.order_by("-version").first()
        next_version = latest.version + 1 if latest else 1
        mutable = request.data.copy()
        mutable["command"] = command.id
        mutable["version"] = next_version
        serializer = CommandVersionSerializer(data=mutable)
        serializer.is_valid(raise_exception=True)
        serializer.save(request=request)
        create_domain_audit_event(
            actor=request.user,
            action="automation.command_version.create",
            resource_type="command_version",
            resource_id=serializer.instance.id,
            after=build_automation_audit_snapshot(serializer.instance),
            request=request,
        )
        return api_ok_response(serializer.data)


class CommandVersionViewSet(AutomationAuditModelViewSet):
    audit_action_prefix = "automation.command_version"
    audit_resource_type = "command_version"
    queryset = CommandVersion.objects.select_related(
        "command",
        "created_by",
        "published_by",
    ).all()
    serializer_class = CommandVersionSerializer
    ordering_fields = ("id", "version", "published_at", "updated_at")
    filterset_fields = ("command", "status", "command_type", "command__resource_kind")
    search_fields = ("command__name", "command__code", "content")

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        selected = self.get_object()
        CommandAtom.objects.select_for_update().get(pk=selected.command_id)
        instance = self.get_object()
        if instance.status != instance.Status.DRAFT:
            return api_error_response("只有草稿版本可以修改")
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        selected = self.get_object()
        CommandAtom.objects.select_for_update().get(pk=selected.command_id)
        instance = self.get_object()
        if instance.status != CommandVersion.Status.DRAFT:
            return api_error_response("只有草稿版本可以删除，历史版本请保留或归档")
        # 业务层保护：检查是否有流程节点引用了该命令版本
        if WorkflowNode.objects.filter(command_version=instance).exists():
            return api_error_response("该命令版本已被流程节点引用，无法删除。可将其状态设为「归档」。")
        return super().destroy(request, *args, **kwargs)

    @action(methods=["POST"], detail=True, url_path="publish")
    @transaction.atomic
    def publish(self, request, pk=None):
        selected = self.get_object()
        command = CommandAtom.objects.select_for_update().get(pk=selected.command_id)
        instance = CommandVersion.objects.select_for_update().get(pk=selected.pk)
        instance.command = command
        if instance.status != CommandVersion.Status.DRAFT:
            return api_error_response("只有草稿版本可以发布")
        validator = self.get_serializer(instance, data={}, partial=True)
        validator.is_valid(raise_exception=True)
        previous_status = instance.status
        # 自动归档同一命令下的旧 published 版本
        CommandVersion.objects.filter(
            command=instance.command,
            status=CommandVersion.Status.PUBLISHED,
        ).exclude(pk=instance.pk).update(status=CommandVersion.Status.ARCHIVED)
        instance.publish(request.user)
        if instance.command.status == CommandAtom.Status.DRAFT:
            instance.command.status = CommandAtom.Status.PUBLISHED
            instance.command.updated_by = request.user
            instance.command.save(update_fields=["status", "updated_by", "updated_at"])
        create_domain_audit_event(
            actor=request.user,
            action="automation.command_version.publish",
            resource_type="command_version",
            resource_id=instance.id,
            before={"status": previous_status},
            after={"status": instance.status, "command_id": instance.command_id},
            request=request,
        )
        serializer = self.get_serializer(instance)
        return api_ok_response(serializer.data)

    @action(methods=["POST"], detail=True, url_path="archive")
    @transaction.atomic
    def archive(self, request, pk=None):
        selected = self.get_object()
        CommandAtom.objects.select_for_update().get(pk=selected.command_id)
        instance = CommandVersion.objects.select_for_update().get(pk=selected.pk)
        previous_status = instance.status
        instance.archive()
        create_domain_audit_event(
            actor=request.user,
            action="automation.command_version.archive",
            resource_type="command_version",
            resource_id=instance.id,
            before={"status": previous_status},
            after={"status": instance.status, "command_id": instance.command_id},
            request=request,
        )
        serializer = self.get_serializer(instance)
        return api_ok_response(serializer.data)


class WorkflowTemplateViewSet(AutomationAuditModelViewSet):
    audit_action_prefix = "automation.workflow"
    audit_resource_type = "workflow"
    queryset = (
        WorkflowTemplate.objects.select_related("created_by", "updated_by")
        .annotate(
            version_count=Count("versions", distinct=True),
            run_count=Count("versions__runs", distinct=True),
            last_run_at=Max("versions__runs__created_at"),
        )
        .all()
    )
    serializer_class = WorkflowTemplateSerializer
    ordering_fields = ("id", "name", "code", "updated_at")
    filterset_fields = ("status", "owner_team")
    search_fields = ("name", "code", "description", "owner_team")

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        from django.db.models import Q

        instance = self.get_object()
        if instance.versions.filter(
            Q(scheduled_jobs__isnull=False)
            | Q(task_tickets__isnull=False)
            | Q(runs__isnull=False)
        ).exists():
            return api_error_response("该流程已被定时任务、任务单或运行记录引用，不能删除，可将其停用")
        before = build_automation_audit_snapshot(instance)
        try:
            response = super().destroy(request, *args, **kwargs)
        except ProtectedError as exc:
            logger.warning("Workflow %s delete blocked: %s", instance.id, exc)
            return api_error_response("该流程存在关联数据无法删除，可将其状态设为「停用」。")
        if not getattr(instance, "is_system", False):
            self._create_audit_event(request, "delete", instance, before=before)
        return response

    @action(methods=["GET", "POST"], detail=True, url_path="versions")
    def versions(self, request, pk=None):
        workflow = self.get_object()
        if request.method == "GET":
            serializer = WorkflowVersionSerializer(
                workflow.versions.select_related(
                    "workflow", "created_by", "published_by"
                ),
                many=True,
            )
            return api_ok_response(serializer.data)

        latest = workflow.versions.order_by("-version").first()
        next_version = latest.version + 1 if latest else 1
        mutable = request.data.copy()
        mutable["workflow"] = workflow.id
        mutable.setdefault("version", next_version)
        serializer = WorkflowVersionSerializer(data=mutable)
        serializer.is_valid(raise_exception=True)
        serializer.save(request=request)
        create_domain_audit_event(
            actor=request.user,
            action="automation.workflow_version.create",
            resource_type="workflow_version",
            resource_id=serializer.instance.id,
            after=build_automation_audit_snapshot(serializer.instance),
            request=request,
        )
        return api_ok_response(serializer.data)

    @action(methods=["POST"], detail=True, url_path="copy")
    def copy_workflow(self, request, pk=None):
        source = self.get_object()
        source_version = source.versions.order_by("-version").first()
        code = str(
            request.data.get("code")
            or f"{source.code}_copy_{timezone.now():%Y%m%d%H%M%S}"
        ).strip()
        if WorkflowTemplate.objects.filter(code=code).exists():
            return api_error_response("流程编码已存在")
        with transaction.atomic():
            copied = WorkflowTemplate.objects.create(
                name=str(request.data.get("name") or f"{source.name} - 副本"),
                code=code,
                description=source.description,
                owner_team=source.owner_team,
                status=WorkflowTemplate.Status.DRAFT,
                created_by=request.user,
                updated_by=request.user,
            )
            if source_version:
                copied_version = WorkflowVersion.objects.create(
                    workflow=copied,
                    version=1,
                    status=WorkflowVersion.Status.DRAFT,
                    input_schema=source_version.input_schema,
                    target_selector_schema=source_version.target_selector_schema,
                    created_by=request.user,
                )
                replace_graph(copied_version, serialize_graph(source_version))
        return api_ok_response(self.get_serializer(copied).data)


class WorkflowVersionViewSet(AutomationAuditModelViewSet):
    audit_action_prefix = "automation.workflow_version"
    audit_resource_type = "workflow_version"
    queryset = WorkflowVersion.objects.select_related(
        "workflow",
        "created_by",
        "published_by",
    ).all()
    serializer_class = WorkflowVersionSerializer
    ordering_fields = ("id", "version", "published_at", "updated_at")
    filterset_fields = ("workflow", "status", "workflow__status")
    search_fields = ("workflow__name", "workflow__code")

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != instance.Status.DRAFT:
            return api_error_response("Only draft workflow versions can be modified")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != instance.Status.DRAFT:
            return api_error_response("只有草稿版本可以删除")
        return super().destroy(request, *args, **kwargs)

    def _validate_workflow_version(self, instance):
        node_keys = set()
        graph = serialize_graph(instance)
        errors = list(instance.validation_report or [])
        errors.extend(validate_graph(graph) if graph.get("nodes") else [])
        nodes = list(
            instance.nodes.select_related(
                "command_version",
                "command_version__command",
            ).order_by("order_index", "id")
        )
        if not nodes:
            errors.append("流程版本至少需要一个节点")
        elif not any(node.node_type not in CONTROL_NODE_TYPES for node in nodes):
            errors.append("流程版本至少需要一个可执行任务节点")
        for node in nodes:
            if node.node_key in node_keys:
                errors.append(f"节点标识重复：{node.node_key}")
            node_keys.add(node.node_key)
            if (
                node.command_version_id
                and node.command_version.status != CommandVersion.Status.PUBLISHED
            ):
                errors.append(f"节点 {node.node_key} 绑定的命令版本未发布")
            ansible_kinds = {
                NodeType.COMMAND: CommandAtom.ResourceKind.COMMAND,
                NodeType.SCRIPT: CommandAtom.ResourceKind.SCRIPT,
                NodeType.PLAYBOOK: CommandAtom.ResourceKind.PLAYBOOK,
                NodeType.MODULE: CommandAtom.ResourceKind.MODULE,
            }
            if node.node_type in ansible_kinds and not node.command_version_id:
                errors.append(f"Ansible 节点 {node.node_key} 必须绑定已发布资源版本")
            if (
                node.command_version_id
                and node.node_type in ansible_kinds
                and node.command_version.command.resource_kind
                != ansible_kinds[node.node_type]
            ):
                errors.append(f"节点 {node.node_key} 绑定的资源类型不匹配")
            if (
                node.command_version_id
                and (node.config or {}).get("checkMode")
                and not node.command_version.check_mode_supported
            ):
                errors.append(f"节点 {node.node_key} 绑定的资源版本不支持 Check Mode")
            if (
                node.node_type == NodeType.API
                and not ApiEndpoint.objects.filter(
                    id=node.resource_id, is_active=True
                ).exists()
            ):
                errors.append(f"API 节点 {node.node_key} 未绑定有效资源")
            if (
                node.node_type == NodeType.JENKINS
                and not JenkinsJob.objects.filter(
                    id=node.resource_id, is_active=True, server__is_active=True
                ).exists()
            ):
                errors.append(f"Jenkins 节点 {node.node_key} 未绑定有效 Job")
            if (
                node.node_type == NodeType.NOTIFY
                and not NotificationTemplate.objects.filter(
                    id=node.resource_id, is_active=True, channel__is_active=True
                ).exists()
            ):
                errors.append(f"通知节点 {node.node_key} 未绑定有效模板")
            if (
                node.condition_policy == WorkflowNode.ConditionPolicy.EXPRESSION
                and not node.condition_expression.strip()
            ):
                errors.append(f"节点 {node.node_key} 使用表达式策略时必须填写条件表达式")
            if node.timeout_seconds is not None and node.timeout_seconds <= 0:
                errors.append(f"节点 {node.node_key} 超时时间必须大于 0")
        return list(dict.fromkeys(errors))

    @action(methods=["POST"], detail=True, url_path="publish")
    @transaction.atomic
    def publish(self, request, pk=None):
        instance = self.get_object()
        if instance.status != instance.Status.DRAFT:
            return api_error_response("只有草稿流程版本可以发布")
        errors = self._validate_workflow_version(instance)
        if errors:
            return api_error_response({"valid": False, "errors": errors})
        previous_status = instance.status
        # 自动归档同一流程下的旧 published 版本
        WorkflowVersion.objects.filter(
            workflow=instance.workflow,
            status=WorkflowVersion.Status.PUBLISHED,
        ).exclude(pk=instance.pk).update(status=WorkflowVersion.Status.ARCHIVED)
        instance.publish(request.user)
        create_domain_audit_event(
            actor=request.user,
            action="automation.workflow_version.publish",
            resource_type="workflow_version",
            resource_id=instance.id,
            before={"status": previous_status},
            after={"status": instance.status, "workflow_id": instance.workflow_id},
            request=request,
        )
        serializer = self.get_serializer(instance)
        return api_ok_response(serializer.data)

    @action(methods=["POST"], detail=True, url_path="archive")
    def archive(self, request, pk=None):
        instance = self.get_object()
        previous_status = instance.status
        instance.archive()
        create_domain_audit_event(
            actor=request.user,
            action="automation.workflow_version.archive",
            resource_type="workflow_version",
            resource_id=instance.id,
            before={"status": previous_status},
            after={"status": instance.status, "workflow_id": instance.workflow_id},
            request=request,
        )
        serializer = self.get_serializer(instance)
        return api_ok_response(serializer.data)

    @action(methods=["POST"], detail=True, url_path="validate")
    def validate(self, request, pk=None):
        instance = self.get_object()
        errors = self._validate_workflow_version(instance)
        instance.validation_report = errors
        instance.save(update_fields=["validation_report", "updated_at"])
        return api_ok_response({"valid": not errors, "errors": errors})

    @action(methods=["GET", "PUT"], detail=True, url_path="graph")
    def graph(self, request, pk=None):
        instance = self.get_object()
        if request.method == "GET":
            return api_ok_response(
                {
                    "graph": serialize_graph(instance),
                    "validationReport": instance.validation_report,
                }
            )
        if instance.status != WorkflowVersion.Status.DRAFT:
            return api_error_response("只有草稿流程版本可以修改")
        graph = request.data.get("graph") or {}
        errors = replace_graph(instance, graph)
        if errors:
            instance.validation_report = errors
            instance.save(update_fields=["validation_report", "updated_at"])
            return api_ok_response(
                {"valid": False, "errors": errors, "graph": serialize_graph(instance)}
            )
        return api_ok_response(
            {"valid": True, "errors": [], "graph": serialize_graph(instance)}
        )


class WorkflowNodeViewSet(AutomationAuditModelViewSet):
    audit_action_prefix = "automation.workflow_node"
    audit_resource_type = "workflow_node"
    queryset = WorkflowNode.objects.select_related(
        "workflow_version",
        "command_version",
        "command_version__command",
    ).all()
    serializer_class = WorkflowNodeSerializer
    ordering_fields = ("id", "workflow_version", "order_index")
    filterset_fields = ("workflow_version", "command_version", "condition_policy")
    search_fields = ("node_key", "name")

    def _is_immutable_version(self, workflow_version):
        return workflow_version.status != WorkflowVersion.Status.DRAFT

    def create(self, request, *args, **kwargs):
        workflow_version_id = request.data.get("workflow_version") or request.data.get(
            "workflowVersion"
        )
        if workflow_version_id:
            workflow_version = WorkflowVersion.objects.filter(
                id=workflow_version_id
            ).first()
            if workflow_version and self._is_immutable_version(workflow_version):
                return api_error_response("只有草稿流程版本可以新增节点")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if self._is_immutable_version(instance.workflow_version):
            return api_error_response("只有草稿流程版本可以编辑节点")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if self._is_immutable_version(instance.workflow_version):
            return api_error_response("只有草稿流程版本可以删除节点")
        return super().destroy(request, *args, **kwargs)


class WorkflowEdgeViewSet(AutomationAuditModelViewSet):
    audit_action_prefix = "automation.workflow_edge"
    audit_resource_type = "workflow_edge"
    queryset = WorkflowEdge.objects.select_related(
        "workflow_version", "source_node", "target_node"
    ).all()
    serializer_class = WorkflowEdgeSerializer
    ordering_fields = ("id", "workflow_version", "order_index")
    filterset_fields = ("workflow_version", "source_node", "target_node")
    search_fields = ("edge_key", "condition_expression")

    def _is_immutable_version(self, workflow_version):
        return workflow_version.status != WorkflowVersion.Status.DRAFT

    def create(self, request, *args, **kwargs):
        workflow_version_id = request.data.get("workflow_version") or request.data.get(
            "workflowVersion"
        )
        workflow_version = WorkflowVersion.objects.filter(
            id=workflow_version_id
        ).first()
        if workflow_version and self._is_immutable_version(workflow_version):
            return api_error_response("只有草稿流程版本可以新增连线")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if self._is_immutable_version(instance.workflow_version):
            return api_error_response("只有草稿流程版本可以编辑连线")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if self._is_immutable_version(instance.workflow_version):
            return api_error_response("只有草稿流程版本可以删除连线")
        return super().destroy(request, *args, **kwargs)


class WorkflowResourceProtectionMixin:
    workflow_node_type = None
    workflow_resource_label = "节点资源"

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if WorkflowNode.objects.filter(
            node_type=self.workflow_node_type,
            resource_id=str(instance.id),
        ).exists():
            return api_error_response(
                f"该{self.workflow_resource_label}已被流程节点引用，无法删除，请先停用或解除引用"
            )
        return super().destroy(request, *args, **kwargs)


class ApiEndpointViewSet(WorkflowResourceProtectionMixin, AutomationAuditModelViewSet):
    workflow_node_type = NodeType.API
    workflow_resource_label = "API 资源"
    audit_action_prefix = "automation.api_endpoint"
    audit_resource_type = "api_endpoint"
    queryset = ApiEndpoint.objects.select_related("created_by", "updated_by").all()
    serializer_class = ApiEndpointSerializer
    ordering_fields = ("id", "name", "method", "updated_at")
    filterset_fields = ("method", "auth_type", "is_active")
    search_fields = ("name", "description", "url")

    @action(methods=["POST"], detail=True, url_path="test")
    def test_request(self, request, pk=None):
        from apps.jobs.node_executors import execute_api_endpoint

        endpoint = self.get_object()
        try:
            result = execute_api_endpoint(
                endpoint,
                {
                    "inputs": request.data.get("inputVars") or {},
                    "system": {"test": True},
                    "nodes": {},
                },
            )
        except Exception as exc:
            logger.exception("API endpoint test %s failed", endpoint.id)
            return api_error_response(str(exc) or exc.__class__.__name__)
        return api_ok_response(result)


class JenkinsServerViewSet(AutomationAuditModelViewSet):
    audit_action_prefix = "automation.jenkins_server"
    audit_resource_type = "jenkins_server"
    queryset = JenkinsServer.objects.select_related("created_by", "updated_by").all()
    serializer_class = JenkinsServerSerializer
    ordering_fields = ("id", "name", "updated_at")
    filterset_fields = ("is_active",)
    search_fields = ("name", "base_url", "username")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if WorkflowNode.objects.filter(
            node_type=NodeType.JENKINS,
            resource_id__in=instance.jobs.values("id"),
        ).exists():
            return api_error_response("该 Jenkins 实例下的 Job 已被流程节点引用，不能删除，可将实例停用")
        if JenkinsBuild.objects.filter(job__server=instance).exists():
            return api_error_response("该 Jenkins 实例已有 Build 记录，不能删除，可将实例停用")
        return super().destroy(request, *args, **kwargs)

    @action(methods=["POST"], detail=False, url_path="test-connection")
    def test_connection(self, request):
        """测试 Jenkins 连通性：已保存实例在 secret 留空时使用存量 Token，新增表单直接用填写值。"""
        from apps.cmdb.crypto import decrypt_secret
        from apps.jobs.node_executors import _jenkins_basic_auth, _request

        data = request.data or {}
        server = None
        server_id = data.get("id")
        if server_id:
            server = self.get_queryset().filter(pk=server_id).first()
            if server is None:
                return api_error_response("Jenkins 服务不存在")
        base_url = str(data.get("baseUrl") or "").strip() or (
            server.base_url if server else ""
        )
        username = str(data.get("username") or "").strip() or (
            server.username if server else ""
        )
        secret = str(data.get("secret") or "")
        if not secret and server:
            secret = decrypt_secret(server.token_encrypted)
        if data.get("verifySsl") is not None:
            verify_ssl = bool(data.get("verifySsl"))
        else:
            verify_ssl = server.verify_ssl if server else True
        if not base_url or not username or not secret:
            return api_error_response("请先填写服务地址、用户名与 API Token")

        status, _, _ = _request(
            "GET",
            base_url.rstrip("/") + "/api/json?tree=mode",
            _jenkins_basic_auth(username, secret),
            None,
            15,
            verify_ssl,
        )
        if status == 200:
            return api_ok_response({"reachable": True})
        if status in (401, 403):
            return api_error_response(f"连接失败：认证被拒绝（HTTP {status}），请检查用户名与 API Token")
        return api_error_response(f"连接失败：HTTP {status}，请检查服务地址与网络")

    @action(methods=["GET"], detail=True, url_path="jobs")
    def jobs(self, request, pk=None):
        from urllib.parse import urljoin

        from apps.jobs.node_executors import _jenkins_headers, _request

        server = self.get_object()
        status, _, body = _request(
            "GET",
            urljoin(
                server.base_url.rstrip("/") + "/", "api/json?tree=jobs[name,url,color]"
            ),
            _jenkins_headers(server),
            None,
            20,
            server.verify_ssl,
        )
        if status != 200:
            return api_error_response(f"Jenkins connection failed: HTTP {status}")
        import json

        try:
            jobs = (json.loads(body or "{}") or {}).get("jobs") or []
        except ValueError:
            return api_error_response("Jenkins returned invalid JSON")
        seen = []
        for item in jobs:
            name = str(item.get("name") or "")
            if not name:
                continue
            seen.append(name)
            JenkinsJob.objects.update_or_create(
                server=server,
                name=name,
                defaults={
                    "url": item.get("url") or "",
                    "color": item.get("color") or "",
                    "is_active": True,
                    "last_synced_at": timezone.now(),
                },
            )
        server.jobs.exclude(name__in=seen).update(
            is_active=False, updated_at=timezone.now()
        )
        return api_ok_response(
            JenkinsJobSerializer(server.jobs.filter(is_active=True), many=True).data
        )

    @action(methods=["GET"], detail=True, url_path="job-detail")
    def job_detail(self, request, pk=None):
        import json
        from urllib.parse import quote, urljoin

        from apps.jobs.node_executors import _jenkins_headers, _request

        job_name = str(request.query_params.get("name") or "").strip("/")
        if not job_name:
            return api_error_response("Jenkins Job name is required")
        job_path = "/job/".join(
            quote(part, safe="") for part in job_name.split("/") if part
        )
        server = self.get_object()
        tree = (
            "name,url,color,property[parameterDefinitions["
            "name,type,description,defaultParameterValue[value],choices]]"
        )
        status, _, body = _request(
            "GET",
            urljoin(
                server.base_url.rstrip("/") + "/",
                f"job/{job_path}/api/json?tree={tree}",
            ),
            _jenkins_headers(server),
            None,
            20,
            server.verify_ssl,
        )
        if status != 200:
            return api_error_response(f"Unable to query Jenkins Job: HTTP {status}")
        try:
            job = json.loads(body or "{}") or {}
        except ValueError:
            return api_error_response("Jenkins returned invalid JSON")
        definitions = []
        for prop in job.get("property") or []:
            for definition in prop.get("parameterDefinitions") or []:
                definitions.append(
                    {
                        "name": definition.get("name") or "",
                        "type": definition.get("type") or "StringParameterDefinition",
                        "description": definition.get("description") or "",
                        "default": (definition.get("defaultParameterValue") or {}).get(
                            "value"
                        ),
                        "choices": definition.get("choices") or [],
                    }
                )
        JenkinsJob.objects.update_or_create(
            server=server,
            name=job_name,
            defaults={
                "url": job.get("url") or "",
                "color": job.get("color") or "",
                "parameters": definitions,
                "is_active": True,
                "last_synced_at": timezone.now(),
            },
        )
        return api_ok_response(
            {
                "name": job.get("name") or job_name,
                "url": job.get("url") or "",
                "color": job.get("color") or "",
                "parameters": definitions,
            }
        )


class GitRepoError(Exception):
    """git 操作失败（携带可读错误信息）"""


def _git_plain_token(repo):
    return decrypt_secret(repo.token_encrypted) if repo.token_encrypted else ""


def _git_remote_url(repo):
    """构造克隆 URL：配置令牌时按「用户名:令牌@」嵌入 http(s) 地址（用户名留空则仅令牌）。"""
    url = (repo.repo_url or "").strip()
    token = _git_plain_token(repo)
    if not token:
        return url
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https"):
        return url
    if repo.username:
        netloc = (
            f"{quote(repo.username, safe='')}:{quote(token, safe='')}@{parsed.netloc}"
        )
    else:
        netloc = f"{quote(token, safe='')}@{parsed.netloc}"
    return urlunsplit(parsed._replace(netloc=netloc))


def _sanitize_git_error(message, repo):
    """错误信息可能回显带令牌的 URL，替换令牌避免泄漏。"""
    token = _git_plain_token(repo)
    if token:
        message = message.replace(quote(token, safe=""), "***").replace(token, "***")
    return message


def _run_git(repo, args, timeout=90):
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise GitRepoError("服务器未安装 git") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitRepoError("git 操作超时") from exc
    if proc.returncode != 0:
        raise GitRepoError(
            _sanitize_git_error(
                (proc.stderr or proc.stdout or "git 执行失败").strip(), repo
            )
        )
    return proc.stdout


def _git_shallow_clone(repo, ref):
    """浅克隆指定分支/标签到临时目录并返回路径；失败时自动清理。"""
    repo_dir = tempfile.mkdtemp(prefix="auto-git-")
    args = ["clone", "--depth", "1", "--single-branch"]
    if ref and ref != "HEAD":
        args += ["--branch", ref]
    args += [_git_remote_url(repo), repo_dir]
    if not repo.verify_ssl:
        args = ["-c", "http.sslVerify=false"] + args
    try:
        _run_git(repo, args)
    except GitRepoError:
        shutil.rmtree(repo_dir, ignore_errors=True)
        raise
    return repo_dir


def _validated_ref(repo, ref):
    value = str(ref or "").strip() or (repo.branch or "").strip() or "HEAD"
    if value.startswith("-") or " " in value:
        raise GitRepoError("分支/标签名不合法")
    return value


def _resolve_repo_file(repo_dir, file_path):
    """校验相对路径安全并返回绝对路径（禁止越出仓库目录）。"""
    if not file_path or file_path.startswith("/") or ".." in file_path.split("/"):
        raise GitRepoError("文件路径不合法")
    repo_root = os.path.realpath(repo_dir)
    full = os.path.realpath(os.path.join(repo_dir, file_path))
    if not full.startswith(repo_root + os.sep):
        raise GitRepoError("文件路径不合法")
    if not os.path.isfile(full):
        raise GitRepoError("仓库中不存在该文件")
    if os.path.getsize(full) > 1024 * 1024:
        raise GitRepoError("文件超过 1MB，无法加载")
    return full


class GitRepositoryViewSet(AutomationAuditModelViewSet):
    audit_action_prefix = "automation.git_repository"
    audit_resource_type = "git_repository"
    queryset = GitRepository.objects.select_related("created_by", "updated_by").all()
    serializer_class = GitRepositorySerializer
    ordering_fields = ("id", "name", "updated_at")
    filterset_fields = ("is_active",)
    search_fields = ("name", "repo_url", "username")

    @action(methods=["GET"], detail=True, url_path="files")
    def files(self, request, pk=None):
        """列出仓库文件（浅克隆后 ls-tree，可按关键字过滤）。"""
        repo = self.get_object()
        try:
            ref = _validated_ref(repo, request.query_params.get("ref"))
        except GitRepoError as exc:
            return api_error_response(str(exc))
        search = str(request.query_params.get("search") or "").strip()
        try:
            limit = min(max(int(request.query_params.get("limit") or 100), 1), 500)
        except (TypeError, ValueError):
            return api_error_response("limit 参数不合法")
        try:
            repo_dir = _git_shallow_clone(repo, ref)
        except GitRepoError as exc:
            return api_error_response(str(exc))
        try:
            out = _run_git(repo, ["ls-tree", "-r", "--name-only", "-z", "HEAD"])
        except GitRepoError as exc:
            return api_error_response(str(exc))
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)
        files = [name for name in out.split("\0") if name]
        if search:
            keyword = search.lower()
            files = [name for name in files if keyword in name.lower()]
        return api_ok_response({"ref": ref, "files": files[:limit]})

    @action(methods=["POST"], detail=True, url_path="load")
    def load(self, request, pk=None):
        """加载仓库中指定文件内容（供脚本/Playbook/Module 新建时导入）。"""
        repo = self.get_object()
        file_path = str(request.data.get("path") or "").strip()
        if not file_path:
            return api_error_response("文件路径不能为空")
        try:
            ref = _validated_ref(repo, request.data.get("ref"))
        except GitRepoError as exc:
            return api_error_response(str(exc))
        try:
            repo_dir = _git_shallow_clone(repo, ref)
        except GitRepoError as exc:
            return api_error_response(str(exc))
        try:
            full = _resolve_repo_file(repo_dir, file_path)
            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except GitRepoError as exc:
            return api_error_response(str(exc))
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)
        return api_ok_response({"ref": ref, "name": file_path, "content": content})


class JenkinsJobViewSet(WorkflowResourceProtectionMixin, StandardModelViewSet):
    workflow_node_type = NodeType.JENKINS
    workflow_resource_label = "Jenkins Job"
    http_method_names = ["get", "post", "head", "options"]
    queryset = JenkinsJob.objects.select_related("server").all()
    serializer_class = JenkinsJobSerializer
    ordering_fields = ("id", "name", "last_synced_at", "updated_at")
    filterset_fields = ("server", "is_active")
    search_fields = ("name", "server__name")

    @action(methods=["GET"], detail=True, url_path="parameters")
    def parameters(self, request, pk=None):
        """探测 Jenkins 任务定义的构建参数，供流程设计配置参数映射时自动带出。"""
        from apps.jobs.node_executors import fetch_jenkins_job_parameter_definitions

        job = self.get_object()
        try:
            definitions = fetch_jenkins_job_parameter_definitions(job.server, job.name)
        except Exception as exc:
            logger.warning("Jenkins Job %s parameter probe failed: %s", job.id, exc)
            return api_error_response(f"探测 Jenkins 参数失败：{exc}")
        if definitions is None:
            return api_error_response("Jenkins 未返回参数定义，请检查任务地址与账号权限后重试")
        return api_ok_response(definitions)

    @action(methods=["POST"], detail=True, url_path="run")
    def run_job(self, request, pk=None):
        from apps.jobs.application.runs import create_trial_run

        job = self.get_object()
        parameters = request.data.get("parameters") or {}
        try:
            run = create_trial_run(
                node_type=NodeType.JENKINS,
                resource_id=job.id,
                node_name=f"Jenkins job trial: {job.name}",
                config={"parameters": parameters},
                input_vars={},
                triggered_by=request.user,
            )
        except Exception as exc:
            logger.exception("Jenkins Job %s trial run failed", job.id)
            return api_error_response(str(exc) or exc.__class__.__name__)
        create_domain_audit_event(
            actor=request.user,
            action="automation.jenkins_job.run",
            resource_type="jenkins_job",
            resource_id=job.id,
            before={},
            after={"workflowRunId": run.id, "parameters": parameters},
            request=request,
        )
        return api_ok_response({"workflowRunId": run.id, "status": run.status})


class JenkinsBuildViewSet(StandardModelViewSet):
    http_method_names = ["get", "post", "head", "options"]
    queryset = JenkinsBuild.objects.select_related(
        "job", "job__server", "workflow_run", "node_run"
    ).all()
    serializer_class = JenkinsBuildSerializer
    ordering_fields = ("id", "status", "started_at", "finished_at", "created_at")
    filterset_fields = ("job", "job__server", "status", "workflow_run", "node_run")
    search_fields = ("job__name", "job__server__name", "result")

    @action(methods=["POST"], detail=True, url_path="refresh")
    def refresh_build(self, request, pk=None):
        import json
        from apps.jobs.node_executors import _jenkins_headers, _request

        build = self.get_object()
        server = build.job.server
        if not build.build_url and build.queue_url:
            status, _, body = _request(
                "GET",
                f"{build.queue_url.rstrip('/')}/api/json",
                _jenkins_headers(server),
                None,
                20,
                server.verify_ssl,
            )
            if status == 200:
                queue_data = json.loads(body or "{}")
                executable = queue_data.get("executable") or {}
                if executable.get("url"):
                    build.build_url = executable["url"]
                    build.build_number = executable.get("number")
                    build.status = JenkinsBuild.Status.RUNNING
                    build.started_at = build.started_at or timezone.now()
        if build.build_url:
            offset = len((build.console_output or "").encode())
            _, _, log_text = _request(
                "GET",
                f"{build.build_url.rstrip('/')}/logText/progressiveText?start={offset}",
                _jenkins_headers(server),
                None,
                20,
                server.verify_ssl,
            )
            if log_text:
                build.console_output += log_text
            status, _, body = _request(
                "GET",
                f"{build.build_url.rstrip('/')}/api/json",
                _jenkins_headers(server),
                None,
                20,
                server.verify_ssl,
            )
            if status == 200:
                build_data = json.loads(body or "{}")
                if not build_data.get("building", False):
                    build.result = build_data.get("result") or "UNKNOWN"
                    build.status = (
                        JenkinsBuild.Status.SUCCESS
                        if build.result == "SUCCESS"
                        else JenkinsBuild.Status.ABORTED
                        if build.result == "ABORTED"
                        else JenkinsBuild.Status.FAILED
                    )
                    build.finished_at = build.finished_at or timezone.now()
        build.save()
        return api_ok_response(self.get_serializer(build).data)

    @action(methods=["POST"], detail=True, url_path="stop")
    def stop_build(self, request, pk=None):
        from apps.jobs.node_executors import _jenkins_headers, _request

        build = self.get_object()
        if not build.build_url:
            return api_error_response("Build 尚未获得 Jenkins 构建地址")
        status, _, body = _request(
            "POST",
            f"{build.build_url.rstrip('/')}/stop",
            _jenkins_headers(build.job.server),
            b"",
            20,
            build.job.server.verify_ssl,
        )
        if status not in {200, 201, 302}:
            return api_error_response(f"停止 Build 失败：HTTP {status} {body}")
        build.status = JenkinsBuild.Status.ABORTED
        build.result = "ABORTED"
        build.finished_at = timezone.now()
        build.save(update_fields=["status", "result", "finished_at", "updated_at"])
        return api_ok_response(self.get_serializer(build).data)


class NotificationChannelViewSet(
    WorkflowResourceProtectionMixin, AutomationAuditModelViewSet
):
    workflow_resource_label = "通知通道"
    audit_action_prefix = "automation.notification_channel"
    audit_resource_type = "notification_channel"
    queryset = NotificationChannel.objects.select_related(
        "created_by", "updated_by"
    ).all()
    serializer_class = NotificationChannelSerializer
    ordering_fields = ("id", "name", "channel_type", "updated_at")
    filterset_fields = ("channel_type", "is_active")
    search_fields = ("name",)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.templates.exists():
            return api_error_response("该通知通道已被模板引用，不能删除，可将通道停用")
        return super().destroy(request, *args, **kwargs)


class NotificationTemplateViewSet(
    WorkflowResourceProtectionMixin, AutomationAuditModelViewSet
):
    workflow_node_type = NodeType.NOTIFY
    workflow_resource_label = "通知模板"
    audit_action_prefix = "automation.notification_template"
    audit_resource_type = "notification_template"
    queryset = NotificationTemplate.objects.select_related(
        "channel", "created_by", "updated_by"
    ).all()
    serializer_class = NotificationTemplateSerializer
    ordering_fields = ("id", "name", "code", "updated_at")
    filterset_fields = ("channel", "is_active")
    search_fields = ("name", "code", "description")

    def _notification_graph(self, data):
        from django.shortcuts import get_object_or_404

        version_id = data.get("workflowVersionId")
        if data["scenario"] != "workflow" or version_id is None:
            return None
        graph = serialize_graph(
            get_object_or_404(
                WorkflowVersion,
                pk=version_id,
                status=WorkflowVersion.Status.PUBLISHED,
                workflow__status=WorkflowTemplate.Status.PUBLISHED,
            )
        )
        api_ids = [
            node["resourceId"]
            for node in graph["nodes"]
            if node["type"] == "api" and str(node.get("resourceId", "")).isdigit()
        ]
        extractors = dict(
            ApiEndpoint.objects.filter(pk__in=api_ids).values_list(
                "pk", "output_extractors"
            )
        )
        for node in graph["nodes"]:
            if node["type"] == "api" and str(node.get("resourceId", "")).isdigit():
                node["resourceSnapshot"] = {
                    "definition": {
                        "output_extractors": extractors.get(int(node["resourceId"]), [])
                    }
                }
        return graph

    @action(methods=["GET"], detail=False, url_path="variables")
    def variables(self, request):
        from .notification_preview import notification_catalog

        serializer = NotificationPreviewSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = notification_catalog(data["scenario"], self._notification_graph(data))
        result["workflowVersions"] = [
            {
                "id": version.pk,
                "workflowName": version.workflow.name,
                "version": version.version,
            }
            for version in WorkflowVersion.objects.select_related("workflow")
            .filter(
                status=WorkflowVersion.Status.PUBLISHED,
                workflow__status=WorkflowTemplate.Status.PUBLISHED,
            )
            .order_by("workflow__name", "-version")
        ]
        return api_ok_response(result)

    @action(methods=["POST"], detail=False, url_path="preview")
    def preview(self, request):
        from .notification_preview import preview_notification

        serializer = NotificationPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = preview_notification(
                scenario=data["scenario"],
                subject=data["subjectTemplate"],
                body=data["bodyTemplate"],
                receivers=data["receiverTemplate"],
                sample_context=data["sampleContext"],
                graph=self._notification_graph(data),
            )
        except ValueError as exc:
            return api_error_response(str(exc))
        return api_ok_response(result)

    @action(methods=["POST"], detail=True, url_path="test-send")
    def test_send(self, request, pk=None):
        from apps.jobs.application.runs import create_trial_run
        from .notification_preview import notification_context, preview_notification

        template = self.get_object()
        serializer = NotificationPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        receivers = request.data.get("receivers") or []
        try:
            graph = self._notification_graph(data)
            context = notification_context(
                data["scenario"], data["sampleContext"], graph
            )
            preview = preview_notification(
                scenario=data["scenario"],
                subject=template.subject_template,
                body=template.body_template,
                receivers=template.receiver_template,
                sample_context=context,
                graph=graph,
            )
            if not preview["valid"]:
                return api_error_response("；".join(preview["errors"].values()))
            run = create_trial_run(
                node_type=NodeType.NOTIFY,
                resource_id=template.id,
                node_name=f"Notification test: {template.name}",
                config={"receivers": receivers, "notificationTestContext": context},
                triggered_by=request.user,
            )
        except Exception as exc:
            logger.exception("Notification template test %s failed", template.id)
            return api_error_response(str(exc) or exc.__class__.__name__)
        create_domain_audit_event(
            actor=request.user,
            action="automation.notification_template.test_send",
            resource_type="notification_template",
            resource_id=template.id,
            before={},
            after={"workflowRunId": run.id, "receivers": receivers},
            request=request,
        )
        return api_ok_response({"workflowRunId": run.id, "status": run.status})


class NotificationRecordViewSet(StandardModelViewSet):
    http_method_names = ["get", "head", "options"]
    queryset = NotificationRecord.objects.select_related(
        "template", "channel", "workflow_run", "node_run"
    ).all()
    serializer_class = NotificationRecordSerializer
    ordering_fields = ("id", "status", "sent_at", "created_at")
    filterset_fields = ("status", "template", "channel", "workflow_run", "node_run")
    search_fields = ("subject", "body", "failure_reason")

    def get_queryset(self):
        from apps.jobs.run_access import visible_runs

        base = super().get_queryset()
        runs = visible_runs(
            base.filter(workflow_run__isnull=False),
            self.request.user,
            owner="workflow_run__triggered_by",
        )
        if self.request.user.is_superuser:
            return base.filter(
                Q(pk__in=runs.values("pk"))
                | Q(alert_key__startswith="cmdb-sync-failure:")
                | Q(alert_key__startswith="provisioning:")
                | Q(alert_key__startswith="security:")
            )
        from apps.provisioning.models import ProvisioningRequest

        own_requests = ProvisioningRequest.objects.filter(
            created_by=self.request.user
        ).values_list("pk", flat=True)
        return base.filter(
            Q(pk__in=runs.values("pk"))
            | Q(
                alert_key__startswith="security:",
                context__delivery__actorId=self.request.user.pk,
            )
            | Q(
                alert_key__startswith="provisioning:",
                context__delivery__requestId__in=own_requests,
            )
        )


class NotificationEmailSettingsView(APIView):
    """系统设置：SMTP 邮件服务器配置。"""

    @extend_schema(responses=_EMAIL_SETTINGS_RESPONSE)
    def get(self, request):
        return api_ok_response(get_email_settings())

    @extend_schema(
        request=EmailSettingsInputSerializer,
        responses=_EMAIL_SETTINGS_RESPONSE,
    )
    def put(self, request):
        try:
            data = save_email_settings(request.data or {})
        except ValueError as exc:
            return api_error_response(str(exc))
        return api_ok_response(data)


class NotificationEmailTestView(APIView):
    """系统设置：发送测试邮件。"""

    @extend_schema(
        request=EmailTestRecipientSerializer,
        responses=api_envelope_serializer(
            "NotificationEmailTestResponse", EmailTestRecipientSerializer
        ),
    )
    def post(self, request):
        recipient = str((request.data or {}).get("recipient") or "").strip()
        if "@" not in recipient:
            return api_error_response("请输入有效的收件人邮箱")
        try:
            send_test_email(recipient)
        except Exception as exc:
            logger.exception("Notification email test failed")
            return api_error_response(f"测试邮件发送失败：{exc}")
        return api_ok_response({"recipient": recipient})


class NotificationEmailConnectionTestView(APIView):
    """系统设置：使用表单值测试 SMTP 连接。"""

    @extend_schema(
        request=EmailConnectionInputSerializer,
        responses=_NOTIFICATION_CONNECTION_RESPONSE,
    )
    def post(self, request):
        try:
            check_email_connection(request.data or {})
        except ValueError as exc:
            return api_error_response(str(exc))
        except Exception as exc:
            logger.exception("Notification email connection test failed")
            return api_error_response(f"连接失败：{exc}")
        return api_ok_response({"connected": True})


class NotificationHistorySettingsView(APIView):
    """系统设置：通知历史记录清理配置。"""

    @extend_schema(responses=_NOTIFICATION_HISTORY_SETTINGS_RESPONSE)
    def get(self, request):
        return api_ok_response(get_history_settings())

    @extend_schema(
        request=NotificationHistorySettingsSerializer,
        responses=_NOTIFICATION_HISTORY_SETTINGS_RESPONSE,
    )
    def put(self, request):
        try:
            data = save_history_settings(request.data or {})
        except ValueError as exc:
            return api_error_response(str(exc))
        return api_ok_response(data)


class NotificationHistoryPurgeView(APIView):
    """系统设置：立即清理通知历史记录。"""

    @extend_schema(
        request=NotificationHistoryPurgeInputSerializer,
        responses=api_envelope_serializer(
            "NotificationHistoryPurgeResponse", NotificationHistoryPurgeResultSerializer
        ),
    )
    def post(self, request):
        payload = request.data or {}
        dry_run = bool(payload.get("dryRun"))
        raw_days = payload.get("retentionDays")
        retention_days = None
        if raw_days is not None:
            try:
                retention_days = parse_retention_days(raw_days)
            except ValueError as exc:
                return api_error_response(str(exc))
        return api_ok_response(
            purge_notification_history(dry_run=dry_run, retention_days=retention_days)
        )


class NotificationAppSettingsView(APIView):
    """系统设置：企业微信 / 钉钉 / 飞书应用凭据。"""

    provider = ""

    def get(self, request):
        return api_ok_response(get_app_settings(self.provider))

    def put(self, request):
        try:
            data = save_app_settings(self.provider, request.data or {})
        except ValueError as exc:
            return api_error_response(str(exc))
        return api_ok_response(data)


class NotificationAppConnectionTestView(APIView):
    """系统设置：使用表单值测试应用凭据。"""

    provider = ""

    @extend_schema(
        request=NotificationAppConnectionInputSerializer,
        responses=_NOTIFICATION_CONNECTION_RESPONSE,
    )
    def post(self, request):
        try:
            check_app_connection(self.provider, request.data or {})
        except ValueError as exc:
            return api_error_response(str(exc))
        except Exception:
            logger.exception("Notification app connection test failed")
            return api_error_response("连接失败，请稍后重试")
        return api_ok_response({"connected": True})


@extend_schema_view(
    get=extend_schema(responses=_NOTIFICATION_APP_SETTINGS_RESPONSE),
    put=extend_schema(
        request=WecomSettingsInputSerializer,
        responses=_NOTIFICATION_APP_SETTINGS_RESPONSE,
    ),
)
class WecomSettingsView(NotificationAppSettingsView):
    provider = PROVIDER_WECOM


@extend_schema_view(
    get=extend_schema(responses=_NOTIFICATION_APP_SETTINGS_RESPONSE),
    put=extend_schema(
        request=DingtalkSettingsInputSerializer,
        responses=_NOTIFICATION_APP_SETTINGS_RESPONSE,
    ),
)
class DingtalkSettingsView(NotificationAppSettingsView):
    provider = PROVIDER_DINGTALK


@extend_schema_view(
    get=extend_schema(responses=_NOTIFICATION_APP_SETTINGS_RESPONSE),
    put=extend_schema(
        request=NotificationAppConnectionInputSerializer,
        responses=_NOTIFICATION_APP_SETTINGS_RESPONSE,
    ),
)
class FeishuSettingsView(NotificationAppSettingsView):
    provider = PROVIDER_FEISHU


class WecomConnectionTestView(NotificationAppConnectionTestView):
    provider = PROVIDER_WECOM


class DingtalkConnectionTestView(NotificationAppConnectionTestView):
    provider = PROVIDER_DINGTALK


class FeishuConnectionTestView(NotificationAppConnectionTestView):
    provider = PROVIDER_FEISHU

from common.workflow.node_types import NodeType
from common.workflow.node_types import CONTROL_NODE_TYPES
from common.workflow.schema import validate_graph
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Count, Max
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.views import APIView

from common.api.responses import api_error_response, api_ok_response
from common.api.viewsets import StandardModelViewSet
from apps.audit_center.services import create_domain_audit_event

import logging

logger = logging.getLogger(__name__)

from .audit import build_automation_audit_snapshot
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
from .serializers import (
    ApiEndpointSerializer,
    AnsibleNodeResourceCreateSerializer,
    AutomationTemplateSerializer,
    CommandAtomSerializer,
    CommandVersionSerializer,
    JenkinsServerSerializer,
    JenkinsBuildSerializer,
    JenkinsJobSerializer,
    NotificationChannelSerializer,
    NotificationRecordSerializer,
    NotificationTemplateSerializer,
    WorkflowEdgeSerializer,
    WorkflowNodeSerializer,
    WorkflowTemplateSerializer,
    WorkflowVersionSerializer,
)
from .node_resources import node_resource_catalog
from .workflow_graph import (
    replace_graph,
    serialize_graph,
)


class AutomationTemplateView(APIView):
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
    def get(self, request):
        return api_ok_response(
            node_resource_catalog(request.query_params.get("node_type") or "")
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

        latest = command.versions.order_by("-version").first()
        next_version = latest.version + 1 if latest else 1
        mutable = request.data.copy()
        mutable["command"] = command.id
        mutable.setdefault("version", next_version)
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

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status == instance.Status.PUBLISHED:
            return api_error_response("Published command versions cannot be modified")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # 业务层保护：检查是否有流程节点引用了该命令版本
        if WorkflowNode.objects.filter(command_version=instance).exists():
            return api_error_response("该命令版本已被流程节点引用，无法删除。可将其状态设为「归档」。")
        return super().destroy(request, *args, **kwargs)

    @action(methods=["POST"], detail=True, url_path="publish")
    def publish(self, request, pk=None):
        instance = self.get_object()
        validator = self.get_serializer(instance, data={}, partial=True)
        validator.is_valid(raise_exception=True)
        previous_status = instance.status
        # 自动归档同一命令下的旧 published 版本
        CommandVersion.objects.filter(
            command=instance.command,
            status=CommandVersion.Status.PUBLISHED,
        ).exclude(pk=instance.pk).update(status=CommandVersion.Status.ARCHIVED)
        instance.publish(request.user)
        if instance.command.status != CommandAtom.Status.PUBLISHED:
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
    def archive(self, request, pk=None):
        instance = self.get_object()
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

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
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
                    global_vars=source_version.global_vars,
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
    filterset_fields = ("workflow", "status")
    search_fields = ("workflow__name", "workflow__code")

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != instance.Status.DRAFT:
            return api_error_response("Only draft workflow versions can be modified")
        return super().update(request, *args, **kwargs)

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
            errors.append("工作流版本至少需要一个节点")
        elif not any(node.node_type not in CONTROL_NODE_TYPES for node in nodes):
            errors.append("工作流版本至少需要一个可执行任务节点")
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
            if node.timeout_seconds <= 0:
                errors.append(f"节点 {node.node_key} 超时时间必须大于 0")
        return list(dict.fromkeys(errors))

    @action(methods=["POST"], detail=True, url_path="publish")
    @transaction.atomic
    def publish(self, request, pk=None):
        instance = self.get_object()
        if instance.status != instance.Status.DRAFT:
            return api_error_response("只有草稿工作流版本可以发布")
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
            return api_error_response("只有草稿工作流版本可以修改")
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
                return api_error_response("只有草稿工作流版本可以新增节点")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if self._is_immutable_version(instance.workflow_version):
            return api_error_response("只有草稿工作流版本可以编辑节点")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if self._is_immutable_version(instance.workflow_version):
            return api_error_response("只有草稿工作流版本可以删除节点")
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
            return api_error_response("只有草稿工作流版本可以新增连线")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if self._is_immutable_version(instance.workflow_version):
            return api_error_response("只有草稿工作流版本可以编辑连线")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if self._is_immutable_version(instance.workflow_version):
            return api_error_response("只有草稿工作流版本可以删除连线")
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
                    "global": {},
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


class JenkinsJobViewSet(WorkflowResourceProtectionMixin, StandardModelViewSet):
    workflow_node_type = NodeType.JENKINS
    workflow_resource_label = "Jenkins Job"
    http_method_names = ["get", "post", "head", "options"]
    queryset = JenkinsJob.objects.select_related("server").all()
    serializer_class = JenkinsJobSerializer
    ordering_fields = ("id", "name", "last_synced_at", "updated_at")
    filterset_fields = ("server", "is_active")
    search_fields = ("name", "server__name")

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

    @action(methods=["POST"], detail=True, url_path="test-send")
    def test_send(self, request, pk=None):
        from apps.jobs.application.runs import create_trial_run

        template = self.get_object()
        receivers = request.data.get("receivers") or []
        try:
            run = create_trial_run(
                node_type=NodeType.NOTIFY,
                resource_id=template.id,
                node_name=f"Notification test: {template.name}",
                config={"receivers": receivers},
                input_vars=request.data.get("inputVars") or {},
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


# End of automation API viewsets.

import json
import shutil
import tempfile

from django.db import models, transaction
from django.db.models.deletion import ProtectedError
from openpyxl import load_workbook
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView

from apps.audit_center.services import create_domain_audit_event
from common.api.responses import api_error_response, api_ok_response
from common.api.viewsets import StandardModelViewSet

from .audit import build_cmdb_audit_snapshot
from .services import resolve_group_host_ids
from .tasks import sync_asset_source
from .models import (
    AssetHost,
    AssetSource,
    AssetSyncRecord,
    Business,
    CredentialRef,
    HostGroup,
    HostGroupMembership,
    HostTag,
    HostTagBinding,
    ServiceTreeNode,
    WorkerPool,
)
from .serializers import (
    AssetHostSerializer,
    AssetSourceSerializer,
    AssetSyncRecordSerializer,
    BusinessSerializer,
    CredentialRefSerializer,
    HostGroupSerializer,
    HostTagSerializer,
    ServiceTreeNodeSerializer,
    WorkerPoolSerializer,
)


def _normalize_excel_header(value):
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _parse_id_list(value):
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if text.startswith("["):
        try:
            return _parse_id_list(json.loads(text))
        except json.JSONDecodeError:
            return []
    return [item.strip() for item in text.replace("，", ",").split(",") if item.strip()]


def _excel_host_row(header, values, default_group_ids):
    raw = {
        key: value
        for key, value in zip(header, values)
        if key and value not in (None, "")
    }

    def first(*keys, default=None):
        for key in keys:
            if raw.get(key) not in (None, ""):
                return raw[key]
        return default

    ansible_vars = {}
    username = first("username", "user", "ansible_user")
    if username:
        ansible_vars["ansible_user"] = str(username).strip()

    data = {
        "hostname": str(first("hostname", "host", "name", default="")).strip(),
        "primary_ip": str(first("primary_ip", "ip", "address", default="")).strip(),
        "asset_type": first("asset_type", "assettype", default="server"),
        "os_family": first("os_family", "os", "system", default="linux"),
        "os_type": str(first("os_type", "os_name", "distribution", default="")),
        "environment": str(first("environment", "env", default="")),
        "status": first("status", default="active"),
        "owner_team": str(first("owner_team", "owner", default="")),
        "app_code": str(first("app_code", "application", "app", default="")),
        "connection_type": first("connection_type", "connection", default="ssh"),
        "connection_port": _excel_number(
            first("connection_port", "port", default=22), 22
        ),
        "default_gateway": first("default_gateway", "gateway_id", default=None),
        "ansible_connection_vars": ansible_vars,
        "metadata": {
            "import_source": "excel",
            "description": str(first("description", "desc", "remark", default="")),
        },
        "source_type": "manual",
        "_group_ids": _parse_id_list(
            first("group_ids", "group_id", "groups", default=None)
        )
        or default_group_ids,
    }
    return data


def _excel_number(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class CMDBAuditModelViewSet(StandardModelViewSet):
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
            after=build_cmdb_audit_snapshot(serializer.instance),
        )

    def perform_update(self, serializer, request=None):
        instance = serializer.instance
        before = build_cmdb_audit_snapshot(instance)
        super().perform_update(serializer, request=request)
        self._create_audit_event(
            request,
            "update",
            serializer.instance,
            before=before,
            after=build_cmdb_audit_snapshot(serializer.instance),
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        before = build_cmdb_audit_snapshot(instance)
        try:
            response = super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return api_error_response("该数据仍被其他资源引用，无法删除")
        if not getattr(instance, "is_system", False):
            self._create_audit_event(request, "delete", instance, before=before)
        return response


class AssetHostViewSet(CMDBAuditModelViewSet):
    audit_action_prefix = "cmdb.host"
    audit_resource_type = "cmdb_host"
    queryset = (
        AssetHost.objects.select_related(
            "credential_ref",
            "default_gateway",
            "service_node",
            "asset_source",
        )
        .prefetch_related("group_memberships", "tag_bindings")
        .all()
    )
    serializer_class = AssetHostSerializer
    ordering_fields = ("id", "hostname", "primary_ip", "updated_at")
    filter_fields = (
        "os_family",
        "environment",
        "service_node",
        "status",
        "app_code",
    )
    search_fields = ("hostname", "primary_ip", "image_name", "app_code", "owner_team")

    def get_queryset(self):
        queryset = super().get_queryset()
        group_id = self.request.query_params.get("group_id")
        if group_id:
            host_ids = resolve_group_host_ids([group_id])
            queryset = queryset.filter(id__in=host_ids)
        return queryset.distinct()

    @action(methods=["POST"], detail=False, url_path="bulk-import")
    def bulk_import(self, request):
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(request=request)
        create_domain_audit_event(
            actor=request.user,
            action="cmdb.host.bulk_import",
            resource_type="cmdb_host",
            resource_id="",
            after={
                "created_count": len(serializer.instance),
                "host_ids": [str(host.id) for host in serializer.instance],
            },
            request=request,
        )
        return api_ok_response({"created": len(serializer.data)})

    @action(
        methods=["POST"],
        detail=False,
        url_path="excel-import",
        parser_classes=[MultiPartParser, FormParser],
    )
    def excel_import(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return api_error_response("请选择 Excel 文件")
        if not upload.name.lower().endswith(".xlsx"):
            return api_error_response("仅支持 .xlsx 文件")

        try:
            workbook = load_workbook(upload, read_only=True, data_only=True)
            worksheet = workbook.active
            rows = worksheet.iter_rows(values_only=True)
            header = next(rows, None)
            if not header:
                return api_error_response("Excel 文件没有表头")
            header = [_normalize_excel_header(value) for value in header]
            if not any(header):
                return api_error_response("Excel 表头不能为空")

            summary = {
                "total": 0,
                "created": 0,
                "skipped": 0,
                "invalid": [],
                "errors": [],
            }
            default_group_ids = _parse_id_list(
                request.data.get("group_ids") or request.data.get("group_id")
            )

            for row_number, values in enumerate(rows, start=2):
                if not any(value not in (None, "") for value in values):
                    continue
                summary["total"] += 1
                data = _excel_host_row(header, values, default_group_ids)
                if not data.get("hostname") or not data.get("primary_ip"):
                    summary["invalid"].append(
                        {"row": row_number, "message": "hostname 和 primary_ip 为必填项"}
                    )
                    continue

                if AssetHost.objects.filter(
                    hostname=data["hostname"],
                    primary_ip=data["primary_ip"],
                ).exists():
                    summary["skipped"] += 1
                    continue

                group_ids = data.pop("_group_ids", [])
                serializer = self.get_serializer(data=data)
                if not serializer.is_valid():
                    summary["invalid"].append(
                        {
                            "row": row_number,
                            "message": serializer.errors,
                        }
                    )
                    continue
                try:
                    with transaction.atomic():
                        host = serializer.save(request=request)
                        HostGroupMembership.objects.bulk_create(
                            [
                                HostGroupMembership(host=host, group_id=group_id)
                                for group_id in group_ids
                            ],
                            ignore_conflicts=True,
                        )
                    summary["created"] += 1
                except Exception as exc:
                    summary["errors"].append({"row": row_number, "message": str(exc)})

            return api_ok_response(summary)
        except Exception as exc:
            return api_error_response(f"Excel 文件解析失败: {exc}")

    @action(methods=["GET", "POST"], detail=True, url_path="relations")
    def relations(self, request, pk=None):
        host = self.get_object()
        if request.method == "GET":
            group_ids = list(
                HostGroupMembership.objects.filter(host=host).values_list(
                    "group_id",
                    flat=True,
                )
            )
            tag_ids = list(
                HostTagBinding.objects.filter(host=host).values_list(
                    "tag_id",
                    flat=True,
                )
            )
            return api_ok_response(
                {
                    "groupIds": [str(group_id) for group_id in group_ids],
                    "tagIds": [str(tag_id) for tag_id in tag_ids],
                }
            )

        group_ids = request.data.get("groupIds", [])
        tag_ids = request.data.get("tagIds", [])
        before = {
            "groupIds": [
                str(group_id)
                for group_id in HostGroupMembership.objects.filter(
                    host=host
                ).values_list("group_id", flat=True)
            ],
            "tagIds": [
                str(tag_id)
                for tag_id in HostTagBinding.objects.filter(host=host).values_list(
                    "tag_id", flat=True
                )
            ],
        }
        HostGroupMembership.objects.filter(host=host).delete()
        HostTagBinding.objects.filter(host=host).delete()
        HostGroupMembership.objects.bulk_create(
            [
                HostGroupMembership(host=host, group_id=group_id)
                for group_id in group_ids
            ],
            ignore_conflicts=True,
        )
        HostTagBinding.objects.bulk_create(
            [HostTagBinding(host=host, tag_id=tag_id) for tag_id in tag_ids],
            ignore_conflicts=True,
        )
        after = {
            "groupIds": [str(group_id) for group_id in group_ids],
            "tagIds": [str(tag_id) for tag_id in tag_ids],
        }
        self._create_audit_event(
            request,
            "relations.update",
            host,
            before=before,
            after=after,
        )
        return api_ok_response(after)


class HostGroupViewSet(CMDBAuditModelViewSet):
    audit_action_prefix = "cmdb.host_group"
    audit_resource_type = "cmdb_host_group"
    queryset = HostGroup.objects.select_related("parent").all()
    serializer_class = HostGroupSerializer
    ordering_fields = ("id", "name", "updated_at")
    filter_fields = ("id", "parent", "group_type", "is_active")
    search_fields = ("name", "description")

    @action(methods=["GET", "POST"], detail=True, url_path="members")
    def members(self, request, pk=None):
        group = self.get_object()
        if request.method == "GET":
            if group.group_type == HostGroup.GroupType.DYNAMIC:
                return api_ok_response(
                    {
                        "hostIds": [
                            str(host_id)
                            for host_id in resolve_group_host_ids([group.id])
                        ]
                    }
                )
            host_ids = list(
                HostGroupMembership.objects.filter(group=group).values_list(
                    "host_id",
                    flat=True,
                )
            )
            return api_ok_response({"hostIds": [str(host_id) for host_id in host_ids]})
        if group.group_type == HostGroup.GroupType.DYNAMIC:
            return api_error_response("动态分组不能手工维护成员")
        host_ids = request.data.get("hostIds", [])
        before = {
            "hostIds": [
                str(host_id)
                for host_id in HostGroupMembership.objects.filter(
                    group=group
                ).values_list("host_id", flat=True)
            ]
        }
        HostGroupMembership.objects.filter(group=group).delete()
        HostGroupMembership.objects.bulk_create(
            [HostGroupMembership(group=group, host_id=host_id) for host_id in host_ids]
        )
        self._create_audit_event(
            request,
            "members.update",
            group,
            before=before,
            after={"hostIds": [str(host_id) for host_id in host_ids]},
        )
        return api_ok_response()


class HostTagViewSet(CMDBAuditModelViewSet):
    audit_action_prefix = "cmdb.tag"
    audit_resource_type = "cmdb_host_tag"
    queryset = HostTag.objects.all()
    serializer_class = HostTagSerializer
    ordering_fields = ("id", "key", "value")
    filter_fields = ("key", "value")
    search_fields = ("key", "value")


class CredentialRefViewSet(CMDBAuditModelViewSet):
    audit_action_prefix = "cmdb.credential"
    audit_resource_type = "cmdb_credential_ref"
    queryset = CredentialRef.objects.all()
    serializer_class = CredentialRefSerializer
    ordering_fields = ("id", "name", "type", "scope", "updated_at")
    filter_fields = ("type", "scope")
    search_fields = ("name", "secret_ref")

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .annotate(host_count=models.Count("assethost", distinct=True))
        )

    @action(detail=False, methods=["get"])
    def available(self, request):
        """返回对指定主机上下文可用的凭据（按 scope 过滤）。"""
        environment = request.query_params.get("environment", "")
        group_ids = [
            gid for gid in request.query_params.get("group_ids", "").split(",") if gid
        ]
        qs = self.get_queryset()
        scope_filter = models.Q(
            scope__in=[
                CredentialRef.Scope.GLOBAL,
                CredentialRef.Scope.HOST,
            ]
        )
        if environment:
            scope_filter |= models.Q(
                scope=CredentialRef.Scope.ENVIRONMENT,
                metadata__environment=environment,
            )
        if group_ids:
            scope_filter |= models.Q(
                scope=CredentialRef.Scope.HOST_GROUP,
                metadata__group_id__in=group_ids,
            )
        qs = qs.filter(scope_filter)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["post"], url_path="test-connection")
    def test_connection(self, request):
        """Test SSH/WinRM connectivity using credential + target host."""
        credential_id = request.data.get("credential_id")
        host_ip = request.data.get("host_ip", "").strip()
        port = request.data.get("port")
        gateway_id = request.data.get("gateway_id")

        if not credential_id:
            return api_error_response("请选择凭据")
        if not host_ip:
            return api_error_response("请输入目标主机 IP")

        credential = CredentialRef.objects.filter(id=credential_id).first()
        if not credential:
            return api_error_response("凭据不存在")

        effective_port = int(port) if port else (credential.effective_port or 22)

        conn_type = credential.connection_type or "ssh"
        private_data_dir = ""
        try:
            from apps.jobs.services import prepare_host_gateway_execution
            from apps.ops.adapters import AnsibleExecutionInput
            from apps.ops.services import JumpServerAnsibleService
            from apps.ops.workflow.inventory import build_inventory

            hosts, group_vars, private_data_dir = prepare_host_gateway_execution(
                [
                    {
                        "host_id": 0,
                        "hostname": "target",
                        "ip": host_ip,
                        "os_family": "windows" if conn_type == "winrm" else "linux",
                        "connection_type": conn_type,
                        "connection_port": effective_port,
                        "credential_ref_id": credential.id,
                        "default_gateway_id": gateway_id,
                    }
                ]
            )
            inventory_text = build_inventory(hosts, group_vars)
            if not private_data_dir:
                private_data_dir = tempfile.mkdtemp(prefix="devops-connection-test-")

            service = JumpServerAnsibleService()
            execution = AnsibleExecutionInput(
                inventory=inventory_text,
                module="ping",
                host_pattern="all",
                private_data_dir=private_data_dir,
                timeout=15,
            )
            cb = service.run(execution)
            if cb.is_success():
                return api_ok_response({"success": True, "message": "连接成功"})
            error_msg = ""
            for host_data in cb.result.get("dark", {}).values():
                for detail in host_data.values():
                    error_msg = detail.get("stderr") or detail.get("res", {}).get(
                        "msg", ""
                    )
                    break
            for host_data in cb.result.get("failures", {}).values():
                for detail in host_data.values():
                    error_msg = detail.get("stderr") or detail.get("res", {}).get(
                        "msg", ""
                    )
                    break
            return api_ok_response({"success": False, "message": error_msg or "连接失败"})
        except Exception as exc:
            return api_ok_response({"success": False, "message": str(exc)})
        finally:
            if private_data_dir:
                shutil.rmtree(private_data_dir, ignore_errors=True)


class WorkerPoolViewSet(CMDBAuditModelViewSet):
    audit_action_prefix = "cmdb.worker_pool"
    audit_resource_type = "cmdb_worker_pool"
    queryset = WorkerPool.objects.all()
    serializer_class = WorkerPoolSerializer
    ordering_fields = ("id", "code", "name")
    filter_fields = ("code", "is_default", "is_active")
    search_fields = ("code", "name", "queue_name")


class BusinessViewSet(CMDBAuditModelViewSet):
    audit_action_prefix = "cmdb.business"
    audit_resource_type = "cmdb_business"
    queryset = Business.objects.all()
    serializer_class = BusinessSerializer
    ordering_fields = ("id", "code", "name", "updated_at")
    filter_fields = ("code", "is_active")
    search_fields = ("code", "name", "description")


class AssetSourceViewSet(CMDBAuditModelViewSet):
    audit_action_prefix = "cmdb.asset_source"
    audit_resource_type = "cmdb_asset_source"
    queryset = AssetSource.objects.all()
    serializer_class = AssetSourceSerializer
    ordering_fields = ("id", "code", "name", "source_type", "updated_at")
    filter_fields = ("source_type", "is_active")
    search_fields = ("code", "name", "endpoint", "description")

    @action(methods=["POST"], detail=True, url_path="sync")
    def sync(self, request, pk=None):
        source = self.get_object()
        assets = request.data.get("assets")
        if not isinstance(assets, list):
            return api_error_response("assets must be a JSON array")
        record = AssetSyncRecord.objects.create(
            source=source,
            total_count=len(assets),
            payload=assets,
        )
        if hasattr(sync_asset_source, "apply_async"):
            task = sync_asset_source.apply_async(args=[record.id], queue="default")
        else:
            task = sync_asset_source.delay(record.id)
        record.task_id = getattr(task, "id", "") or ""
        record.save(update_fields=["task_id", "updated_at"])
        return api_ok_response(AssetSyncRecordSerializer(record).data)


class AssetSyncRecordViewSet(CMDBAuditModelViewSet):
    queryset = AssetSyncRecord.objects.select_related("source").all()
    serializer_class = AssetSyncRecordSerializer
    http_method_names = ("get", "head", "options")
    ordering_fields = ("id", "created_at", "status", "finished_at")
    filter_fields = ("source", "status")
    search_fields = ("task_id", "error_message")


class CMDBSearchView(APIView):
    def get(self, request):
        keyword = str(request.query_params.get("q", "")).strip()
        if not keyword:
            return api_ok_response(
                {
                    "hosts": [],
                    "businesses": [],
                    "serviceTreeNodes": [],
                    "assetSources": [],
                }
            )
        try:
            limit = min(max(int(request.query_params.get("limit", 20)), 1), 100)
        except (TypeError, ValueError):
            limit = 20
        hosts = AssetHost.objects.filter(
            models.Q(hostname__icontains=keyword)
            | models.Q(primary_ip__icontains=keyword)
            | models.Q(app_code__icontains=keyword)
        ).values("id", "hostname", "primary_ip", "asset_type", "status")[:limit]
        businesses = Business.objects.filter(
            models.Q(code__icontains=keyword) | models.Q(name__icontains=keyword)
        ).values("id", "code", "name")[:limit]
        nodes = ServiceTreeNode.objects.filter(
            models.Q(code__icontains=keyword) | models.Q(name__icontains=keyword)
        ).values("id", "business_id", "code", "name", "node_type")[:limit]
        sources = AssetSource.objects.filter(
            models.Q(code__icontains=keyword) | models.Q(name__icontains=keyword)
        ).values("id", "code", "name", "source_type")[:limit]
        return api_ok_response(
            {
                "hosts": list(hosts),
                "businesses": list(businesses),
                "serviceTreeNodes": list(nodes),
                "assetSources": list(sources),
            }
        )


class ServiceTreeNodeViewSet(CMDBAuditModelViewSet):
    audit_action_prefix = "cmdb.service_tree_node"
    audit_resource_type = "cmdb_service_tree_node"
    queryset = ServiceTreeNode.objects.select_related("business", "parent").all()
    serializer_class = ServiceTreeNodeSerializer
    ordering_fields = ("id", "code", "name", "node_type", "sort_order", "updated_at")
    filter_fields = ("business", "parent", "node_type", "is_active")
    search_fields = ("code", "name", "description")

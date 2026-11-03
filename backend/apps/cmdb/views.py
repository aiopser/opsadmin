import json
import shutil
import tempfile

from django.db import models, transaction
from django.db.models.deletion import ProtectedError
from openpyxl import load_workbook
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.audit_center.services import create_domain_audit_event
from common.api.responses import api_error_response, api_ok_response
from common.api.viewsets import StandardModelViewSet
from common.api.schema import api_envelope_serializer
from .schema_serializers import CMDBSearchSerializer

from .audit import build_cmdb_audit_snapshot
from .services import collect_group_tree_ids, resolve_group_host_ids
from .sync_preview import cloud_asset_digest, preview_asset_sync
from .tasks import collect_cloud_import_preview, sync_asset_source
from .models import (
    AssetHost,
    AssetProbe,
    AssetSource,
    AssetSyncRecord,
    CloudImportPreview,
    CredentialRef,
    HostGroup,
    HostGroupMembership,
    HostTag,
    HostTagBinding,
)
from .serializers import (
    AssetHostSerializer,
    AssetProbeSerializer,
    AssetSourceSerializer,
    AssetSyncRecordSerializer,
    CredentialRefSerializer,
    HostGroupSerializer,
    HostTagSerializer,
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
        "internal_ip": str(
            first("internal_ip", "primary_ip", "ip", "address", default="")
        ).strip(),
        "external_ip": str(first("external_ip", "public_ip", default="")).strip()
        or None,
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
        "_group_names": [
            name.strip()
            for name in str(first("group_names", "group_name", default=""))
            .replace("，", ",")
            .split(",")
            if name.strip()
        ],
    }
    return data


def _excel_number(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _validated_relation_ids(data, field, queryset):
    values = data.get(field, [])
    if not isinstance(values, list) or any(
        isinstance(value, bool)
        or not isinstance(value, (int, str))
        or not str(value).isascii()
        or not str(value).isdigit()
        for value in values
    ):
        raise serializers.ValidationError({field: "必须提供有效 ID 列表"})
    ids = [int(value) for value in values]
    if any(value <= 0 or value > 9223372036854775807 for value in ids):
        raise serializers.ValidationError({field: "ID 必须是有效的正整数"})
    if len(ids) != len(set(ids)):
        raise serializers.ValidationError({field: "ID 不可重复"})
    if queryset.filter(pk__in=ids).count() != len(ids):
        raise serializers.ValidationError({field: "部分关联对象不存在，请刷新后重试"})
    return ids


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
            "asset_source",
        )
        .prefetch_related("group_memberships", "tag_bindings")
        .all()
    )
    serializer_class = AssetHostSerializer
    ordering_fields = ("id", "hostname", "internal_ip", "updated_at")
    filterset_fields = (
        "os_family",
        "environment",
        "status",
        "app_code",
    )
    search_fields = (
        "hostname",
        "internal_ip",
        "external_ip",
        "image_name",
        "app_code",
        "owner_team",
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        # 按分组过滤：含子分组级联（选中父分组时列出全部子孙分组的主机）
        group_id = self.request.query_params.get("group_id")
        if group_id:
            group_ids = [gid for gid in group_id.split(",") if gid.strip().isdigit()]
            host_ids = resolve_group_host_ids(collect_group_tree_ids(group_ids))
            queryset = queryset.filter(id__in=host_ids)
        # 按 id 集合过滤（编辑任务单回填主机 chips 等场景）
        ids = self.request.query_params.get("ids")
        if ids:
            id_list = [int(item) for item in ids.split(",") if item.strip().isdigit()]
            queryset = queryset.filter(id__in=id_list)
        return queryset.distinct()

    def destroy(self, request, *args, **kwargs):
        """支持 DELETE hosts/1,2,3 逗号分隔批量删除，批量时逐条记录审计并保留引用保护。"""
        raw_pk = str(kwargs.get(self.lookup_url_kwarg or self.lookup_field, ""))
        ids = [item for item in raw_pk.split(",") if item]

        if len(ids) > 1:
            queryset = self.get_queryset().filter(pk__in=ids)
            instances = list(queryset)
            snapshots = {i.id: build_cmdb_audit_snapshot(i) for i in instances}
            try:
                deleted, _ = queryset.delete()
            except ProtectedError:
                return api_error_response("该数据仍被其他资源引用，无法删除")
            for i in instances:
                self._create_audit_event(request, "delete", i, before=snapshots[i.id])
            return api_ok_response({"deleted": deleted})

        return super().destroy(request, *args, **kwargs)

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
                if not data.get("hostname") or not data.get("internal_ip"):
                    summary["invalid"].append(
                        {"row": row_number, "message": "hostname 和 internal_ip 为必填项"}
                    )
                    continue

                if AssetHost.objects.filter(
                    hostname=data["hostname"],
                    internal_ip=data["internal_ip"],
                ).exists():
                    summary["skipped"] += 1
                    continue

                group_ids = data.pop("_group_ids", [])
                group_names = data.pop("_group_names", [])
                if group_names:
                    static_groups = {
                        group.name: group.id
                        for group in HostGroup.objects.filter(
                            name__in=group_names,
                            group_type=HostGroup.GroupType.STATIC,
                        )
                    }
                    missing = [
                        name for name in group_names if name not in static_groups
                    ]
                    if missing:
                        summary["invalid"].append(
                            {
                                "row": row_number,
                                "message": f"静态分组不存在: {', '.join(missing)}",
                            }
                        )
                        continue
                    group_ids = list(
                        dict.fromkeys([*group_ids, *static_groups.values()])
                    )
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

        group_ids = _validated_relation_ids(
            request.data, "groupIds", HostGroup.objects.all()
        )
        tag_ids = _validated_relation_ids(request.data, "tagIds", HostTag.objects.all())
        after = {
            "groupIds": [str(group_id) for group_id in group_ids],
            "tagIds": [str(tag_id) for tag_id in tag_ids],
        }
        with transaction.atomic():
            host = AssetHost.objects.select_for_update().get(pk=host.pk)
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
                ]
            )
            HostTagBinding.objects.bulk_create(
                [HostTagBinding(host=host, tag_id=tag_id) for tag_id in tag_ids]
            )
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
    filterset_fields = ("id", "parent", "group_type", "is_active")
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
        host_ids = _validated_relation_ids(
            request.data, "hostIds", AssetHost.objects.all()
        )
        with transaction.atomic():
            group = HostGroup.objects.select_for_update().get(pk=group.pk)
            if group.group_type == HostGroup.GroupType.DYNAMIC:
                return api_error_response("动态分组不能手工维护成员")
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
                [
                    HostGroupMembership(group=group, host_id=host_id)
                    for host_id in host_ids
                ]
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
    filterset_fields = ("key", "value")
    search_fields = ("key", "value")


class CredentialRefViewSet(CMDBAuditModelViewSet):
    audit_action_prefix = "cmdb.credential"
    audit_resource_type = "cmdb_credential_ref"
    queryset = CredentialRef.objects.all()
    serializer_class = CredentialRefSerializer
    ordering_fields = ("id", "name", "type", "scope", "updated_at")
    filterset_fields = ("type", "scope")
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
        """Queue a connectivity probe; the routed worker pool executes it.

        Returns the probe id so the client can poll for the result. Scheduling
        failures (no access, no usable worker pool) surface synchronously as
        400/403; queueing happens after commit and is recovered by the
        scanner if the process dies first.
        """
        from .probes import schedule_asset_probe

        host_id = request.data.get("hostId")
        probe = schedule_asset_probe(
            actor=request.user, host_id=host_id, kind=AssetProbe.Kind.CONNECT
        )
        return api_ok_response({"probeId": probe.id, "status": probe.status})

    @extend_schema(
        parameters=[OpenApiParameter("probe_id", int, OpenApiParameter.PATH)]
    )
    @action(detail=False, methods=["get"], url_path=r"probes/(?P<probe_id>[^/.]+)")
    def probe_status(self, request, probe_id=None):
        """Poll one probe result (owner or superuser only)."""
        from apps.jobs.run_access import ALL, NONE, run_access_state

        state = run_access_state(request.user)
        if state == NONE:
            return api_error_response("Forbidden", code="A0403", http_status=403)
        probe = (
            AssetProbe.objects.select_related("host", "worker_pool")
            .filter(pk=probe_id)
            .first()
        )
        if probe is None or (state != ALL and probe.triggered_by_id != request.user.id):
            return api_error_response("Not found", code="A0400", http_status=404)
        return api_ok_response(AssetProbeSerializer(probe).data)


class AssetSourceViewSet(CMDBAuditModelViewSet):
    audit_action_prefix = "cmdb.asset_source"
    audit_resource_type = "cmdb_asset_source"
    queryset = AssetSource.objects.all()
    serializer_class = AssetSourceSerializer
    ordering_fields = ("id", "code", "name", "source_type", "updated_at")
    filterset_fields = ("source_type", "is_active")
    search_fields = ("code", "name", "endpoint", "description")

    @action(methods=["POST"], detail=False, url_path="test-cloud-connection")
    def test_cloud_connection(self, request):
        from django.shortcuts import get_object_or_404
        from .cloud import CloudCollectionError, probe_public_cloud
        from .crypto import decrypt_secret

        source = None
        if request.data.get("source_id"):
            try:
                source_id = int(request.data["source_id"])
            except (ValueError, TypeError):
                return api_error_response("云账号 ID 无效")
            source = get_object_or_404(self.get_queryset(), pk=source_id)
            self.check_object_permissions(request, source)
        serializer = self.get_serializer(
            source, data=request.data, partial=source is not None
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        provider = data.get("cloud_provider", getattr(source, "cloud_provider", ""))
        regions = data.get("regions", getattr(source, "regions", []))
        test_regions = request.data.get("test_regions", regions[:5])
        if (
            not isinstance(test_regions, list)
            or not 1 <= len(test_regions) <= 5
            or any(
                not isinstance(region, str) or region not in regions
                for region in test_regions
            )
            or len(test_regions) != len(set(test_regions))
        ):
            return api_error_response("请选择账号同步区域中的 1 至 5 个区域进行测试")
        try:
            if data.get("access_key_id"):
                credentials = {
                    key: data[key] for key in ("access_key_id", "access_key_secret")
                }
            else:
                credentials = json.loads(decrypt_secret(source.credentials_encrypted))
        except Exception:
            return api_error_response("无法读取已保存凭据，请重新填写完整 AccessKey")
        try:
            results = probe_public_cloud(provider, test_regions, credentials)
        except CloudCollectionError as exc:
            return api_error_response(str(exc))
        return api_ok_response(
            {
                "results": results,
                "untestedRegions": [
                    region for region in regions if region not in test_regions
                ],
            }
        )

    def get_queryset(self):
        queryset = super().get_queryset()
        if (
            self.request.query_params.get("exclude_source_type")
            == AssetSource.SourceType.CLOUD
        ):
            return queryset.exclude(source_type=AssetSource.SourceType.CLOUD)
        return queryset

    @action(methods=["POST"], detail=True, url_path="preview-cloud")
    def preview_cloud(self, request, pk=None):
        from datetime import timedelta
        from django.utils import timezone

        source = self.get_object()
        now = timezone.now()
        CloudImportPreview.objects.filter(expires_at__lt=now).delete()
        frozen = CloudImportPreview.objects.create(
            source=source,
            created_by=request.user,
            source_updated_at=source.updated_at,
            expires_at=now + timedelta(minutes=30),
        )
        try:
            collect_cloud_import_preview.apply_async(args=[frozen.pk], queue="task")
        except Exception:
            frozen.status = "failed"
            frozen.error_message = "云资产预览任务投递失败，请检查 Worker 队列"
            frozen.save(update_fields=["status", "error_message", "updated_at"])
            return api_error_response(frozen.error_message)
        return api_ok_response({"previewId": frozen.pk, "status": "pending"})

    @action(methods=["GET"], detail=True, url_path="preview-cloud-status")
    def preview_cloud_status(self, request, pk=None):
        from django.core import signing
        from django.utils import timezone

        source = self.get_object()
        preview_id = request.query_params.get("previewId", "")
        if not preview_id.isdigit():
            return api_error_response("预览 ID 无效")
        frozen = CloudImportPreview.objects.filter(
            pk=int(preview_id),
            source=source,
            created_by=request.user,
            expires_at__gt=timezone.now(),
        ).first()
        if frozen is None or frozen.source_updated_at != source.updated_at:
            return api_error_response("预览已过期或云账号配置已变化，请重新预览")
        if frozen.status == "failed":
            return api_error_response(frozen.error_message or "云资产拉取失败")
        if frozen.status != "ready":
            return api_ok_response({"previewId": frozen.pk, "status": "pending"})
        preview = preview_asset_sync(source, frozen.assets)
        preview["confirmationToken"] = signing.dumps(
            {
                "source": source.pk,
                "preview": frozen.pk,
                "digest": frozen.digest,
                "impactDigest": cloud_asset_digest(preview["rows"]),
            },
            salt="cmdb-cloud-preview",
        )
        return api_ok_response(preview)

    @action(methods=["POST"], detail=True, url_path="sync-cloud")
    @transaction.atomic
    def sync_cloud(self, request, pk=None):
        from django.core import signing
        from django.utils import timezone

        source = self.get_object()
        source = AssetSource.objects.select_for_update().get(pk=source.pk)
        try:
            token = signing.loads(
                request.data.get("confirmationToken", ""),
                salt="cmdb-cloud-preview",
                max_age=1800,
            )
        except signing.BadSignature:
            return api_error_response("预览确认已过期，请重新预览")
        if token.get("source") != source.pk:
            return api_error_response("预览确认与当前来源不匹配")
        frozen = (
            CloudImportPreview.objects.select_for_update()
            .filter(
                pk=token.get("preview"),
                source=source,
                created_by=request.user,
                expires_at__gt=timezone.now(),
            )
            .first()
        )
        if (
            frozen is None
            or frozen.status != "ready"
            or frozen.source_updated_at != source.updated_at
        ):
            return api_error_response("预览已过期或云账号配置已变化，请重新预览")
        assets = frozen.assets
        if (
            frozen.digest != token.get("digest")
            or cloud_asset_digest(assets) != frozen.digest
        ):
            return api_error_response("预览清单校验失败，请重新预览")
        preview = preview_asset_sync(source, assets)
        if token.get("impactDigest") and token["impactDigest"] != cloud_asset_digest(
            preview["rows"]
        ):
            return api_error_response("资产数据已变化，请重新读取并核对字段变化后再同步")
        selected_ids = request.data.get("selectedSourceIds")
        if (
            not isinstance(selected_ids, list)
            or not selected_ids
            or any(not isinstance(item, str) or not item for item in selected_ids)
            or len(selected_ids) != len(set(selected_ids))
        ):
            return api_error_response("请选择至少一台且不重复的云主机")
        valid_ids = {
            row["sourceId"] for row in preview["rows"] if row["action"] != "invalid"
        }
        if not set(selected_ids).issubset(valid_ids):
            return api_error_response("所选主机与预览结果不一致，请重新预览")
        selected = set(selected_ids)
        valid_indexes = {
            row["index"] - 1
            for row in preview["rows"]
            if row["sourceId"] in selected and row["action"] != "invalid"
        }
        selected_assets = [
            item for index, item in enumerate(assets) if index in valid_indexes
        ]
        from .sync_automation import collection_scope

        scope = collection_scope(source)
        scope["selectedCount"] = len(selected_assets)
        scope["readCount"] = len(assets)
        response = self._queue_sync(
            source, selected_assets, observed_at=frozen.updated_at, scope=scope
        )
        if response.status_code == 200:
            frozen.delete()
        return response

    @transaction.atomic
    def _queue_sync(self, source, assets, *, observed_at=None, scope=None):
        from .sync_automation import create_sync_record, dispatch_sync

        source = AssetSource.objects.select_for_update().get(pk=source.pk)
        if not source.is_active:
            return api_error_response("资产来源已停用")
        if AssetSyncRecord.objects.filter(
            source=source, status__in=["queued", "running"]
        ).exists():
            return api_error_response("该账号已有同步任务，请等待完成后重试")
        record = create_sync_record(
            source, assets, observed_at=observed_at, scope=scope
        )
        transaction.on_commit(lambda: dispatch_sync(record.pk))
        return api_ok_response(AssetSyncRecordSerializer(record).data)

    @action(methods=["POST"], detail=True, url_path="preview-sync")
    def preview_sync(self, request, pk=None):
        source = self.get_object()
        if source.source_type == AssetSource.SourceType.CLOUD:
            return api_error_response("云资产请使用云端预览入口")
        try:
            preview = preview_asset_sync(source, request.data.get("assets"))
        except ValueError as exc:
            return api_error_response(str(exc))
        return api_ok_response(preview)

    @action(methods=["POST"], detail=True, url_path="sync")
    def sync(self, request, pk=None):
        source = self.get_object()
        if source.source_type == AssetSource.SourceType.CLOUD:
            return api_error_response("云资产请使用云端同步入口")
        assets = request.data.get("assets")
        if not source.is_active:
            return api_error_response("资产来源已停用，不能同步")
        try:
            preview = preview_asset_sync(source, assets)
        except ValueError as exc:
            return api_error_response(str(exc))
        if preview["invalid"]:
            return api_error_response("资产清单包含无效或重复主机，请先修正")
        record = AssetSyncRecord.objects.create(
            source=source,
            total_count=len(assets),
            payload=assets,
        )
        if hasattr(sync_asset_source, "apply_async"):
            # worker 只监听 task/ops/ansible/devops.ansible，投递到 task 队列（default 无人消费）
            task = sync_asset_source.apply_async(args=[record.id], queue="task")
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
    filterset_fields = ("source", "status")
    search_fields = ("task_id", "error_message")


class CMDBSearchView(APIView):
    @extend_schema(
        responses=api_envelope_serializer("CMDBSearchResponse", CMDBSearchSerializer)
    )
    def get(self, request):
        keyword = str(request.query_params.get("q", "")).strip()
        if not keyword:
            return api_ok_response(
                {
                    "hosts": [],
                    "hostGroups": [],
                    "assetSources": [],
                }
            )
        try:
            limit = min(max(int(request.query_params.get("limit", 20)), 1), 100)
        except (TypeError, ValueError):
            limit = 20
        hosts = AssetHost.objects.filter(
            models.Q(hostname__icontains=keyword)
            | models.Q(internal_ip__icontains=keyword)
            | models.Q(external_ip__icontains=keyword)
            | models.Q(app_code__icontains=keyword)
        ).values(
            "id", "hostname", "internal_ip", "external_ip", "asset_type", "status"
        )[
            :limit
        ]
        groups = HostGroup.objects.filter(models.Q(name__icontains=keyword)).values(
            "id", "name", "group_type"
        )[:limit]
        sources = AssetSource.objects.filter(
            models.Q(code__icontains=keyword) | models.Q(name__icontains=keyword)
        ).values("id", "code", "name", "source_type")[:limit]
        return api_ok_response(
            {
                "hosts": list(hosts),
                "hostGroups": list(groups),
                "assetSources": list(sources),
            }
        )

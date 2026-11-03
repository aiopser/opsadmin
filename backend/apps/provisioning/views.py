from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from drf_spectacular.utils import extend_schema

from common.auth.rbac import ApiRBACPermission, verify_permission
from common.api.responses import api_ok_response
from common.api.schema import api_envelope_serializer
from .schema_serializers import ProvisioningOperationsHealthSerializer
from .contracts import ProvisioningError
from .models import (
    ResourceTemplate,
    ResourceTemplateVersion,
    ProvisioningCredential,
    ProvisioningRequest,
)
from .serializers import (
    TemplateSerializer,
    VersionSerializer,
    CredentialSerializer,
    RequestSerializer,
    PlanSerializer,
    EventSerializer,
)
from . import services
from .models import ProvisioningStateVersion
from .manual_resolution import ProvisioningReviewPermission
from rest_framework.views import APIView


class BaseViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, ApiRBACPermission]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = (
            self.paginate_queryset(queryset)
            if request.query_params.get("pageNum")
            else None
        )
        if page is not None:
            return self.get_paginated_response(
                self.get_serializer(page, many=True).data
            )
        return api_ok_response(self.get_serializer(queryset, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        return api_ok_response(self.get_serializer(self.get_object()).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return api_ok_response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            self.get_object(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_ok_response(serializer.data)


class TemplateViewSet(BaseViewSet):
    queryset = ResourceTemplate.objects.order_by("-id")
    serializer_class = TemplateSerializer


class VersionViewSet(BaseViewSet):
    queryset = ResourceTemplateVersion.objects.select_related("template").order_by(
        "-number"
    )
    serializer_class = VersionSerializer

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        with transaction.atomic():
            version = (
                self.get_queryset().select_for_update().get(pk=self.get_object().pk)
            )
            if version.status != "draft":
                raise serializers.ValidationError("版本已发布")
            if not version.constraints.get("bundle_digest"):
                raise serializers.ValidationError("发布前请填写审核后的模板包摘要")
            version.status = "published"
            version.published_at = timezone.now()
            version.save()
        return api_ok_response(self.get_serializer(version).data)


class CredentialViewSet(BaseViewSet):
    queryset = ProvisioningCredential.objects.select_related("source").order_by("-id")
    serializer_class = CredentialSerializer


class RequestViewSet(BaseViewSet):
    serializer_class = RequestSerializer
    queryset = ProvisioningRequest.objects.none()
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        query = (
            ProvisioningRequest.objects.select_related(
                "credential__source", "version__template"
            )
            .prefetch_related("plans")
            .order_by("-id")
        )
        user = self.request.user
        manage = verify_permission(user, "/api/v1/provisioning/review", "GET")[0]
        if not manage:
            query = query.filter(created_by=user)
        keyword = self.request.query_params.get("search", "").strip()
        return query.filter(name__icontains=keyword) if keyword else query

    def perform_create(self, serializer):
        record = serializer.save(created_by=self.request.user)
        services.event(record, self.request.user, "created", "已提交主机资源申请")

    @action(
        detail=True,
        methods=["post"],
        url_path="resolution-preview",
        permission_classes=[IsAuthenticated, ProvisioningReviewPermission],
    )
    def resolution_preview(self, request, pk=None):
        from .manual_resolution import preview_resolution

        record = self.get_object()
        version_id = request.data.get("stateVersionId")
        if version_id is not None and type(version_id) is not int:
            raise serializers.ValidationError("请选择有效 state 版本")
        try:
            preview = preview_resolution(record.pk, request.user, version_id)
        except ProvisioningError as exc:
            raise serializers.ValidationError(str(exc)) from None
        except (OSError, KeyError, ValueError, TypeError):
            raise serializers.ValidationError("无法校验执行归档或云端证据，请修复证据后重试") from None
        return api_ok_response(
            {
                "previewId": str(preview.pk),
                "digest": preview.digest,
                "expiresAt": preview.expires_at,
                "stateVersionId": preview.state_version_id,
                "stateDigest": preview.evidence["stateDigest"],
                "serial": preview.evidence["serial"],
                "instanceIds": preview.evidence["instanceIds"],
                "observedAssets": preview.evidence["observedAssets"],
                "notice": "核实成功后结案并纳管现有资源；不会重新 apply，缺失或数量不全的资源仍须调查",
            }
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="resolution-confirm",
        permission_classes=[IsAuthenticated, ProvisioningReviewPermission],
    )
    def resolution_confirm(self, request, pk=None):
        from .manual_resolution import confirm_resolution
        from .models import ProvisioningResolutionPreview

        record = self.get_object()
        try:
            preview = ProvisioningResolutionPreview.objects.get(
                pk=request.data.get("previewId"), request=record
            )
            resolved = confirm_resolution(
                preview.pk,
                request.user,
                request.data.get("digest"),
                request.data.get("evidenceReference"),
                request.data.get("comment"),
            )
        except ProvisioningError as exc:
            raise serializers.ValidationError(str(exc)) from None
        except (
            ProvisioningResolutionPreview.DoesNotExist,
            DjangoValidationError,
            OSError,
            KeyError,
            ValueError,
            TypeError,
        ):
            raise serializers.ValidationError("核实预览或证据无效，请重新预览") from None
        return api_ok_response(
            {
                "execution_status": "success",
                "inventory_status": "success",
                "stateVersionId": resolved.state_version_id,
            }
        )

    @action(detail=True, methods=["get"], url_path="state-versions")
    def state_versions(self, request, pk=None):
        record = self.get_object()
        rows = record.state_versions.order_by("-version")
        return api_ok_response(
            [
                {
                    "id": row.pk,
                    "version": row.version,
                    "serial": row.serial,
                    "status": row.protection_status,
                    "createdAt": row.created_at,
                    "verifiedAt": row.verified_at,
                    "message": row.message,
                }
                for row in rows[:100]
            ]
        )

    @action(detail=True, methods=["post"], url_path="restore-preview")
    def restore_preview(self, request, pk=None):
        from .state_restore import preview_restore

        record = self.get_object()
        version_id = request.data.get("stateVersionId")
        if type(version_id) is not int:
            raise serializers.ValidationError("请选择 state 版本")
        try:
            preview = preview_restore(record.pk, request.user, version_id)
            from .state_protection import read_state_files
            from .reconciliation import state_instance_ids

            instance_ids = state_instance_ids(
                read_state_files(preview.state_version, backup=True),
                record.version.template.provider,
            )
        except ProvisioningError as exc:
            raise serializers.ValidationError(str(exc)) from None
        except (ProvisioningStateVersion.DoesNotExist, OSError):
            raise serializers.ValidationError("备份无法恢复，请检查版本、权限、密钥及当前执行状态") from None
        return api_ok_response(
            {
                "previewId": str(preview.pk),
                "digest": preview.digest,
                "expiresAt": preview.expires_at,
                "stateVersionId": preview.state_version_id,
                "serial": preview.state_version.serial,
                "version": preview.state_version.version,
                "createdAt": preview.state_version.created_at,
                "status": preview.state_version.protection_status,
                "instanceIds": instance_ids[:20],
                "notice": "仅恢复控制状态，不回滚云资源",
            }
        )

    @action(detail=True, methods=["post"], url_path="restore-confirm")
    def restore_confirm(self, request, pk=None):
        from .state_restore import confirm_restore
        from .models import ProvisioningRestorePreview

        record = self.get_object()
        preview_id, digest = request.data.get("previewId"), request.data.get("digest")
        try:
            preview = ProvisioningRestorePreview.objects.get(
                pk=preview_id, request=record
            )
            version = confirm_restore(preview.pk, request.user, digest)
        except ProvisioningError as exc:
            raise serializers.ValidationError(str(exc)) from None
        except (
            ProvisioningRestorePreview.DoesNotExist,
            ValueError,
            TypeError,
            DjangoValidationError,
            OSError,
        ):
            raise serializers.ValidationError("恢复预览无效或已过期，请重新校验") from None
        return api_ok_response(
            {"stateVersionId": version.pk, "status": version.protection_status}
        )

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        rows = self.get_object().events.order_by("-id")
        page = (
            self.paginate_queryset(rows)
            if request.query_params.get("pageNum")
            else None
        )
        if page is not None:
            return self.get_paginated_response(EventSerializer(page, many=True).data)
        return api_ok_response(EventSerializer(rows[:100], many=True).data)

    def transition(self, request, operation):
        record = self.get_object()
        plan_id = request.data.get("plan_id")
        digest = request.data.get("digest")
        if type(plan_id) is not int or not isinstance(digest, str) or len(digest) != 64:
            raise serializers.ValidationError("请提交有效的计划与校验摘要")
        try:
            if operation == "execute":
                result = services.execute_plan(
                    record.pk,
                    request.user,
                    plan_id,
                    digest,
                    request.data.get("idempotency_key"),
                )
                return api_ok_response(
                    {"attempt_id": result.pk, "status": result.status}
                )
            if operation in {"approve", "reject"}:
                comment = request.data.get("comment", "")
                if not isinstance(comment, str):
                    raise serializers.ValidationError("审批说明必须为文字")
                services.approve_plan(
                    record.pk,
                    request.user,
                    plan_id,
                    digest,
                    "approved" if operation == "approve" else "rejected",
                    comment,
                )
            else:
                services.confirm_plan(record.pk, request.user, plan_id, digest)
        except (ProvisioningError, services.ProvisioningPlan.DoesNotExist) as exc:
            raise serializers.ValidationError(str(exc)) from exc
        record.refresh_from_db()
        return api_ok_response(self.get_serializer(record).data)

    @action(detail=True, methods=["post"])
    def plan(self, request, pk=None):
        record = self.get_object()
        try:
            plan = services.queue_plan(record.pk, request.user)
        except ProvisioningError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return api_ok_response(PlanSerializer(plan).data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return self.transition(request, "confirm")

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self.transition(request, "approve")

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self.transition(request, "reject")

    @action(detail=True, methods=["post"])
    def execute(self, request, pk=None):
        return self.transition(request, "execute")

    @action(detail=True, methods=["post"])
    def reconcile(self, request, pk=None):
        record = self.get_object()
        attempt = record.plans.filter(attempt__isnull=False).order_by("-id").first()
        if not attempt:
            raise serializers.ValidationError("尚无执行记录")
        if attempt.attempt.status not in {
            "applied",
            "needs_reconciliation",
            "reconciled",
        }:
            raise serializers.ValidationError("执行尚未结束或尚未创建资源")
        from .reconciliation import queue_reconciliation

        try:
            queued = queue_reconciliation(
                attempt.attempt.pk, request.user.pk, force=True
            )
        except ProvisioningError as exc:
            raise serializers.ValidationError(str(exc)) from None
        record.refresh_from_db()
        return api_ok_response(
            {"status": "queued" if queued else record.inventory_status}
        )


class OperationsHealthView(APIView):
    permission_classes = [IsAuthenticated, ApiRBACPermission]

    @extend_schema(
        responses=api_envelope_serializer(
            "ProvisioningOperationsHealthResponse",
            ProvisioningOperationsHealthSerializer,
        )
    )
    def get(self, request):
        from .worker_health import health_snapshot
        from .state_protection import check_protection_storage

        result = health_snapshot()
        try:
            check_protection_storage()
            result["storage"] = {"ready": True, "message": "主存储及备份可写；独立故障域需部署验收"}
        except Exception:
            result["storage"] = {"ready": False, "message": "存储、备份或密钥配置未就绪"}
        result["retention"] = {
            "planDays": 30,
            "diagnosticDays": 30,
            "retiredStateDays": 180,
            "auditDays": 365,
            "activeStateProtected": True,
        }
        return api_ok_response(result)

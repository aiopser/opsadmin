from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework import serializers
from drf_spectacular.utils import extend_schema
from common.api.schema import api_envelope_serializer
from common.api.responses import api_ok_response
from common.api.viewsets import StandardModelViewSet
from apps.consul.models import ConsulConnection
from apps.consul.serializers import ConsulConnectionSerializer
from apps.audit_center.services import create_domain_audit_event
from .models import MonitoringTarget, SyncRecord
from .serializers import MonitoringTargetSerializer, SyncRecordSerializer
from .registration import (
    ACTIVE,
    build_registration,
    enqueue_sync,
    prometheus_config,
    alert_rules,
)
from .tasks import sync_consul_target
from .batch_import import (
    HostImportSerializer,
    HostImportCommitSerializer,
    preview_host_import,
    commit_host_import,
)


class MonitoringTargetViewSet(StandardModelViewSet):
    queryset = MonitoringTarget.objects.select_related("connection", "host")
    serializer_class = MonitoringTargetSerializer
    search_fields = ["name", "address", "service_id"]
    filterset_fields = ["connection", "kind", "registered"]
    ordering_fields = ["id", "name", "updated_at"]

    @extend_schema(
        request=HostImportSerializer,
        responses=api_envelope_serializer(
            "MonitoringHostImportPreview", serializers.DictField()
        ),
    )
    @action(detail=False, methods=["post"], url_path="host-import-preview")
    def host_import_preview(self, request):
        values = HostImportSerializer(data=request.data)
        values.is_valid(raise_exception=True)
        return api_ok_response(preview_host_import(values.validated_data, request.user))

    @extend_schema(
        request=HostImportCommitSerializer,
        responses=api_envelope_serializer(
            "MonitoringHostImportResult", serializers.DictField()
        ),
    )
    @action(detail=False, methods=["post"], url_path="host-import")
    def host_import(self, request):
        values = HostImportCommitSerializer(data=request.data)
        values.is_valid(raise_exception=True)
        return api_ok_response(commit_host_import(values.validated_data, request.user))

    def _audit(self, row, action):
        create_domain_audit_event(
            self.request.user,
            "monitoring.target." + action,
            "monitoring_target",
            row.pk,
            after={"name": row.name, "connection_id": row.connection_id},
            request=self.request,
            domain="monitoring",
        )

    def perform_create(self, serializer, request=None):
        self._audit(serializer.save(), "create")

    def perform_update(self, serializer, request=None):
        self._audit(serializer.save(), "update")

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        target = self.get_object()
        ConsulConnection.objects.select_for_update().get(pk=target.connection_id)
        row = MonitoringTarget.objects.select_for_update().get(pk=target.pk)
        if (
            row.registered
            or row.registration_uncertain
            or row.sync_records.filter(status__in=ACTIVE).exists()
        ):
            raise ValidationError("请先完成注销，再删除监控目标")
        self._audit(row, "delete")
        row.delete()
        return api_ok_response()

    @extend_schema(
        responses=api_envelope_serializer(
            "MonitoringRegistrationPreview", serializers.DictField()
        )
    )
    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        return api_ok_response(build_registration(self.get_object()))

    def _queue(self, operation):
        target = self.get_object()
        record = enqueue_sync(target.pk, operation, self.request.user)
        try:
            sync_consul_target.delay(record.pk)
        except Exception:
            SyncRecord.objects.filter(pk=record.pk, status="queued").update(
                status="failed",
                error="任务投递失败，请检查 Celery 服务后重试",
                finished_at=timezone.now(),
            )
            raise ValidationError("任务投递失败，请检查 Celery 服务后重试") from None
        record.refresh_from_db()
        return api_ok_response(SyncRecordSerializer(record).data)

    @extend_schema(
        request=None,
        responses=api_envelope_serializer(
            "MonitoringSyncSubmitted", SyncRecordSerializer
        ),
    )
    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        return self._queue("register")

    @extend_schema(
        request=None,
        responses=api_envelope_serializer(
            "MonitoringDeregisterSubmitted", SyncRecordSerializer
        ),
    )
    @action(detail=True, methods=["post"])
    def deregister(self, request, pk=None):
        return self._queue("deregister")


class SyncRecordViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    queryset = SyncRecord.objects.select_related("target").all()
    serializer_class = SyncRecordSerializer
    filterset_fields = ["target", "status"]
    ordering_fields = ["id", "created_at"]


class MonitoringConnectionViewSet(viewsets.GenericViewSet):
    queryset = ConsulConnection.objects.all()
    serializer_class = ConsulConnectionSerializer

    @extend_schema(
        responses=api_envelope_serializer(
            "MonitoringPrometheusConfig",
            serializers.DictField(child=serializers.CharField()),
        )
    )
    @action(detail=True, methods=["get"], url_path="prometheus-config")
    def prometheus_config(self, request, pk=None):
        return api_ok_response(
            {
                "config": prometheus_config(self.get_object()),
                "note": "配置为合并片段；Token 需另行挂载 authorization.credentials_file，Exporter 与 Blackbox 需提前部署。",
            }
        )

    @extend_schema(
        responses=api_envelope_serializer(
            "MonitoringAlertRules", serializers.DictField(child=serializers.CharField())
        )
    )
    @action(detail=True, methods=["get"], url_path="alert-rules")
    def alert_rules(self, request, pk=None):
        return api_ok_response(
            {
                "config": alert_rules(self.get_object()),
                "note": "基础规则仅供预览；保存为规则文件并加入 Prometheus rule_files，告警路由由 Alertmanager 配置。",
            }
        )

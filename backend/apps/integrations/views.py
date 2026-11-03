from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from common.api.viewsets import StandardModelViewSet
from common.api.responses import api_ok_response
from .models import JumpServerConnection, JumpServerSync
from .serializers import JumpServerConnectionSerializer, JumpServerSyncSerializer
from .services import preview, confirm
from .tasks import sync_jumpserver
from .client import JumpServerClient, JumpServerError
from django.db import transaction
from apps.audit_center.services import create_domain_audit_event


class JumpServerConnectionViewSet(StandardModelViewSet):
    queryset = JumpServerConnection.objects.all().order_by("id")
    serializer_class = JumpServerConnectionSerializer

    def audit(self, row, action):
        create_domain_audit_event(
            self.request.user,
            "integrations.jumpserver." + action,
            "jumpserver_connection",
            row.pk,
            after={"name": row.name},
            request=self.request,
            domain="monitoring",
        )

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search", "")
        return qs.filter(name__icontains=search) if search else qs

    def perform_create(self, serializer, request=None):
        self.audit(serializer.save(), "create")

    def perform_update(self, serializer, request=None):
        self.audit(serializer.save(), "update")

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = JumpServerConnection.objects.select_for_update().get(
            pk=self.get_object().pk
        )
        if instance.mappings.exists() or instance.runs.exists():
            raise ValidationError("连接有纳管映射或记录，请停用以保留审计身份")
        self.audit(instance, "delete")
        instance.delete()
        return api_ok_response()

    def perform_destroy(self, instance):
        if instance.runs.filter(status__in=["queued", "running"]).exists():
            raise ValidationError("连接有执行中的任务")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="test")
    def test_connection(self, request, pk=None):
        connection = self.get_object()
        if not connection.is_active:
            raise ValidationError("连接已停用")
        try:
            JumpServerClient(connection).test()
        except JumpServerError as exc:
            raise ValidationError(str(exc)) from None
        self.audit(connection, "test")
        return api_ok_response({"success": True})

    @action(detail=True, methods=["post"])
    def preview(self, request, pk=None):
        field = serializers.ListField(
            child=serializers.IntegerField(min_value=1), min_length=1, max_length=500
        )
        run = preview(
            self.get_object(),
            request.user,
            field.run_validation(request.data.get("host_ids")),
        )
        self.audit(run.connection, "preview")
        return api_ok_response(JumpServerSyncSerializer(run).data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        run = JumpServerSync.objects.filter(
            pk=request.data.get("preview_id"), connection=self.get_object()
        ).first()
        if not run:
            raise ValidationError("预览不存在")
        run = confirm(run, request.user)
        self.audit(run.connection, "confirm")
        try:
            task = sync_jumpserver.delay(run.pk)
            run.task_id = task.id
            run.save(update_fields=["task_id"])
        except Exception:
            run.status = "failed"
            run.error = "任务入队失败，请重新预览重试"
            run.save()
            raise ValidationError("任务入队失败，请重新预览重试") from None
        return api_ok_response(JumpServerSyncSerializer(run).data)

    @action(detail=True, methods=["get"])
    def records(self, request, pk=None):
        return api_ok_response(
            JumpServerSyncSerializer(
                self.get_object().runs.order_by("-id")[:100], many=True
            ).data
        )

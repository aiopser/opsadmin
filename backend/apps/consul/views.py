from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework import serializers
from drf_spectacular.utils import extend_schema
from common.api.schema import api_envelope_serializer
from common.api.responses import api_ok_response
from common.api.viewsets import StandardModelViewSet
from apps.audit_center.services import create_domain_audit_event
from .client import ConsulClient, ConsulError
from .models import ConsulConnection, ConsulTemplateFile
from .serializers import ConsulConnectionSerializer, ConsulTemplateFileSerializer
from .templates import submit_template_deploy
from .remote_views import RemoteFileActions, RemoteDeployInput
from .catalog import (
    CatalogQuerySerializer,
    CatalogInstanceQuerySerializer,
    catalog_item,
)


class KvQuerySerializer(serializers.Serializer):
    prefix = serializers.CharField(
        max_length=512, required=False, allow_blank=True, default=""
    )


class KvValueQuerySerializer(serializers.Serializer):
    key = serializers.CharField(max_length=512)


class KvValueResponseSerializer(serializers.Serializer):
    key = serializers.CharField()
    value = serializers.CharField(allow_blank=True)
    create_index = serializers.IntegerField()
    modify_index = serializers.IntegerField()
    lock_index = serializers.IntegerField()
    flags = serializers.IntegerField()


class KvWriteSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=512)
    value = serializers.CharField(max_length=1_048_576, allow_blank=True)


class ConsulConnectionViewSet(StandardModelViewSet):
    queryset = ConsulConnection.objects.all()
    serializer_class = ConsulConnectionSerializer
    search_fields = ["name", "endpoint"]
    ordering_fields = ["id", "name", "updated_at"]
    filterset_fields = ["is_active"]

    def perform_create(self, serializer, request=None):
        row = serializer.save()
        self._audit(row, "create")

    def perform_update(self, serializer, request=None):
        row = serializer.save()
        self._audit(row, "update")

    def _audit(self, row, action):
        create_domain_audit_event(
            self.request.user,
            "consul.connection." + action,
            "consul_connection",
            row.pk,
            after={"name": row.name, "endpoint": row.endpoint},
            request=self.request,
            domain="monitoring",
        )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        row = ConsulConnection.objects.select_for_update().get(pk=self.get_object().pk)
        if row.monitoring_targets.exists() or row.enrollment_policies.exists():
            raise ValidationError("连接仍有关联监控目标，请先处理目标")
        self._audit(row, "delete")
        row.delete()
        return api_ok_response()

    @extend_schema(
        request=None,
        responses=api_envelope_serializer(
            "ConsulConnectionTest", serializers.DictField(child=serializers.CharField())
        ),
    )
    @action(detail=True, methods=["post"], url_path="test")
    def test(self, request, pk=None):
        row = self.get_object()
        try:
            result = ConsulClient(row).test_connection()
        except ConsulError as exc:
            create_domain_audit_event(
                request.user,
                "consul.connection.test",
                "consul_connection",
                row.pk,
                result="failure",
                domain="monitoring",
                request=request,
            )
            raise ValidationError(str(exc)) from None
        self._audit(row, "test")
        return api_ok_response(result)

    @extend_schema(
        responses=api_envelope_serializer(
            "ConsulAgentServices", serializers.ListField(child=serializers.DictField())
        )
    )
    @action(detail=True, methods=["get"])
    def services(self, request, pk=None):
        row = self.get_object()
        try:
            client = ConsulClient(row)
            services = client.agent_services()
            checks = client.agent_checks()
        except ConsulError as exc:
            raise ValidationError(str(exc)) from None
        owned = {
            target.service_id: str(target.pk) for target in row.monitoring_targets.all()
        }
        items = []
        for sid, service in services.items():
            statuses = [
                check.get("Status", "unknown")
                for check in checks.values()
                if isinstance(check, dict) and check.get("ServiceID", "") in {sid, ""}
            ]
            meta = service.get("Meta") or {}
            items.append(
                {
                    "id": sid,
                    "name": service.get("Service", ""),
                    "address": service.get("Address", ""),
                    "port": service.get("Port", 0),
                    "tags": service.get("Tags") or [],
                    "meta": meta,
                    "health": "critical"
                    if "critical" in statuses
                    else "warning"
                    if "warning" in statuses
                    else "passing"
                    if statuses and all(status == "passing" for status in statuses)
                    else "unknown",
                    "managed": sid in owned
                    and meta.get("managed_by") == "devops-platform"
                    and meta.get("target_id") == owned[sid],
                }
            )
        return api_ok_response(items)

    @extend_schema(
        responses=api_envelope_serializer(
            "ConsulDatacenters", serializers.ListField(child=serializers.CharField())
        )
    )
    @action(detail=True, methods=["get"])
    def datacenters(self, request, pk=None):
        try:
            return api_ok_response(ConsulClient(self.get_object()).datacenters())
        except ConsulError as exc:
            raise ValidationError(str(exc)) from None

    @extend_schema(
        parameters=[KvQuerySerializer],
        responses=api_envelope_serializer("ConsulKvKeys", serializers.DictField()),
    )
    @action(detail=True, methods=["get"], url_path="kv")
    def kv(self, request, pk=None):
        query = KvQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        try:
            keys = ConsulClient(self.get_object()).kv_keys(
                query.validated_data["prefix"]
            )
        except ConsulError as exc:
            raise ValidationError(str(exc)) from None
        return api_ok_response({"keys": keys})

    @extend_schema(
        parameters=[KvValueQuerySerializer],
        responses=api_envelope_serializer("ConsulKvValue", KvValueResponseSerializer()),
    )
    @action(detail=True, methods=["get"], url_path="kv-value")
    def kv_value(self, request, pk=None):
        query = KvValueQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        try:
            result = ConsulClient(self.get_object()).kv_value(
                query.validated_data["key"]
            )
        except ConsulError as exc:
            raise ValidationError(str(exc)) from None
        return api_ok_response(result)

    @extend_schema(
        request=KvWriteSerializer,
        responses=api_envelope_serializer("ConsulKvWriteOk", serializers.DictField()),
    )
    @action(detail=True, methods=["post"], url_path="kv-write")
    def kv_write(self, request, pk=None):
        query = KvWriteSerializer(data=request.data)
        query.is_valid(raise_exception=True)
        try:
            ConsulClient(self.get_object()).kv_write(**query.validated_data)
        except ConsulError as exc:
            raise ValidationError(str(exc)) from None
        return api_ok_response({"ok": True})

    @extend_schema(
        request=KvValueQuerySerializer,
        responses=api_envelope_serializer("ConsulKvDeleteOk", serializers.DictField()),
    )
    @action(detail=True, methods=["delete"], url_path="kv-delete")
    def kv_delete(self, request, pk=None):
        query = KvValueQuerySerializer(data=request.data)
        query.is_valid(raise_exception=True)
        try:
            ConsulClient(self.get_object()).kv_delete(query.validated_data["key"])
        except ConsulError as exc:
            raise ValidationError(str(exc)) from None
        return api_ok_response({"ok": True})

    @extend_schema(
        parameters=[CatalogQuerySerializer],
        responses=api_envelope_serializer(
            "ConsulCatalogServices",
            serializers.ListField(child=serializers.DictField()),
        ),
    )
    @action(detail=True, methods=["get"], url_path="catalog-services")
    def catalog_services(self, request, pk=None):
        query = CatalogQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        try:
            return api_ok_response(
                ConsulClient(self.get_object()).catalog_services(
                    query.validated_data["datacenter"]
                )
            )
        except ConsulError as exc:
            raise ValidationError(str(exc)) from None

    @extend_schema(
        parameters=[CatalogInstanceQuerySerializer],
        responses=api_envelope_serializer(
            "ConsulCatalogInstances", serializers.DictField()
        ),
    )
    @action(detail=True, methods=["get"], url_path="catalog-instances")
    def catalog_instances(self, request, pk=None):
        query = CatalogInstanceQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        values = query.validated_data
        try:
            items = ConsulClient(self.get_object()).catalog_instances(
                values["service"], values["datacenter"]
            )
        except ConsulError as exc:
            raise ValidationError(str(exc)) from None
        page, size = values["pageNum"], values["pageSize"]
        ordered = sorted(
            items,
            key=lambda item: (
                str(item["Node"].get("Node", "")),
                str(item["Service"].get("ID", "")),
            ),
        )
        return api_ok_response(
            {
                "list": [
                    catalog_item(item)
                    for item in ordered[(page - 1) * size : page * size]
                ],
                "total": len(ordered),
                "page": page,
                "size": size,
            }
        )


class ConsulTemplateFileViewSet(RemoteFileActions, StandardModelViewSet):
    queryset = ConsulTemplateFile.objects.select_related("host", "last_deploy_run")
    serializer_class = ConsulTemplateFileSerializer
    search_fields = ["name", "path"]
    ordering_fields = ["id", "name", "updated_at"]

    def perform_create(self, serializer, request=None):
        row = serializer.save()
        self._audit(row, "create")

    def perform_update(self, serializer, request=None):
        row = serializer.save()
        self._audit(row, "update")

    def _audit(self, row, action):
        create_domain_audit_event(
            self.request.user,
            "consul.template." + action,
            "consul_template_file",
            row.pk,
            after={"name": row.name, "host": row.host.hostname, "path": row.path},
            request=self.request,
            domain="monitoring",
        )

    def destroy(self, request, *args, **kwargs):
        row = self.get_object()
        self._audit(row, "delete")
        row.delete()
        return api_ok_response()

    @extend_schema(
        request=RemoteDeployInput,
        responses=api_envelope_serializer(
            "ConsulTemplateDeploy", serializers.DictField()
        ),
    )
    @action(detail=True, methods=["post"], url_path="deploy")
    def deploy(self, request, pk=None):
        values = RemoteDeployInput(data=request.data)
        values.is_valid(raise_exception=True)
        row = self.get_object()
        run = submit_template_deploy(
            row, request.user, values.validated_data["read_id"]
        )
        row.refresh_from_db()
        row.last_deploy_status = ConsulTemplateFile.DeployStatus.PENDING
        row.last_deploy_at = timezone.now()
        row.last_deploy_message = f"已提交下发，运行 #{run.id}"
        row.last_deploy_run = run
        row.save(
            update_fields=[
                "last_deploy_status",
                "last_deploy_at",
                "last_deploy_message",
                "last_deploy_run",
                "updated_at",
            ]
        )
        create_domain_audit_event(
            request.user,
            "consul.template.deploy",
            "consul_template_file",
            row.pk,
            after={"run_id": run.id, "path": row.path},
            request=request,
            domain="monitoring",
        )
        return api_ok_response({"run_id": run.id})

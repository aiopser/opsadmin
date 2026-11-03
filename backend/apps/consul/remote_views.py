from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema

from apps.audit_center.services import create_domain_audit_event
from common.api.responses import api_ok_response
from common.api.schema import api_envelope_serializer
from .models import RemoteFileRead
from .remote_files import schedule_read, read_result, compare_read, MAX_BYTES


class RemoteReadInput(serializers.Serializer):
    host = serializers.IntegerField(min_value=1)
    path = serializers.CharField(max_length=512)
    template_id = serializers.IntegerField(min_value=1, required=False)
    revision = serializers.CharField(max_length=64, required=False, default="")


class RemoteReadResult(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    exists = serializers.BooleanField(allow_null=True)
    content = serializers.CharField(
        allow_null=True, allow_blank=True, trim_whitespace=False
    )
    checksum = serializers.CharField(allow_blank=True)
    size = serializers.IntegerField()
    error = serializers.CharField(allow_blank=True)


class RemoteCompareInput(serializers.Serializer):
    read_id = serializers.UUIDField()
    content = serializers.CharField(
        allow_blank=True, trim_whitespace=False, max_length=MAX_BYTES
    )


class RemoteComparison(serializers.Serializer):
    changed = serializers.BooleanField()
    diff = serializers.CharField(allow_blank=True, trim_whitespace=False)


class RemoteDeployInput(serializers.Serializer):
    read_id = serializers.UUIDField()


def private_response(data):
    response = api_ok_response(data)
    response["Cache-Control"] = "no-store"
    return response


class RemoteFileActions:
    @extend_schema(
        request=RemoteReadInput,
        responses=api_envelope_serializer("ConsulRemoteRead", RemoteReadResult),
    )
    @action(detail=False, methods=["post"], url_path="read-remote")
    def read_remote(self, request):
        serializer = RemoteReadInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        host_id = values.pop("host")
        row = schedule_read(request.user, host_id, **values)
        create_domain_audit_event(
            request.user,
            "consul.template.read",
            "consul_template_file",
            row.template_id or "",
            after={"host_id": row.host_id, "path": row.path, "read_id": str(row.pk)},
            request=request,
            domain="monitoring",
        )
        return private_response(read_result(row, request.user))

    @extend_schema(
        responses=api_envelope_serializer("ConsulRemoteReadStatus", RemoteReadResult)
    )
    @action(
        detail=False,
        methods=["get"],
        url_path=r"remote-reads/(?P<read_id>[0-9a-f-]{36})",
    )
    def remote_read_status(self, request, read_id=None):
        row = get_object_or_404(RemoteFileRead, pk=read_id)
        return private_response(read_result(row, request.user))

    @extend_schema(
        request=RemoteCompareInput,
        responses=api_envelope_serializer("ConsulRemoteComparison", RemoteComparison),
    )
    @action(detail=False, methods=["post"], url_path="compare-remote")
    def compare_remote(self, request):
        serializer = RemoteCompareInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        row = get_object_or_404(RemoteFileRead, pk=values["read_id"])
        return private_response(compare_read(row, request.user, values["content"]))

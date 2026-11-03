from django.db import transaction
from django.db.models import Q
from rest_framework import serializers
from apps.cmdb.crypto import encrypt_secret
from apps.cmdb.models import AssetHost
from .client import validate_endpoint
from .models import ConsulConnection, ConsulTemplateFile
from .templates import validate_reload_command, validate_template_path


class ConsulConnectionSerializer(serializers.ModelSerializer):
    token = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
        max_length=4096,
    )
    has_token = serializers.SerializerMethodField()

    class Meta:
        model = ConsulConnection
        exclude = ["token_encrypted"]
        read_only_fields = ["created_at", "updated_at"]

    def get_has_token(self, obj) -> bool:
        return bool(obj.token_encrypted)

    def validate_endpoint(self, value):
        return validate_endpoint(value)

    def create(self, validated_data):
        token = validated_data.pop("token", "")
        return ConsulConnection.objects.create(
            **validated_data, token_encrypted=encrypt_secret(token)
        )

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = ConsulConnection.objects.select_for_update().get(pk=instance.pk)
        if instance.enrollment_policies.filter(
            runs__status__in=["queued", "running"]
        ).exists():
            raise serializers.ValidationError("连接有正在执行的纳管策略，请稍后修改")
        if instance.monitoring_targets.filter(
            sync_records__status__in=["queued", "running"]
        ).exists():
            raise serializers.ValidationError("连接有正在同步的目标，请稍后修改")
        if (
            "endpoint" in validated_data
            and validated_data["endpoint"] != instance.endpoint
            and instance.monitoring_targets.filter(
                Q(registered=True) | Q(registration_uncertain=True)
            ).exists()
        ):
            raise serializers.ValidationError({"endpoint": "请先注销已注册目标，再更换 Consul 地址"})
        token = validated_data.pop("token", "")
        if token:
            validated_data["token_encrypted"] = encrypt_secret(token)
        return super().update(instance, validated_data)


class ConsulTemplateFileSerializer(serializers.ModelSerializer):
    content = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False
    )
    host_name = serializers.CharField(source="host.hostname", read_only=True)
    host_ip = serializers.CharField(source="host.internal_ip", read_only=True)
    revision = serializers.SerializerMethodField()
    last_deploy_status = serializers.SerializerMethodField()
    last_deploy_message = serializers.SerializerMethodField()

    class Meta:
        model = ConsulTemplateFile
        fields = [
            "id",
            "name",
            "host",
            "host_name",
            "host_ip",
            "path",
            "content",
            "reload_command",
            "last_deploy_status",
            "last_deploy_at",
            "last_deploy_message",
            "created_at",
            "updated_at",
            "revision",
            "last_deploy_run",
        ]
        read_only_fields = [
            "last_deploy_status",
            "last_deploy_at",
            "last_deploy_message",
            "created_at",
            "updated_at",
            "last_deploy_run",
        ]

    def get_revision(self, obj) -> str:
        from .remote_files import template_revision

        return template_revision(obj)

    def get_last_deploy_status(self, obj) -> str:
        if not obj.last_deploy_run_id:
            return obj.last_deploy_status
        return {
            "success": "success",
            "failed": "failure",
            "timeout": "failure",
            "canceled": "canceled",
            "cancel_requested": "running",
            "running": "running",
        }.get(obj.last_deploy_run.status, "queued")

    def get_last_deploy_message(self, obj) -> str:
        if obj.last_deploy_run_id:
            return f"运行 #{obj.last_deploy_run_id} · {self.get_last_deploy_status(obj)}"
        return obj.last_deploy_message

    def validate_name(self, value):
        return value.strip()

    def validate_host(self, value):
        if value.os_family != AssetHost.OSFamily.LINUX:
            raise serializers.ValidationError("模板下发仅支持 Linux 主机")
        return value

    def validate_path(self, value):
        return validate_template_path(value)

    def validate_reload_command(self, value):
        return validate_reload_command(value)

    def validate_content(self, value):
        if len(value.encode()) > 256 * 1024:
            raise serializers.ValidationError("内容超过256 KiB上限")
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        current = ConsulTemplateFile.objects.select_for_update().get(pk=instance.pk)
        if current.last_deploy_run_id and current.last_deploy_run.status in {
            "pending",
            "queued",
            "running",
            "waiting",
            "cancel_requested",
        }:
            raise serializers.ValidationError("下发进行中，请等待结束后修改")
        return super().update(current, validated_data)

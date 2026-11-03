from django.db import transaction
from rest_framework import serializers
from apps.cmdb.crypto import encrypt_secret
from apps.consul.client import validate_endpoint
from .models import JumpServerConnection, JumpServerSync


class JumpServerConnectionSerializer(serializers.ModelSerializer):
    secret = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=4096,
        trim_whitespace=False,
    )
    has_secret = serializers.SerializerMethodField()

    class Meta:
        model = JumpServerConnection
        exclude = ["secret_encrypted"]
        read_only_fields = [
            "created_at",
            "updated_at",
            "sync_actor",
            "last_sync_at",
            "selected_host_ids",
        ]

    def get_has_secret(self, obj) -> bool:
        return bool(obj.secret_encrypted)

    def validate_key_id(self, value):
        if any(char in value for char in ['"', "\\", "\r", "\n"]):
            raise serializers.ValidationError("Key ID 含非法字符")
        return value

    def validate_org_id(self, value):
        return self.validate_node_id(value) if value else ""

    def validate_endpoint(self, value):
        return validate_endpoint(value)

    def validate_node_id(self, value):
        import uuid

        try:
            return str(uuid.UUID(value))
        except ValueError:
            raise serializers.ValidationError("请输入 JumpServer 节点 UUID")

    def validate(self, attrs):
        if not self.instance and not attrs.get("secret"):
            raise serializers.ValidationError({"secret": "请输入 API Key Secret"})
        interval = attrs.get(
            "sync_interval_minutes", getattr(self.instance, "sync_interval_minutes", 0)
        )
        if not 0 <= interval <= 10080:
            raise serializers.ValidationError(
                {"sync_interval_minutes": "同步间隔范围为 0–10080 分钟"}
            )
        if interval and self.automatic_changed(attrs):
            from common.auth.rbac import verify_permission

            actor = getattr(self.context.get("request"), "user", None)
            if not self.instance or not self.instance.selected_host_ids:
                raise serializers.ValidationError("请先保存连接并确认一次主机同步，再启用定时同步")
            if (
                not actor
                or not actor.is_active
                or not verify_permission(
                    actor,
                    f"/api/v1/integrations/jumpserver/connections/{self.instance.pk}/confirm",
                    "POST",
                )[0]
            ):
                raise serializers.ValidationError("修改自动同步配置需要同步执行权限")
        return attrs

    def automatic_changed(self, attrs):
        return (
            self.instance is None
            or any(
                value != getattr(self.instance, key, None)
                for key, value in attrs.items()
                if key not in {"name", "secret"}
            )
            or bool(attrs.get("secret"))
        )

    def create(self, validated_data):
        secret = validated_data.pop("secret", "")
        return JumpServerConnection.objects.create(
            **validated_data, secret_encrypted=encrypt_secret(secret)
        )

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = JumpServerConnection.objects.select_for_update().get(pk=instance.pk)
        if instance.runs.filter(status__in=["queued", "running"]).exists():
            raise serializers.ValidationError("同步执行中，请稍后修改")
        if instance.mappings.exists() and any(
            validated_data.get(key, getattr(instance, key)) != getattr(instance, key)
            for key in ["endpoint", "org_id"]
        ):
            raise serializers.ValidationError("已纳管连接不能更换地址或组织，请新建连接")
        if self.automatic_changed(validated_data):
            validated_data["sync_actor"] = (
                self.context["request"].user
                if validated_data.get(
                    "sync_interval_minutes", instance.sync_interval_minutes
                )
                else None
            )
        secret = validated_data.pop("secret", "")
        if secret:
            validated_data["secret_encrypted"] = encrypt_secret(secret)
        return super().update(instance, validated_data)


class JumpServerSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = JumpServerSync
        fields = "__all__"

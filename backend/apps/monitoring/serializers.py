import re
from urllib.parse import urlsplit
from django.db import transaction
from rest_framework import serializers
from apps.consul.models import ConsulConnection
from apps.consul.client import validate_endpoint
from .models import MonitoringTarget, SyncRecord
from .registration import ACTIVE, revision


class MonitoringTargetSerializer(serializers.ModelSerializer):
    sync_interval_minutes = serializers.IntegerField(
        min_value=0, max_value=10080, required=False
    )
    connection_name = serializers.CharField(source="connection.name", read_only=True)
    sync_state = serializers.SerializerMethodField()

    class Meta:
        model = MonitoringTarget
        fields = "__all__"
        read_only_fields = [
            "enrollment_policy",
            "auto_sync_actor",
            "last_auto_sync_at",
            "next_auto_sync_at",
            "service_id",
            "registered",
            "registration_uncertain",
            "synced_at",
            "synced_revision",
            "created_at",
            "updated_at",
        ]

    def get_sync_state(self, obj) -> str:
        latest = obj.sync_records.order_by("-id").first()
        if latest and latest.status in ACTIVE:
            return latest.status
        if latest and latest.status == "failed":
            return "failed"
        if obj.registered:
            return "synced" if obj.synced_revision == revision(obj) else "pending"
        return "unregistered"

    def automatic_changed(self, attrs):
        fields = {
            "address",
            "port",
            "tags",
            "meta",
            "kind",
            "connection",
            "probe_target",
            "probe_module",
            "check_enabled",
            "sync_interval_minutes",
            "follow_host_address",
            "host",
            "address_source",
        }
        return self.instance is None or any(
            value != getattr(self.instance, field)
            for field, value in attrs.items()
            if field in fields
        )

    def validate_address(self, value):
        import ipaddress

        try:
            address = ipaddress.ip_address(value)
            if address.is_link_local or address.is_unspecified or address.is_multicast:
                raise serializers.ValidationError("不允许使用链路本地、未指定或组播地址")
        except ValueError:
            if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", value):
                raise serializers.ValidationError("请填写 Exporter IP 或主机名，不包含协议和路径")
        return value

    def validate_port(self, value):
        if not 1 <= value <= 65535:
            raise serializers.ValidationError("端口范围为 1–65535")
        return value

    def validate_tags(self, value):
        if (
            not isinstance(value, list)
            or len(value) > 64
            or any(
                not isinstance(item, str) or not item.strip() or len(item) > 128
                for item in value
            )
        ):
            raise serializers.ValidationError("标签必须是不超过 64 项的非空字符串列表")
        return list(dict.fromkeys(value))

    def validate_meta(self, value):
        if not isinstance(value, dict) or len(value) > 64:
            raise serializers.ValidationError("Meta 必须是不超过 64 项的对象")
        for key, item in value.items():
            if key in {
                "managed_by",
                "target_id",
                "kind",
                "probe_target",
                "probe_module",
            }:
                raise serializers.ValidationError("不可覆盖平台保留的 Meta 字段")
            if (
                not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key)
                or len(key) > 128
                or not isinstance(item, str)
                or len(item) > 512
            ):
                raise serializers.ValidationError("Meta 键使用字母数字下划线，值必须是字符串")
        return value

    def validate(self, attrs):
        follow = attrs.get(
            "follow_host_address", getattr(self.instance, "follow_host_address", False)
        )
        host = attrs.get("host", getattr(self.instance, "host", None))
        if follow and not host:
            raise serializers.ValidationError({"host": "跟随资产地址需要关联 CMDB 主机"})
        interval = attrs.get(
            "sync_interval_minutes", getattr(self.instance, "sync_interval_minutes", 0)
        )
        if interval and self.automatic_changed(attrs):
            from common.auth.rbac import verify_permission

            request = self.context.get("request")
            user = getattr(request, "user", None)
            if (
                not user
                or not user.is_active
                or not verify_permission(
                    user,
                    f"/api/v1/monitoring/targets/{getattr(self.instance, 'pk', 0)}/sync",
                    "POST",
                )[0]
            ):
                raise serializers.ValidationError(
                    {"sync_interval_minutes": "启用自动同步需要有效账号和同步权限"}
                )
            if (
                follow
                and not verify_permission(user, f"/api/v1/cmdb/hosts/{host.pk}", "GET")[
                    0
                ]
            ):
                raise serializers.ValidationError({"host": "缺少关联主机读取权限"})
        kind = attrs.get("kind", getattr(self.instance, "kind", "host"))
        if kind == "blackbox":
            target = attrs.get(
                "probe_target", getattr(self.instance, "probe_target", "")
            )
            try:
                parsed = urlsplit(target)
            except ValueError:
                raise serializers.ValidationError(
                    {"probe_target": "探测地址格式不正确"}
                ) from None
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.fragment
            ):
                raise serializers.ValidationError(
                    {"probe_target": "请填写不含凭据的 HTTP(S) 探测地址"}
                )
            try:
                validate_endpoint(f"{parsed.scheme}://{parsed.netloc}")
            except serializers.ValidationError:
                raise serializers.ValidationError(
                    {"probe_target": "探测地址不允许使用云元数据、链路本地或无效地址"}
                ) from None
            module = attrs.get(
                "probe_module", getattr(self.instance, "probe_module", "http_2xx")
            )
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", module):
                raise serializers.ValidationError({"probe_module": "请输入 Blackbox 模块名称"})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        connection = validated_data["connection"]
        if (
            not ConsulConnection.objects.select_for_update()
            .filter(pk=connection.pk)
            .exists()
        ):
            raise serializers.ValidationError({"connection": "连接已删除，请重新选择"})
        if validated_data.get("sync_interval_minutes"):
            validated_data["auto_sync_actor"] = self.context["request"].user
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        previous_connection_id = instance.connection_id
        new_connection_id = validated_data.get("connection", instance.connection).pk
        connection_ids = sorted({previous_connection_id, new_connection_id})
        locked_ids = list(
            ConsulConnection.objects.select_for_update()
            .filter(pk__in=connection_ids)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        if locked_ids != connection_ids:
            raise serializers.ValidationError({"connection": "连接已变更，请刷新重试"})
        instance = MonitoringTarget.objects.select_for_update().get(pk=instance.pk)
        if instance.connection_id != previous_connection_id:
            raise serializers.ValidationError("目标连接已变更，请刷新重试")
        if instance.sync_records.filter(status__in=ACTIVE).exists():
            raise serializers.ValidationError("目标正在同步，请稍后修改")
        if self.automatic_changed(validated_data):
            if validated_data.get(
                "sync_interval_minutes", instance.sync_interval_minutes
            ):
                validated_data["auto_sync_actor"] = self.context["request"].user
            else:
                validated_data["auto_sync_actor"] = None
            validated_data["next_auto_sync_at"] = None
        if validated_data.get(
            "connection", instance.connection
        ).pk != instance.connection_id and (
            instance.registered or instance.registration_uncertain
        ):
            raise serializers.ValidationError({"connection": "请先注销，再更换连接"})
        return super().update(instance, validated_data)


class SyncRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncRecord
        fields = "__all__"
        read_only_fields = [field.name for field in SyncRecord._meta.fields]

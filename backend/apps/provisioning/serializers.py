import json

from django.db import transaction
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .schema_serializers import (
    ProvisioningAttemptSummarySerializer,
    StateProtectionSummarySerializer,
)
from apps.cmdb.crypto import encrypt_secret
from .contracts import ProvisioningError, validate_inputs, validate_resource_scope
from .models import (
    ResourceTemplate,
    ResourceTemplateVersion,
    ProvisioningCredential,
    ProvisioningRequest,
    ProvisioningPlan,
    ProvisioningEvent,
    ProvisioningAttempt,
)


class CredentialSerializer(serializers.ModelSerializer):
    secret = serializers.JSONField(write_only=True, required=False)
    has_secret = serializers.SerializerMethodField()

    class Meta:
        model = ProvisioningCredential
        fields = [
            "id",
            "source",
            "name",
            "secret",
            "has_secret",
            "revision",
            "is_active",
        ]
        read_only_fields = ["revision"]

    def get_has_secret(self, obj) -> bool:
        return bool(obj.encrypted_secret)

    def validate(self, attrs):
        source = attrs.get("source", getattr(self.instance, "source", None))
        if source.source_type != "cloud" or source.cloud_provider not in {
            "aliyun",
            "tencent",
        }:
            raise serializers.ValidationError("创建凭据仅支持公有云账号")
        if self.instance and source.pk != self.instance.source_id:
            raise serializers.ValidationError("已有创建凭据不可更换云账号")
        secret = attrs.get("secret")
        if not self.instance and not secret:
            raise serializers.ValidationError("请填写创建凭据")
        if secret is not None:
            keys = (
                {"access_key_id", "access_key_secret"}
                if source.cloud_provider == "aliyun"
                else {"secret_id", "secret_key"}
            )
            if (
                not isinstance(secret, dict)
                or set(secret) != keys
                or any(not isinstance(v, str) or not v.strip() for v in secret.values())
            ):
                raise serializers.ValidationError("请填写完整的云 API 创建凭据")
        return attrs

    def create(self, validated_data):
        secret = validated_data.pop("secret")
        return ProvisioningCredential.objects.create(
            **validated_data, encrypted_secret=encrypt_secret(json.dumps(secret))
        )

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = ProvisioningCredential.objects.select_for_update().get(
            pk=instance.pk
        )
        secret = validated_data.pop("secret", None)
        if secret is not None:
            instance.encrypted_secret = encrypt_secret(json.dumps(secret))
            instance.revision += 1
        return super().update(instance, validated_data)


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceTemplate
        fields = ["id", "name", "provider", "description", "is_active"]

    def validate_provider(self, value):
        if self.instance and value != self.instance.provider:
            raise serializers.ValidationError("已有模板不可更换云平台")
        return value


class VersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceTemplateVersion
        fields = ["id", "template", "number", "status", "constraints", "published_at"]
        read_only_fields = ["status", "published_at"]

    def validate_constraints(self, value):
        regions = value.get("regions") if isinstance(value, dict) else None
        if (
            not isinstance(regions, list)
            or not regions
            or any(not isinstance(item, str) or not item for item in regions)
        ):
            raise serializers.ValidationError("请配置允许的地域列表")
        from .catalog.policy import validate_selectors

        try:
            validate_selectors(value)
        except ProvisioningError as exc:
            raise serializers.ValidationError(str(exc)) from None
        return value

    def validate(self, attrs):
        if self.instance and self.instance.status == "published":
            raise serializers.ValidationError("已发布版本不可修改")
        return attrs


class PlanSerializer(serializers.ModelSerializer):
    attempt = serializers.SerializerMethodField()

    class Meta:
        model = ProvisioningPlan
        fields = [
            "id",
            "revision",
            "status",
            "digest",
            "summary",
            "error_message",
            "expires_at",
            "confirmed_by",
            "created_at",
            "attempt",
            "resource_snapshot",
        ]
        read_only_fields = fields

    @extend_schema_field(ProvisioningAttemptSummarySerializer(allow_null=True))
    def get_attempt(self, obj):
        try:
            attempt = obj.attempt
        except ProvisioningAttempt.DoesNotExist:
            return None
        return {
            "id": attempt.pk,
            "status": attempt.status,
            "error_message": attempt.error_message,
            "instance_ids": attempt.instance_ids,
            "asset_ids": attempt.asset_ids,
        }


class RequestSerializer(serializers.ModelSerializer):
    stateProtection = serializers.SerializerMethodField()
    notification_config = serializers.JSONField(write_only=True, required=False)
    allowed_actions = serializers.SerializerMethodField()
    plans = PlanSerializer(many=True, read_only=True)
    source_name = serializers.CharField(source="credential.source.name", read_only=True)
    template_name = serializers.CharField(
        source="version.template.name", read_only=True
    )

    class Meta:
        model = ProvisioningRequest
        fields = [
            "id",
            "name",
            "created_by",
            "version",
            "credential",
            "region",
            "parameters",
            "revision",
            "requires_approval",
            "approval_status",
            "execution_status",
            "inventory_status",
            "plans",
            "created_at",
            "source_name",
            "template_name",
            "allowed_actions",
            "notification_config",
            "stateProtection",
        ]
        read_only_fields = [
            "created_by",
            "revision",
            "requires_approval",
            "approval_status",
            "execution_status",
            "inventory_status",
        ]

    def get_allowed_actions(self, obj) -> list[str]:
        from common.auth.rbac import verify_permission

        user = self.context["request"].user
        own = user.pk == obj.created_by_id
        actions = (
            ["plan", "confirm", "execute", "reconcile"]
            if own
            else ["approve", "reject"]
        )
        actions = actions + ["restore-preview", "restore-confirm"]
        allowed = [
            name
            for name in actions
            if verify_permission(
                user, f"/api/v1/provisioning/requests/{obj.pk}/{name}", "POST"
            )[0]
        ]
        if verify_permission(
            user, f"/api/v1/provisioning/requests/{obj.pk}/state-versions", "GET"
        )[0]:
            allowed.append("state-versions")
        if verify_permission(user, "/api/v1/provisioning/review", "GET")[0] and not own:
            allowed.extend(["resolution-preview", "resolution-confirm"])
        return allowed

    @extend_schema_field(StateProtectionSummarySerializer)
    def get_stateProtection(self, obj):
        from .state_protection import protection_summary

        return protection_summary(obj)

    def validate(self, attrs):
        if self.instance:
            raise serializers.ValidationError("申请提交后不可原地修改，请重新申请")
        try:
            from .services import check_source

            config = attrs.pop("notification_config", {})
            from apps.automation.failure_alerts import (
                validate_failure_alert,
                freeze_failure_alert,
            )

            attrs["notification_snapshot"] = (
                freeze_failure_alert(validate_failure_alert(config)) or {}
            )
            record = ProvisioningRequest(**attrs)
            check_source(record)
            validate_inputs(record.parameters, record.version.template.provider)
            validate_resource_scope(record)
            from common.auth.rbac import verify_permission

            actor = self.context["request"].user
            if not verify_permission(
                actor,
                f"/api/v1/provisioning/credentials/{record.credential_id}/use",
                "POST",
            )[0]:
                raise ProvisioningError("无此云账号创建凭据的使用权限")
        except (ProvisioningError, KeyError, TypeError) as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return attrs


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProvisioningEvent
        fields = ["id", "kind", "message", "actor", "plan", "created_at"]

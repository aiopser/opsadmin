from rest_framework import serializers
from apps.automation.failure_alerts import validate_failure_alert
from .models import SecurityAdvisory, SecurityCollection, SecuritySubscription
from django.db import transaction


class SubscriptionSerializer(serializers.ModelSerializer):
    interval_minutes = serializers.IntegerField(min_value=5, max_value=10080)
    keywords = serializers.ListField(
        child=serializers.CharField(max_length=100, allow_blank=False),
        max_length=30,
        required=False,
    )
    severities = serializers.ListField(
        child=serializers.ChoiceField(
            choices=["critical", "high", "medium", "low", "unknown"]
        ),
        required=False,
    )
    notification = serializers.JSONField(required=False)

    class Meta:
        model = SecuritySubscription
        fields = [
            "id",
            "name",
            "enabled",
            "interval_minutes",
            "keywords",
            "severities",
            "notification",
            "initialized_at",
            "last_attempt_at",
        ]
        read_only_fields = ["initialized_at", "last_attempt_at"]

    def validate_notification(self, value):
        return validate_failure_alert(value) or {}

    def validate(self, attrs):
        enabled = attrs.get("enabled", getattr(self.instance, "enabled", False))
        config = attrs.get("notification", getattr(self.instance, "notification", {}))
        if enabled and not config:
            raise serializers.ValidationError("启用订阅前请选择通知模板")
        if enabled:
            from common.auth.rbac import verify_permission

            actor = getattr(self.context.get("request"), "user", None)
            if (
                not actor
                or not actor.is_active
                or not verify_permission(
                    actor,
                    f"/api/v1/security/subscriptions/{getattr(self.instance, 'pk', 0)}/collect",
                    "POST",
                )[0]
            ):
                raise serializers.ValidationError("启用或修改周期订阅需要采集执行权限")
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = SecuritySubscription.objects.select_for_update().get(pk=instance.pk)
        if SecurityCollection.objects.filter(
            subscription=instance, status__in=["queued", "running"]
        ).exists():
            raise serializers.ValidationError("公告采集中，请稍后修改订阅")
        return super().update(instance, validated_data)


class AdvisorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityAdvisory
        fields = "__all__"


class CollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityCollection
        fields = "__all__"

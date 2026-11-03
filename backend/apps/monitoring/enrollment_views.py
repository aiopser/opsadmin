from django.db import transaction
from rest_framework import serializers, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema

from common.api.responses import api_ok_response
from common.api.schema import api_envelope_serializer
from common.api.viewsets import StandardModelViewSet
from apps.audit_center.services import create_domain_audit_event
from .models import EnrollmentPolicy, EnrollmentRun
from .registration import ACTIVE
from .enrollment import (
    validate_rules,
    preview_policy,
    enqueue_policy_run,
    publish_policy_run,
    lock_policy,
)


class EnrollmentPolicySerializer(serializers.ModelSerializer):
    connection_name = serializers.CharField(source="connection.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True, default="")
    actor_name = serializers.CharField(
        source="actor.username", read_only=True, default=""
    )
    interval_minutes = serializers.IntegerField(
        min_value=1, max_value=10080, required=False
    )
    target_sync_interval_minutes = serializers.IntegerField(
        min_value=0, max_value=10080, required=False
    )
    port = serializers.IntegerField(min_value=1, max_value=65535, required=False)

    class Meta:
        model = EnrollmentPolicy
        fields = "__all__"
        read_only_fields = [
            "actor",
            "is_active",
            "next_run_at",
            "last_run_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        scope = attrs.get("scope", getattr(self.instance, "scope", "group"))
        if scope == "group":
            group = attrs.get("group", getattr(self.instance, "group", None))
            if not group or not group.is_active:
                raise ValidationError({"group": "请选择有效主机分组"})
            attrs["match_rule"] = {}
        else:
            validate_rules(
                attrs.get("match_rule", getattr(self.instance, "match_rule", {}))
            )
            attrs["group"] = None
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = lock_policy(instance.pk)
        if instance.runs.filter(status__in=ACTIVE).exists():
            raise ValidationError("策略正在执行，请稍后修改")
        validated_data["is_active"] = False
        validated_data["next_run_at"] = None
        return super().update(instance, validated_data)


class EnrollmentRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnrollmentRun
        fields = "__all__"
        read_only_fields = [field.name for field in EnrollmentRun._meta.fields]


class PolicyConfirmationSerializer(serializers.Serializer):
    preview_token = serializers.CharField(max_length=1024)


class EnrollmentPolicyViewSet(StandardModelViewSet):
    queryset = EnrollmentPolicy.objects.select_related("connection", "group", "actor")
    serializer_class = EnrollmentPolicySerializer
    search_fields = ["name"]
    filterset_fields = ["is_active", "scope", "connection"]
    ordering_fields = ["id", "name", "updated_at"]

    def audit(self, row, action):
        create_domain_audit_event(
            self.request.user,
            "monitoring.enrollment." + action,
            "enrollment_policy",
            row.pk,
            after={"name": row.name, "scope": row.scope, "is_active": row.is_active},
            request=self.request,
            domain="monitoring",
        )

    def perform_create(self, serializer, request=None):
        self.audit(serializer.save(actor=self.request.user), "create")

    def perform_update(self, serializer, request=None):
        self.audit(serializer.save(), "update")

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        row = lock_policy(self.get_object().pk)
        if row.is_active or row.runs.filter(status__in=ACTIVE).exists():
            raise ValidationError("请先暂停策略并等待执行结束，再删除")
        self.audit(row, "delete")
        row.delete()
        return api_ok_response()

    @extend_schema(
        responses=api_envelope_serializer("EnrollmentPreview", serializers.DictField())
    )
    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        return api_ok_response(preview_policy(self.get_object(), request.user))

    def confirm(self, enable=False):
        values = PolicyConfirmationSerializer(data=self.request.data)
        values.is_valid(raise_exception=True)
        run = enqueue_policy_run(
            self.get_object().pk,
            self.request.user,
            values.validated_data["preview_token"],
            enable=enable,
        )
        publish_policy_run(run.pk)
        run.refresh_from_db()
        return api_ok_response(EnrollmentRunSerializer(run).data)

    @extend_schema(
        request=PolicyConfirmationSerializer,
        responses=api_envelope_serializer(
            "EnrollmentRunSubmitted", EnrollmentRunSerializer
        ),
    )
    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        return self.confirm()

    @extend_schema(
        request=PolicyConfirmationSerializer,
        responses=api_envelope_serializer("EnrollmentEnabled", EnrollmentRunSerializer),
    )
    @action(detail=True, methods=["post"])
    def enable(self, request, pk=None):
        return self.confirm(enable=True)

    @extend_schema(
        request=None,
        responses=api_envelope_serializer(
            "EnrollmentPaused", EnrollmentPolicySerializer
        ),
    )
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def pause(self, request, pk=None):
        row = lock_policy(self.get_object().pk)
        row.is_active = False
        row.next_run_at = None
        row.save(update_fields=["is_active", "next_run_at"])
        self.audit(row, "pause")
        return api_ok_response(self.get_serializer(row).data)


class EnrollmentRunViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    queryset = EnrollmentRun.objects.all()
    serializer_class = EnrollmentRunSerializer
    filterset_fields = ["policy", "status"]
    ordering_fields = ["id", "created_at"]

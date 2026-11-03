"""Exact payloads returned by the jobs dashboard and engine settings APIs."""

from rest_framework import serializers
from common.api.schema_serializers import RuntimeEnvironmentSerializer
from .models import ScheduledJob


class SecurityStatsSerializer(serializers.Serializer):
    ruleCount = serializers.IntegerField()
    monthBlocked = serializers.IntegerField()
    accidents = serializers.IntegerField()


class DashboardStatsSerializer(serializers.Serializer):
    todayExecutions = serializers.IntegerField()
    finishedExecutions = serializers.IntegerField()
    successRate = serializers.FloatField(allow_null=True)
    avgResponseSeconds = serializers.FloatField(allow_null=True)
    scheduledExecutions = serializers.IntegerField()
    blockedCommands = serializers.IntegerField()


class ExecutionDistributionItemSerializer(serializers.Serializer):
    key = serializers.CharField()
    count = serializers.IntegerField()


class ExecutionDistributionSerializer(serializers.Serializer):
    periodDays = serializers.IntegerField()
    total = serializers.IntegerField()
    items = ExecutionDistributionItemSerializer(many=True)


class RedisHealthSerializer(serializers.Serializer):
    healthy = serializers.BooleanField()
    error = serializers.CharField(allow_blank=True)


class WorkersHealthSerializer(serializers.Serializer):
    healthy = serializers.BooleanField()
    count = serializers.IntegerField()
    nodes = serializers.ListField(child=serializers.CharField())
    queues = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField())
    )
    missingQueues = serializers.ListField(child=serializers.CharField())


class WebsocketHealthSerializer(serializers.Serializer):
    healthy = serializers.BooleanField()
    backend = serializers.CharField()


class SevenDayHealthSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    finished = serializers.IntegerField()
    successRate = serializers.FloatField()


class DashboardHealthSerializer(serializers.Serializer):
    redis = RedisHealthSerializer()
    workers = WorkersHealthSerializer()
    queues = serializers.DictField(child=serializers.IntegerField(allow_null=True))
    websocket = WebsocketHealthSerializer()
    sevenDay = SevenDayHealthSerializer()
    checkedAt = serializers.DateTimeField()
    environment = RuntimeEnvironmentSerializer()


class DashboardRecentItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.CharField()
    target = serializers.CharField()
    status = serializers.CharField()
    executor = serializers.CharField(allow_blank=True)
    time = serializers.DateTimeField()


class EngineSettingsSerializer(serializers.Serializer):
    timeout = serializers.IntegerField(min_value=1)
    forks = serializers.IntegerField(min_value=1)
    host_strategy = serializers.ChoiceField(choices=ScheduledJob.HostStrategy.choices)
    serial_batch = serializers.IntegerField(min_value=1)
    max_fail_percentage = serializers.IntegerField(min_value=0, max_value=100)


class EngineSettingsUpdateSerializer(EngineSettingsSerializer):
    def get_fields(self):
        fields = super().get_fields()
        for field in fields.values():
            field.required = False
        return fields


class ScheduleOutcomeSummarySerializer(serializers.Serializer):
    outcome = serializers.CharField()
    reason = serializers.CharField(allow_blank=True)
    scheduledFor = serializers.DateTimeField()
    runId = serializers.IntegerField(allow_null=True)

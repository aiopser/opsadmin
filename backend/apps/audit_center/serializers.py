from rest_framework import serializers

from .models import DomainAuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    actorName = serializers.CharField(source="actor.username", default="", read_only=True)
    resourceType = serializers.CharField(source="resource_type", read_only=True)
    resourceId = serializers.CharField(source="resource_id", read_only=True)
    requestId = serializers.CharField(source="request_id", read_only=True)
    runId = serializers.CharField(source="run_id", read_only=True)
    ipAddress = serializers.IPAddressField(source="ip_address", read_only=True)
    userAgent = serializers.CharField(source="user_agent", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = DomainAuditEvent
        fields = ("id", "domain", "actor", "actorName", "action", "resourceType", "resourceId", "before", "after", "requestId", "runId", "result", "ipAddress", "userAgent", "createdAt")
        read_only_fields = fields

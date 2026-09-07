from common.api.serializers import StandardModelSerializer

from .models import DomainAuditEvent


class AuditEventSerializer(StandardModelSerializer):
    class Meta:
        model = DomainAuditEvent
        fields = "__all__"

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["actorName"] = instance.actor.username if instance.actor else ""
        # soybean 前端 camelCase 别名
        representation["resourceType"] = representation.get("resource_type")
        representation["resourceId"] = representation.get("resource_id")
        representation["ipAddress"] = representation.get("ip_address")
        representation["userAgent"] = representation.get("user_agent")
        representation["requestId"] = representation.get("request_id")
        representation["createdAt"] = representation.get("created_at")
        return representation

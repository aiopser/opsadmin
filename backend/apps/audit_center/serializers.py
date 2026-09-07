from common.api.serializers import StandardModelSerializer

from .models import DomainAuditEvent


class AuditEventSerializer(StandardModelSerializer):
    class Meta:
        model = DomainAuditEvent
        fields = "__all__"

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["actorName"] = instance.actor.username if instance.actor else ""
        return representation

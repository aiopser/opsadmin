from common.api.viewsets import StandardModelViewSet

from .models import DomainAuditEvent
from .serializers import AuditEventSerializer


class AuditEventViewSet(StandardModelViewSet):
    http_method_names = ["get", "head", "options"]
    queryset = DomainAuditEvent.objects.select_related("actor").all()
    serializer_class = AuditEventSerializer
    ordering_fields = ("id", "created_at")
    filterset_fields = (
        "domain",
        "actor",
        "action",
        "resource_type",
        "resource_id",
    )
    search_fields = (
        "action",
        "resource_type",
        "resource_id",
        "actor__username",
        "ip_address",
        "user_agent",
    )

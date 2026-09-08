import json

from django.http import StreamingHttpResponse
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.viewsets import ReadOnlyModelViewSet

from common.api.responses import api_ok_response

from .models import DomainAuditEvent
from .serializers import AuditEventSerializer


class AuditEventViewSet(ReadOnlyModelViewSet):
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
        "run_id",
        "result",
    )
    search_fields = (
        "action",
        "resource_type",
        "resource_id",
        "actor__username",
        "ip_address",
        "user_agent",
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(actor=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        return api_ok_response(self.get_serializer(self.get_object()).data)

    @action(detail=False, methods=["get"])
    def export(self, request):
        if not request.user.is_superuser and not request.user.role.filter(
            is_active=True, permission__code="audit.event.export", permission__is_active=True
        ).exists():
            raise PermissionDenied("Audit export permission required")
        queryset = self.filter_queryset(self.get_queryset())
        response = StreamingHttpResponse(
            (json.dumps(self.get_serializer(event).data, ensure_ascii=False) + "\n" for event in queryset.iterator(chunk_size=200)),
            content_type="application/x-ndjson",
        )
        response["Content-Disposition"] = 'attachment; filename="audit-events.ndjson"'
        return response

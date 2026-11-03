import json
from ipaddress import ip_address as parse_ip_address

from django.db.models import Q
from django.http import StreamingHttpResponse
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.viewsets import ReadOnlyModelViewSet
from django.utils.dateparse import parse_date

from common.api.responses import api_ok_response

from .labels import match_event_pairs
from .models import DomainAuditEvent
from .serializers import AuditEventSerializer, LoginEventSerializer

KEYWORD_FIELDS = (
    "action",
    "resource_type",
    "resource_id",
    "actor__username",
    "ip_address",
    "user_agent",
)


def _keyword_query(queryset, keyword):
    """关键词匹配原始字段 + 表格展示名（中文操作内容/操作对象）。"""
    query = Q()
    for field in KEYWORD_FIELDS:
        query |= Q(**{f"{field}__icontains": keyword})
    pairs = queryset.order_by().values_list("action", "resource_type").distinct()
    for action, resource_type in match_event_pairs(list(pairs), keyword):
        query |= Q(action=action, resource_type=resource_type)
    return query


def _parse_login_date(value):
    try:
        return parse_date(value) if value else None
    except ValueError as exc:
        raise ValidationError({"date": "Invalid date"}) from exc


class LoginEventViewSet(ReadOnlyModelViewSet):
    http_method_names = ["get", "head", "options"]
    serializer_class = LoginEventSerializer
    queryset = DomainAuditEvent.objects.filter(
        domain=DomainAuditEvent.Domain.SECURITY,
        resource_type="login",
        action__in=("auth.login.success", "auth.login.failure"),
    ).order_by("-created_at", "-id")

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        username = params.get("username", "").strip()
        ip_address = params.get("ipAddress", "").strip()
        result = params.get("result", "").strip()
        start = _parse_login_date(params.get("startDate", ""))
        end = _parse_login_date(params.get("endDate", ""))
        if username:
            queryset = queryset.filter(resource_id__icontains=username)
        if ip_address:
            try:
                parse_ip_address(ip_address)
            except ValueError as exc:
                raise ValidationError({"ipAddress": "Invalid IP address"}) from exc
            queryset = queryset.filter(ip_address=ip_address)
        if result in {"success", "failure"}:
            queryset = queryset.filter(result=result)
        if start:
            queryset = queryset.filter(created_at__date__gte=start)
        if end:
            queryset = queryset.filter(created_at__date__lte=end)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        return api_ok_response(self.get_serializer(self.get_object()).data)


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

    def get_queryset(self):

        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(actor=self.request.user)
        keyword = self.request.query_params.get("search", "").strip()
        if keyword:
            queryset = queryset.filter(_keyword_query(queryset, keyword))
        return queryset

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

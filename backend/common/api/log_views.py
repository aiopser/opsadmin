from datetime import date, datetime, time, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from rest_framework import serializers
from drf_spectacular.utils import extend_schema

from common.api.responses import api_ok_response
from common.api.views import StandardApiView
from common.api.schema import api_envelope_serializer
from common.api.schema_serializers import (
    OperationLogPageSerializer,
    VisitOverviewSerializer,
    VisitTrendSerializer,
)
from apps.permission.models import OperationLog


def _parse_date(value, fallback):
    if not value:
        return fallback
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return fallback


def _get_date_range(request):
    values = []
    values.extend(request.query_params.getlist("createTime"))
    values.extend(request.query_params.getlist("createTime[]"))
    start = request.query_params.get("startDate")
    end = request.query_params.get("endDate")
    if len(values) >= 2:
        start, end = values[0], values[1]
    start_date = _parse_date(start, None)
    end_date = _parse_date(end, None)
    return start_date, end_date


def _in_date_range(created_at, start_date, end_date):
    if not created_at:
        return True
    current = created_at.date() if hasattr(created_at, "date") else created_at
    if start_date and current < start_date:
        return False
    if end_date and current > end_date:
        return False
    return True


def _format_dt(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def _format_operation_log(log):
    return {
        "id": log.id,
        "module": log.module,
        "actionType": log.action_type,
        "title": log.title,
        "content": log.content,
        "operatorId": log.operator_id,
        "operatorName": log.operator_name or "anonymous",
        "requestUri": log.request_uri,
        "requestMethod": log.request_method,
        "ip": log.ip,
        "region": log.region,
        "device": log.device,
        "browser": log.browser,
        "os": log.os,
        "status": log.status,
        "executionTime": log.execution_time,
        "errorMsg": log.error_msg,
        "createTime": _format_dt(log.created_at),
    }


class LogListApiView(StandardApiView):
    @extend_schema(
        responses=api_envelope_serializer(
            "OperationLogPageResponse", OperationLogPageSerializer
        )
    )
    def get(self, request, *args, **kwargs):
        start_date, end_date = _get_date_range(request)
        keywords = request.query_params.get("keywords", "")
        queryset = OperationLog.objects.select_related("operator").order_by(
            "-created_at", "-id"
        )
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        if keywords and keywords.strip():
            keyword = keywords.strip()
            queryset = queryset.filter(
                Q(operator_name__icontains=keyword)
                | Q(ip__icontains=keyword)
                | Q(request_uri__icontains=keyword)
                | Q(title__icontains=keyword)
            )
        total = queryset.count()
        page = int(
            request.query_params.get("pageNum") or request.query_params.get("page") or 1
        )
        size = int(
            request.query_params.get("pageSize")
            or request.query_params.get("size")
            or 10
        )
        start_index = max(page - 1, 0) * size
        page_items = [
            _format_operation_log(log)
            for log in queryset[start_index : start_index + size]
        ]
        return api_ok_response(
            {
                "list": page_items,
                "total": total,
                "count": total,
                "page": page,
                "size": size,
            }
        )


class VisitOverviewApiView(StandardApiView):
    @extend_schema(
        responses=api_envelope_serializer(
            "VisitOverviewResponse", VisitOverviewSerializer
        )
    )
    def get(self, request, *args, **kwargs):
        today = date.today()
        yesterday = today - timedelta(days=1)
        queryset = OperationLog.objects.all()
        today_pv = queryset.filter(created_at__date=today).count()
        yesterday_pv = queryset.filter(created_at__date=yesterday).count()
        total_pv = queryset.count()
        today_actors = set(
            queryset.filter(created_at__date=today).values_list(
                "operator_name", flat=True
            )
        )
        total_actors = set(queryset.values_list("operator_name", flat=True))
        today_uv = len({actor for actor in today_actors if actor})
        total_uv = len({actor for actor in total_actors if actor})
        pv_growth = (
            0
            if yesterday_pv == 0
            else round((today_pv - yesterday_pv) / yesterday_pv * 100, 2)
        )
        return api_ok_response(
            {
                "todayUvCount": today_uv,
                "totalUvCount": total_uv,
                "uvGrowthRate": 0,
                "todayPvCount": today_pv,
                "totalPvCount": total_pv,
                "pvGrowthRate": pv_growth,
            }
        )


class VisitTrendApiView(StandardApiView):
    @extend_schema(
        responses=api_envelope_serializer("VisitTrendResponse", VisitTrendSerializer)
    )
    def get(self, request, *args, **kwargs):
        today = date.today()
        start_date = _parse_date(
            request.query_params.get("startDate"), today - timedelta(days=6)
        )
        end_date = _parse_date(request.query_params.get("endDate"), today)
        if start_date > end_date:
            start_date, end_date = end_date, start_date

        max_days = 366
        days = min((end_date - start_date).days + 1, max_days)
        dates = [
            (start_date + timedelta(days=offset)).strftime("%Y-%m-%d")
            for offset in range(days)
        ]
        pv_by_date = {day: 0 for day in dates}
        uv_by_date = {day: set() for day in dates}
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)
        rows = (
            OperationLog.objects.filter(created_at__range=(start_dt, end_dt))
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(count=Count("id"))
        )
        for row in rows:
            day = row["day"].strftime("%Y-%m-%d")
            if day in pv_by_date:
                pv_by_date[day] += row["count"]
        for log in OperationLog.objects.filter(created_at__range=(start_dt, end_dt)):
            day = log.created_at.strftime("%Y-%m-%d")
            if log.operator_name and day in uv_by_date:
                uv_by_date[day].add(log.operator_name)

        return api_ok_response(
            {
                "dates": dates,
                "pvList": [pv_by_date[day] for day in dates],
                "uvList": [len(uv_by_date[day]) for day in dates],
            }
        )

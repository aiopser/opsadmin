import csv
import socket
from datetime import datetime, timedelta

from django.conf import settings
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Avg, Count
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.decorators import action
from rest_framework.views import APIView

from .tasks import enqueue_workflow_run
from .cron import next_cron_time
from apps.cmdb.models import WorkerPool
from common.api.responses import api_error_response, api_ok_response
from common.api.viewsets import StandardModelViewSet

from apps.audit_center.services import create_domain_audit_event
from .recovery import recover_stale_execution, request_execution_cancel
from .settings_service import (
    get_engine_settings,
    get_notify_settings,
    save_engine_settings,
    save_notify_settings,
)
from .services import (
    InvalidTargetHosts,
    create_workflow_run_from_host_ids,
    scheduled_job_run_options,
)
from .models import (
    CommandIntercept,
    Gateway,
    HostRunResult,
    JobEventLog,
    NodeRun,
    NodeRunAttempt,
    ScheduledJob,
    SecurityRule,
    WorkflowRun,
)
from .serializers import (
    CommandInterceptSerializer,
    GatewaySerializer,
    HostRunResultSerializer,
    JobEventLogSerializer,
    ModuleRunCreateSerializer,
    NodeRunSerializer,
    NodeRunAttemptSerializer,
    PlaybookRunCreateSerializer,
    QuickCommandRunCreateSerializer,
    ScheduledJobSerializer,
    SecurityRuleSerializer,
    WorkflowRunCreateSerializer,
    WorkflowRunSerializer,
)


def _workflow_run_audit_summary(run):
    """从 WorkflowRun 提取审计「操作内容」可读摘要，供前端展示命令详情。

    依据 run.input_vars 中的 execution_source 返回对应键：
    快速执行 -> command、Playbook -> playbook_name、Module -> module，
    其余普通工作流回退为工作流模板名称 name。
    """
    input_vars = run.input_vars or {}
    source = input_vars.get("execution_source")
    if source == "quick_command" and input_vars.get("command_content"):
        return {"command": input_vars["command_content"]}
    if source == "playbook":
        return {"playbook_name": input_vars.get("playbook_name") or "Playbook"}
    if source == "module":
        summary = (
            f"{input_vars.get('module') or ''} {input_vars.get('module_args') or ''}"
        ).strip()
        return {"module": summary} if summary else {}
    version = run.workflow_version
    workflow = getattr(version, "workflow", None) if version else None
    name = getattr(workflow, "name", "") or ""
    return {"name": name} if name else {}


class WorkflowRunViewSet(StandardModelViewSet):
    http_method_names = ["get", "post", "head", "options"]
    queryset = WorkflowRun.objects.select_related(
        "workflow_version",
        "workflow_version__workflow",
        "triggered_by",
        "worker_pool",
    ).all()
    serializer_class = WorkflowRunSerializer
    ordering_fields = ("id", "status", "started_at", "finished_at", "updated_at")
    filterset_fields = (
        "status",
        "trigger_type",
        "execution_kind",
        "workflow_version",
        "worker_pool",
    )
    search_fields = ("=id", "failure_reason", "workflow_version__workflow__name")
    run_domain = WorkflowRun.RunDomain.TASK

    def get_queryset(self):
        queryset = super().get_queryset().filter(run_domain=self.run_domain)
        created_after = self.request.query_params.get("created_after")
        created_before = self.request.query_params.get("created_before")
        if created_after:
            value = parse_datetime(created_after)
            if value is None and parse_date(created_after):
                value = timezone.make_aware(
                    datetime.combine(parse_date(created_after), datetime.min.time())
                )
            if value:
                queryset = queryset.filter(created_at__gte=value)
        if created_before:
            value = parse_datetime(created_before)
            if value is None and parse_date(created_before):
                value = timezone.make_aware(
                    datetime.combine(parse_date(created_before), datetime.max.time())
                )
            if value:
                queryset = queryset.filter(created_at__lte=value)
        return queryset

    def get_object(self):
        run = super().get_object()
        recover_stale_execution(run.id)
        if run.status in {
            WorkflowRun.Status.PENDING,
            WorkflowRun.Status.QUEUED,
            WorkflowRun.Status.RUNNING,
            WorkflowRun.Status.CANCEL_REQUESTED,
        }:
            run.refresh_from_db()
        return run

    @action(methods=["GET"], detail=False, url_path="summary")
    def summary(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        counts = {
            row["status"]: row["count"]
            for row in queryset.values("status").annotate(count=Count("id"))
        }
        return api_ok_response(
            {
                "total": sum(counts.values()),
                "statuses": counts,
            }
        )

    @action(methods=["GET"], detail=False, url_path="export")
    def export_csv(self, request):
        queryset = self.filter_queryset(self.get_queryset()).order_by("-id")[:10000]
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="workflow-runs.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(
            [
                "Run ID",
                "Workflow",
                "Version",
                "Status",
                "Trigger",
                "Triggered by",
                "Targets",
                "Worker pool",
                "Created at",
                "Started at",
                "Finished at",
                "Duration (ms)",
                "Failure reason",
            ]
        )
        for run in queryset:
            writer.writerow(
                [
                    run.id,
                    run.workflow_version.workflow.name
                    if run.workflow_version
                    else run.get_execution_kind_display(),
                    run.workflow_version.version if run.workflow_version else "",
                    run.status,
                    run.trigger_type,
                    run.triggered_by.username if run.triggered_by else "",
                    len(run.target_snapshot or []),
                    run.worker_pool.name if run.worker_pool else "",
                    run.created_at,
                    run.started_at or "",
                    run.finished_at or "",
                    run.duration_ms or "",
                    run.failure_reason,
                ]
            )
        return response

    @action(methods=["GET"], detail=True, url_path="nodes")
    def nodes(self, request, pk=None):
        run = self.get_object()
        serializer = NodeRunSerializer(
            run.node_runs.select_related(
                "workflow_node",
                "command_version",
                "command_version__command",
            ),
            many=True,
        )
        return api_ok_response(serializer.data)

    @action(methods=["GET"], detail=True, url_path="events")
    def events(self, request, pk=None):
        run = self.get_object()
        event_logs = run.event_logs.all()
        after_id = request.query_params.get("after_id")
        if after_id:
            try:
                event_logs = event_logs.filter(id__gt=int(after_id))
            except (TypeError, ValueError):
                return api_error_response(message="after_id must be an integer")
        serializer = JobEventLogSerializer(event_logs, many=True)
        return api_ok_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = WorkflowRunCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        create_domain_audit_event(
            actor=request.user,
            action="workflow_run.create",
            resource_type="workflow_run",
            resource_id=run.id,
            after={
                "status": run.status,
                "target_count": len(run.target_snapshot or []),
                **_workflow_run_audit_summary(run),
            },
            request=request,
        )
        JobEventLog.objects.create(
            workflow_run=run,
            event_type="workflow_dispatch_requested",
            message="Workflow run dispatch requested.",
            payload={"workflow_run_id": run.id},
        )
        transaction.on_commit(lambda: enqueue_workflow_run(run.id))
        run.refresh_from_db()
        return api_ok_response(self.get_serializer(run).data)

    @action(methods=["POST"], detail=False, url_path="validate")
    def validate_run(self, request):
        serializer = WorkflowRunCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        workflow_version = values["workflow_version"]
        worker_pool = values["worker_pool"]
        return api_ok_response(
            {
                "valid": True,
                "workflowVersionId": workflow_version.id,
                "workflowName": workflow_version.workflow.name,
                "targetCount": len(values["hostIds"]),
                "workerPoolId": worker_pool.id,
                "workerPoolName": worker_pool.name,
            }
        )

    @action(methods=["POST"], detail=True, url_path="cancel")
    def cancel(self, request, pk=None):
        run = self.get_object()
        if run.status not in {
            WorkflowRun.Status.PENDING,
            WorkflowRun.Status.QUEUED,
            WorkflowRun.Status.RUNNING,
            WorkflowRun.Status.WAITING,
        }:
            return api_error_response(message="只有等待中或运行中的执行任务可以取消")

        previous_status = run.status
        run = request_execution_cancel(run.id)
        JobEventLog.objects.create(
            workflow_run=run,
            event_type="workflow_cancel_requested",
            message="Workflow run cancellation requested.",
            payload={"workflow_run_id": run.id},
        )
        create_domain_audit_event(
            actor=request.user,
            action="workflow_run.cancel",
            resource_type="workflow_run",
            resource_id=run.id,
            before={"status": previous_status},
            after={"status": run.status, **_workflow_run_audit_summary(run)},
            request=request,
        )
        return api_ok_response(self.get_serializer(run).data)

    @action(methods=["POST"], detail=True, url_path="retry-failed")
    def retry_failed(self, request, pk=None):
        run = self.get_object()
        if run.status != WorkflowRun.Status.FAILED:
            return api_error_response(message="只有失败的执行任务可以重试")

        retry_run = self._clone_run(run, request.user)
        JobEventLog.objects.create(
            workflow_run=retry_run,
            event_type="workflow_retry_requested",
            message="Retry failed nodes requested.",
            payload={"source_workflow_run_id": run.id, "workflow_run_id": retry_run.id},
        )
        create_domain_audit_event(
            actor=request.user,
            action="workflow_run.retry_failed",
            resource_type="workflow_run",
            resource_id=run.id,
            after={
                "status": "accepted",
                "retry_workflow_run_id": retry_run.id,
                **_workflow_run_audit_summary(run),
            },
            request=request,
        )
        transaction.on_commit(lambda: enqueue_workflow_run(retry_run.id))
        return api_ok_response(self.get_serializer(retry_run).data)

    @action(methods=["POST"], detail=True, url_path="rerun")
    def rerun(self, request, pk=None):
        run = self.get_object()
        if run.status in {
            WorkflowRun.Status.PENDING,
            WorkflowRun.Status.QUEUED,
            WorkflowRun.Status.RUNNING,
            WorkflowRun.Status.WAITING,
            WorkflowRun.Status.CANCEL_REQUESTED,
        }:
            return api_error_response(message="未结束的执行任务不能重跑")

        rerun_run = self._clone_run(run, request.user)
        JobEventLog.objects.create(
            workflow_run=rerun_run,
            event_type="workflow_rerun_requested",
            message="Workflow run rerun requested.",
            payload={"source_workflow_run_id": run.id, "workflow_run_id": rerun_run.id},
        )
        create_domain_audit_event(
            actor=request.user,
            action="workflow_run.rerun",
            resource_type="workflow_run",
            resource_id=run.id,
            after={
                "status": "accepted",
                "rerun_workflow_run_id": rerun_run.id,
                **_workflow_run_audit_summary(run),
            },
            request=request,
        )
        transaction.on_commit(lambda: enqueue_workflow_run(rerun_run.id))
        return api_ok_response(self.get_serializer(rerun_run).data)

    @staticmethod
    def _clone_run(run, user):
        """以原运行为模板克隆一个新的待调度运行（重试/重跑共用）。"""
        now = timezone.now()
        return WorkflowRun.objects.create(
            workflow_version=run.workflow_version,
            run_domain=run.run_domain,
            execution_kind=run.execution_kind,
            trigger_type=WorkflowRun.TriggerType.MANUAL,
            triggered_by=user,
            input_vars=run.input_vars,
            secret_input_vars_encrypted=run.secret_input_vars_encrypted,
            target_snapshot=run.target_snapshot,
            context_vars={"inputs": run.input_vars or {}},
            graph_snapshot=run.graph_snapshot,
            worker_pool=run.worker_pool,
            timeout_seconds=run.timeout_seconds,
            queue_timeout_seconds=run.queue_timeout_seconds,
            queue_deadline_at=now + timedelta(seconds=run.queue_timeout_seconds),
        )


class OpsWorkflowRunViewSet(WorkflowRunViewSet):
    """作业系统运行历史；与任务工作流共享执行引擎但不共享查询口径。"""

    run_domain = WorkflowRun.RunDomain.OPS

    def create(self, request, *args, **kwargs):
        return api_error_response("请使用快捷命令、Playbook 或 Module 执行接口")


class QuickCommandRunViewSet(StandardModelViewSet):
    http_method_names = ["post", "options"]
    queryset = WorkflowRun.objects.none()
    serializer_class = WorkflowRunSerializer

    def create(self, request, *args, **kwargs):
        serializer = QuickCommandRunCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        create_domain_audit_event(
            actor=request.user,
            action="quick_command_run.create",
            resource_type="workflow_run",
            resource_id=run.id,
            after={
                "status": run.status,
                "target_count": len(run.target_snapshot or []),
                **_workflow_run_audit_summary(run),
            },
            request=request,
        )
        JobEventLog.objects.create(
            workflow_run=run,
            event_type="workflow_dispatch_requested",
            message="Quick-command workflow run dispatch requested.",
            payload={"workflow_run_id": run.id},
        )
        transaction.on_commit(lambda: enqueue_workflow_run(run.id))
        run.refresh_from_db()
        return api_ok_response(WorkflowRunSerializer(run).data)


class ScheduledJobViewSet(StandardModelViewSet):
    queryset = ScheduledJob.objects.select_related(
        "workflow_version__workflow",
        "worker_pool",
        "last_workflow_run",
    ).all()
    serializer_class = ScheduledJobSerializer
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    ordering_fields = ("id", "name", "enabled", "next_run_at", "created_at")
    filterset_fields = ("enabled", "workflow_version", "worker_pool")
    search_fields = ("name", "workflow_version__workflow__name")

    def perform_create(self, serializer, request=None):
        cron_expression = serializer.validated_data.get("cron_expression", "0 * * * *")
        timezone_name = serializer.validated_data.get("timezone", "Asia/Shanghai")
        enabled = serializer.validated_data.get("enabled", True)
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user,
            next_run_at=(
                next_cron_time(cron_expression, timezone_name) if enabled else None
            ),
        )

    def perform_update(self, serializer, request=None):
        instance = serializer.instance
        enabled = serializer.validated_data.get("enabled", instance.enabled)
        cron_expression = serializer.validated_data.get(
            "cron_expression", instance.cron_expression
        )
        timezone_name = serializer.validated_data.get("timezone", instance.timezone)
        schedule_changed = (
            enabled != instance.enabled
            or cron_expression != instance.cron_expression
            or timezone_name != instance.timezone
        )
        next_run_at = instance.next_run_at
        if not enabled:
            next_run_at = None
        elif schedule_changed or next_run_at is None:
            next_run_at = next_cron_time(cron_expression, timezone_name)
        serializer.save(
            updated_by=self.request.user,
            next_run_at=next_run_at,
        )

    @action(methods=["POST"], detail=True, url_path="run-now")
    def run_now(self, request, pk=None):
        schedule = self.get_object()
        try:
            run_options = scheduled_job_run_options(schedule)
            run = create_workflow_run_from_host_ids(
                workflow_version=schedule.workflow_version,
                host_ids=schedule.host_ids or [],
                input_vars={
                    **run_options["input_vars"],
                    "execution_source": "scheduled_manual",
                    "scheduled_job_id": schedule.id,
                },
                worker_pool=schedule.worker_pool,
                triggered_by=request.user,
                trigger_type=WorkflowRun.TriggerType.SCHEDULED,
                timeout_seconds=run_options["timeout_seconds"],
                queue_timeout_seconds=run_options["queue_timeout_seconds"],
            )
        except InvalidTargetHosts:
            return api_error_response("定时任务包含无效或未启用的目标主机")
        JobEventLog.objects.create(
            workflow_run=run,
            event_type="workflow_dispatch_requested",
            message="Scheduled workflow run manually dispatched.",
            payload={"scheduled_job_id": schedule.id, "workflow_run_id": run.id},
        )
        schedule.last_run_at = timezone.now()
        schedule.last_workflow_run = run
        schedule.save(update_fields=["last_run_at", "last_workflow_run", "updated_at"])
        transaction.on_commit(lambda: enqueue_workflow_run(run.id))
        return api_ok_response(WorkflowRunSerializer(run).data)


class ReadOnlyHistoryViewSet(StandardModelViewSet):
    http_method_names = ["get", "head", "options"]


class NodeRunViewSet(ReadOnlyHistoryViewSet):
    http_method_names = ["get", "post", "head", "options"]
    queryset = NodeRun.objects.select_related(
        "workflow_run",
        "workflow_node",
        "command_version",
        "command_version__command",
    ).all()
    serializer_class = NodeRunSerializer
    ordering_fields = ("id", "status", "started_at", "finished_at")
    filterset_fields = ("workflow_run", "status", "workflow_node", "command_version")
    search_fields = ("failure_reason", "workflow_node__name", "workflow_node__node_key")

    @action(methods=["GET"], detail=True, url_path="host-results")
    def host_results(self, request, pk=None):
        node_run = self.get_object()
        serializer = HostRunResultSerializer(node_run.host_results.all(), many=True)
        return api_ok_response(serializer.data)

    @action(methods=["GET"], detail=True, url_path="attempts")
    def attempts(self, request, pk=None):
        node_run = self.get_object()
        return api_ok_response(
            NodeRunAttemptSerializer(node_run.attempts.all(), many=True).data
        )

    @action(methods=["POST"], detail=True, url_path="retry")
    def retry(self, request, pk=None):
        node_run = self.get_object()
        if node_run.status not in {NodeRun.Status.FAILED, NodeRun.Status.TIMEOUT}:
            return api_error_response("只有失败或超时节点可以重试")
        node_run.status = NodeRun.Status.PENDING
        node_run.failure_reason = ""
        node_run.finished_at = None
        node_run.save(
            update_fields=["status", "failure_reason", "finished_at", "updated_at"]
        )
        transaction.on_commit(
            lambda: enqueue_workflow_run(
                node_run.workflow_run_id, record_dispatch_task=False
            )
        )
        return api_ok_response(self.get_serializer(node_run).data)

    @action(methods=["POST"], detail=True, url_path="ignore")
    def ignore(self, request, pk=None):
        node_run = self.get_object()
        if node_run.status not in {NodeRun.Status.FAILED, NodeRun.Status.TIMEOUT}:
            return api_error_response("只有失败或超时节点可以忽略")
        node_run.status = NodeRun.Status.IGNORED
        node_run.save(update_fields=["status", "updated_at"])
        transaction.on_commit(
            lambda: enqueue_workflow_run(
                node_run.workflow_run_id, record_dispatch_task=False
            )
        )
        return api_ok_response(self.get_serializer(node_run).data)


class HostRunResultViewSet(ReadOnlyHistoryViewSet):
    queryset = HostRunResult.objects.select_related(
        "node_run", "node_run__workflow_run"
    ).all()
    serializer_class = HostRunResultSerializer
    ordering_fields = ("id", "hostname", "status", "started_at", "finished_at")
    filterset_fields = ("node_run", "status", "host_id")
    search_fields = ("hostname", "ip", "stdout", "stderr")


class JobEventLogViewSet(ReadOnlyHistoryViewSet):
    queryset = JobEventLog.objects.select_related("workflow_run", "node_run").all()
    serializer_class = JobEventLogSerializer
    ordering_fields = ("id", "created_at")
    filterset_fields = ("workflow_run", "node_run", "event_type", "host_id")
    search_fields = ("event_type", "message")


class SecurityRuleViewSet(StandardModelViewSet):
    queryset = SecurityRule.objects.all()
    serializer_class = SecurityRuleSerializer
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    ordering_fields = ("id", "blocked_count", "risk_level", "created_at")
    filterset_fields = ("enabled", "match_mode", "risk_level")
    search_fields = ("pattern", "description")

    @action(methods=["POST"], detail=True, url_path="toggle")
    def toggle(self, request, pk=None):
        rule = self.get_object()
        rule.enabled = not rule.enabled
        rule.save(update_fields=["enabled", "updated_at"])
        return api_ok_response(self.get_serializer(rule).data)


class CommandInterceptViewSet(ReadOnlyHistoryViewSet):
    queryset = CommandIntercept.objects.select_related("operator", "rule").all()
    serializer_class = CommandInterceptSerializer
    ordering_fields = ("id", "created_at")
    filterset_fields = ("risk_level", "rule")
    search_fields = ("command", "hit_pattern", "target_desc")


class SecurityStatsView(APIView):
    def get(self, request):
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return api_ok_response(
            {
                "ruleCount": SecurityRule.objects.filter(enabled=True).count(),
                "monthBlocked": CommandIntercept.objects.filter(
                    created_at__gte=month_start
                ).count(),
                "accidents": 0,
            }
        )


class GatewayViewSet(StandardModelViewSet):
    queryset = Gateway.objects.all()
    serializer_class = GatewaySerializer
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    ordering_fields = ("id", "name", "status", "created_at")
    filterset_fields = ("cloud", "status", "auth_type")
    search_fields = ("name", "address", "network")

    @action(methods=["POST"], detail=True, url_path="test")
    def test(self, request, pk=None):
        gateway = self.get_object()
        host, _, port = gateway.address.rpartition(":")
        if host and port.isdigit():
            target = (host, int(port))
        else:
            # 地址未携带端口时整体作为主机名，默认探测 22 端口
            target = (gateway.address, 22)
        reachable = False
        try:
            with socket.create_connection(target, timeout=3):
                reachable = True
        except (OSError, ValueError):
            reachable = False
        gateway.status = Gateway.Status.NORMAL if reachable else Gateway.Status.ABNORMAL
        gateway.last_tested_at = timezone.now()
        gateway.save(update_fields=["status", "last_tested_at", "updated_at"])
        if reachable:
            return api_ok_response(self.get_serializer(gateway).data)
        return api_error_response(
            message=f"网关「{gateway.name}」连接失败，请检查地址与网络",
        )


class PlaybookRunViewSet(StandardModelViewSet):
    http_method_names = ["post", "options"]
    queryset = WorkflowRun.objects.none()
    serializer_class = WorkflowRunSerializer

    def create(self, request, *args, **kwargs):
        serializer = PlaybookRunCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        create_domain_audit_event(
            actor=request.user,
            action="playbook_run.create",
            resource_type="workflow_run",
            resource_id=run.id,
            after={
                "status": run.status,
                "target_count": len(run.target_snapshot or []),
                **_workflow_run_audit_summary(run),
            },
            request=request,
        )
        JobEventLog.objects.create(
            workflow_run=run,
            event_type="workflow_dispatch_requested",
            message="Playbook workflow run dispatch requested.",
            payload={"workflow_run_id": run.id},
        )
        transaction.on_commit(lambda: enqueue_workflow_run(run.id))
        run.refresh_from_db()
        return api_ok_response(WorkflowRunSerializer(run).data)


class ModuleRunViewSet(StandardModelViewSet):
    http_method_names = ["post", "options"]
    queryset = WorkflowRun.objects.none()
    serializer_class = WorkflowRunSerializer

    def create(self, request, *args, **kwargs):
        serializer = ModuleRunCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        create_domain_audit_event(
            actor=request.user,
            action="module_run.create",
            resource_type="workflow_run",
            resource_id=run.id,
            after={
                "status": run.status,
                "target_count": len(run.target_snapshot or []),
                **_workflow_run_audit_summary(run),
            },
            request=request,
        )
        JobEventLog.objects.create(
            workflow_run=run,
            event_type="workflow_dispatch_requested",
            message="Module ad-hoc workflow run dispatch requested.",
            payload={"workflow_run_id": run.id},
        )
        transaction.on_commit(lambda: enqueue_workflow_run(run.id))
        run.refresh_from_db()
        return api_ok_response(WorkflowRunSerializer(run).data)


class DashboardStatsView(APIView):
    def get(self, request):
        now = timezone.now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        today_runs = WorkflowRun.objects.filter(
            run_domain=WorkflowRun.RunDomain.OPS,
            created_at__gte=day_start,
        )
        finished_today = today_runs.filter(
            status__in=[
                WorkflowRun.Status.SUCCESS,
                WorkflowRun.Status.FAILED,
                WorkflowRun.Status.TIMEOUT,
                WorkflowRun.Status.CANCELED,
            ]
        )
        success_count = finished_today.filter(status=WorkflowRun.Status.SUCCESS).count()
        finished_count = finished_today.count()
        avg_duration_ms = (
            finished_today.exclude(duration_ms=None).aggregate(avg=Avg("duration_ms"))[
                "avg"
            ]
            or 0
        )
        return api_ok_response(
            {
                "todayExecutions": today_runs.count(),
                "successRate": round(success_count / finished_count * 100, 1)
                if finished_count
                else 100.0,
                "avgResponseSeconds": round(avg_duration_ms / 1000, 1),
                "blockedCommands": CommandIntercept.objects.filter(
                    created_at__gte=month_start
                ).count(),
            }
        )


class DashboardHealthView(APIView):
    def get(self, request):
        from celery import current_app
        import redis

        broker_url = getattr(settings, "CELERY_BROKER_URL", "")
        queue_names = {"task", "ops", "ansible"}
        queue_names.update(
            WorkerPool.objects.filter(is_active=True)
            .exclude(queue_name="")
            .values_list("queue_name", flat=True)
        )
        queues = {name: None for name in sorted(queue_names)}
        redis_ok = False
        redis_error = ""
        try:
            client = redis.Redis.from_url(
                broker_url, socket_connect_timeout=1, socket_timeout=1
            )
            redis_ok = bool(client.ping())
            queues = {name: int(client.llen(name)) for name in queues}
        except Exception as exc:
            redis_error = str(exc)
        workers = {}
        active_queues = {}
        try:
            inspector = current_app.control.inspect(timeout=1)
            workers = inspector.ping() or {}
            active_queues = inspector.active_queues() or {}
        except Exception:
            workers = {}
            active_queues = {}
        queue_workers = {
            queue_name: sorted(
                node_name
                for node_name, worker_queues in active_queues.items()
                if any(
                    item.get("name") == queue_name
                    for item in (worker_queues or [])
                )
            )
            for queue_name in queues
        }
        channel_backend = str(
            (getattr(settings, "CHANNEL_LAYERS", {}).get("default") or {}).get(
                "BACKEND"
            )
            or ""
        )
        seven_days_ago = timezone.now() - timedelta(days=7)
        recent = WorkflowRun.objects.filter(
            run_domain=WorkflowRun.RunDomain.TASK,
            created_at__gte=seven_days_ago,
        )
        finished = recent.filter(
            status__in=[
                WorkflowRun.Status.SUCCESS,
                WorkflowRun.Status.FAILED,
                WorkflowRun.Status.TIMEOUT,
                WorkflowRun.Status.CANCELED,
            ]
        )
        finished_count = finished.count()
        success_count = finished.filter(status=WorkflowRun.Status.SUCCESS).count()
        return api_ok_response(
            {
                "redis": {"healthy": redis_ok, "error": redis_error},
                "workers": {
                    "healthy": bool(workers),
                    "count": len(workers),
                    "nodes": sorted(workers),
                    "queues": queue_workers,
                    "missingQueues": sorted(
                        name for name, nodes in queue_workers.items() if not nodes
                    ),
                },
                "queues": queues,
                "websocket": {
                    "healthy": bool(channel_backend),
                    "backend": channel_backend,
                },
                "sevenDay": {
                    "total": recent.count(),
                    "finished": finished_count,
                    "successRate": round(success_count * 100 / finished_count, 1)
                    if finished_count
                    else 100.0,
                },
                "checkedAt": timezone.now(),
            }
        )


class DashboardRecentView(APIView):
    def get(self, request):
        runs = WorkflowRun.objects.filter(
            run_domain=WorkflowRun.RunDomain.OPS,
        ).select_related(
            "workflow_version", "workflow_version__workflow", "triggered_by"
        )[:10]
        items = []
        for run in runs:
            input_vars = run.input_vars or {}
            name = (
                input_vars.get("playbook_name")
                or input_vars.get("name")
                or (
                    run.workflow_version.workflow.name
                    if run.workflow_version
                    else "Ansible task"
                )
            )
            items.append(
                {
                    "id": run.id,
                    "name": name,
                    "type": input_vars.get("execution_source") or run.trigger_type,
                    "target": f"{len(run.target_snapshot or [])}台主机",
                    "status": run.status,
                    "executor": run.triggered_by.username if run.triggered_by else "",
                    "time": run.created_at,
                }
            )
        return api_ok_response(items)


class EngineSettingsView(APIView):
    def get(self, request):
        return api_ok_response(get_engine_settings())

    def put(self, request):
        return api_ok_response(save_engine_settings(request.data or {}))


class NotifySettingsView(APIView):
    def get(self, request):
        return api_ok_response(get_notify_settings())

    def put(self, request):
        return api_ok_response(save_notify_settings(request.data or {}))

import asyncio
import os
from urllib.parse import parse_qs

import aiofiles
from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework_simplejwt.authentication import JWTAuthentication

from common.auth.rbac import verify_permission

from apps.jobs.models import NodeRun, WorkflowRun
from .constants import CELERY_LOG_MAGIC_MARK
from .utils import get_task_log_path


def normalize_terminal_line(data):
    """Normalize one file-log line for terminal cursor semantics."""
    has_line_ending = data.endswith((b"\r", b"\n"))
    content = data.rstrip(b"\r\n")
    return content + (b"\r\n" if has_line_ending else b"")


class TaskLogWebsocket(AsyncJsonWebsocketConsumer):
    disconnected = False

    @staticmethod
    def permission_path(workflow_run):
        prefix = (
            "ops"
            if workflow_run.run_domain == WorkflowRun.RunDomain.OPS
            else "tasks"
        )
        return f"/api/v1/{prefix}/runs/{workflow_run.id}/log"

    async def connect(self):
        self.disconnected = False
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            token = parse_qs(self.scope.get("query_string", b"").decode()).get(
                "token", [""]
            )[0]
            user = await self.authenticate_token(token)
            self.scope["user"] = user
        if user and user.is_authenticated:
            await self.accept()
        else:
            await self.close()

    @sync_to_async
    def authenticate_token(self, token):
        if not token:
            return AnonymousUser()
        try:
            authentication = JWTAuthentication()
            validated = authentication.get_validated_token(token)
            return authentication.get_user(validated)
        except Exception:
            return AnonymousUser()

    @sync_to_async
    def get_task_context(self, task_id):
        node_run = (
            NodeRun.objects.select_related("workflow_run")
            .filter(celery_task_id=task_id)
            .first()
        )
        if node_run:
            workflow_run = node_run.workflow_run
            return {
                "task_id": str(node_run.celery_task_id),
                "workflow_run_id": workflow_run.id,
                "node_run_id": node_run.id,
                "owner_id": workflow_run.triggered_by_id,
                "permission_path": self.permission_path(workflow_run),
            }
        workflow_run = WorkflowRun.objects.filter(celery_task_id=task_id).first()
        if not workflow_run:
            try:
                workflow_run = WorkflowRun.objects.filter(id=task_id).first()
            except (TypeError, ValueError, ValidationError):
                workflow_run = None
        if workflow_run:
            return {
                "task_id": str(workflow_run.celery_task_id or task_id),
                "workflow_run_id": workflow_run.id,
                "owner_id": workflow_run.triggered_by_id,
                "permission_path": self.permission_path(workflow_run),
            }
        return None

    @sync_to_async
    def can_view(self, user, task_context):
        if user.is_superuser or task_context["owner_id"] == user.id:
            return True
        allowed, _ = verify_permission(user, task_context["permission_path"], "GET")
        return allowed

    @sync_to_async
    def is_workflow_terminal(self, workflow_run_id):
        status = (
            WorkflowRun.objects.filter(id=workflow_run_id)
            .values_list(
                "status",
                flat=True,
            )
            .first()
        )
        return status in {
            WorkflowRun.Status.SUCCESS,
            WorkflowRun.Status.FAILED,
            WorkflowRun.Status.TIMEOUT,
            WorkflowRun.Status.CANCELED,
        }

    async def receive_json(self, content, **kwargs):
        task_id = content.get("task")
        task_context = await self.get_task_context(task_id)
        if not task_context:
            await self.send_json({"message": "Task not found", "task": task_id})
            return
        if not await self.can_view(self.scope["user"], task_context):
            await self.send_json({"message": "No permission", "task": task_id})
            return
        await self.send_task_log(task_context)

    async def send_task_log(self, task_context):
        task_id = task_context["task_id"]
        workflow_run_id = task_context["workflow_run_id"]
        try:
            log_path = get_task_log_path(task_id)
        except ValueError:
            await self.send_json(
                {
                    "event": "end",
                    "message": "Task has no Celery log id",
                    "task": task_id,
                }
            )
            return
        timeout = 0
        while not os.path.exists(log_path) and not self.disconnected:
            if await self.is_workflow_terminal(workflow_run_id):
                await self.send_json(
                    {
                        "event": "end",
                        "message": "Task log was not created",
                        "task": task_id,
                    }
                )
                return
            if timeout >= 60:
                await self.send_json(
                    {
                        "event": "end",
                        "message": "Task log was not found",
                        "task": task_id,
                    }
                )
                return
            timeout += 0.5
            await asyncio.sleep(0.5)

        async with aiofiles.open(log_path, "rb") as task_log:
            terminal_idle_checks = 0
            while not self.disconnected:
                data = await task_log.readline()
                if data:
                    terminal_idle_checks = 0
                    is_end = CELERY_LOG_MAGIC_MARK in data
                    data = data.replace(CELERY_LOG_MAGIC_MARK, b"")
                    if data:
                        data = normalize_terminal_line(data)
                        await self.send_json(
                            {
                                "message": data.decode(errors="replace"),
                                "task": task_id,
                            }
                        )
                    if is_end:
                        await self.send_json(
                            {"event": "end", "task": task_id, "message": ""}
                        )
                        return
                elif await self.is_workflow_terminal(workflow_run_id):
                    terminal_idle_checks += 1
                    if terminal_idle_checks >= 5:
                        await self.send_json(
                            {"event": "end", "task": task_id, "message": ""}
                        )
                        return
                await asyncio.sleep(0.2)

    async def disconnect(self, close_code):
        self.disconnected = True

import asyncio
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.contrib.auth import get_user_model

from apps.jobs.models import WorkflowRun
from .access import can_view_run
from .tickets import consume_ticket


class RunEventsConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.run_id = None
        self.user_id = None
        self.subscription_timeout = None
        origin = (
            dict(self.scope.get("headers", []))
            .get(b"origin", b"")
            .decode("utf-8", errors="replace")
        )
        if self.scope.get("query_string") or origin not in getattr(
            settings, "JOBS_REALTIME_ALLOWED_ORIGINS", []
        ):
            await self.close(code=4403)
            return
        await self.accept()
        self.subscription_timeout = asyncio.create_task(self.close_unsubscribed())

    async def close_unsubscribed(self):
        await asyncio.sleep(10)
        if self.run_id is None:
            await self.close(code=4401)

    @database_sync_to_async
    def authorize_ticket(self, ticket, run_id):
        user_id = consume_ticket(ticket, run_id=run_id)
        user = get_user_model().objects.filter(pk=user_id).first() if user_id else None
        run = WorkflowRun.objects.filter(pk=run_id).first()
        return user_id if run and can_view_run(user, run) else None

    @database_sync_to_async
    def still_authorized(self):
        user = get_user_model().objects.filter(pk=self.user_id).first()
        run = WorkflowRun.objects.filter(pk=self.run_id).first()
        return bool(run and can_view_run(user, run))

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        if text_data is None or len(text_data) > 4096:
            await self.close(code=4400)
            return
        try:
            await super().receive(text_data=text_data, **kwargs)
        except json.JSONDecodeError:
            await self.send_json({"type": "error", "code": "invalid_subscription"})

    async def receive_json(self, content, **kwargs):
        if (
            not isinstance(content, dict)
            or content.get("type") != "subscribe"
            or self.run_id is not None
        ):
            await self.send_json({"type": "error", "code": "invalid_subscription"})
            return
        run_id = content.get("run_id")
        if type(run_id) is not int or run_id <= 0:
            await self.send_json({"type": "error", "code": "invalid_subscription"})
            return
        try:
            user_id = await self.authorize_ticket(content.get("ticket"), run_id)
            if not user_id:
                await self.send_json({"type": "error", "code": "forbidden"})
                return
            if self.channel_layer is None:
                raise RuntimeError("Channel layer is not configured")
            await self.channel_layer.group_add(f"jobs.run.{run_id}", self.channel_name)
        except Exception:
            await self.send_json({"type": "error", "code": "realtime_unavailable"})
            return
        self.run_id, self.user_id = run_id, user_id
        if self.subscription_timeout:
            self.subscription_timeout.cancel()
        await self.send_json({"type": "subscribed", "run_id": run_id})

    async def events_available(self, event):
        if event.get("run_id") != self.run_id:
            return
        if not await self.still_authorized():
            await self.close(code=4403)
            return
        await self.send_json(
            {
                "type": "events_available",
                "run_id": self.run_id,
                "sequence": event["sequence"],
            }
        )

    async def disconnect(self, code):
        if self.subscription_timeout:
            self.subscription_timeout.cancel()
        if self.run_id and self.channel_layer:
            try:
                await self.channel_layer.group_discard(
                    f"jobs.run.{self.run_id}", self.channel_name
                )
            except Exception:
                pass

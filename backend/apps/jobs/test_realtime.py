from types import SimpleNamespace
import time as time_mod
from unittest.mock import patch

import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.db import transaction
from django.test import override_settings

import apps.jobs.realtime.publisher as publisher
from apps.jobs.events import append_run_event
from apps.jobs.models import JobEventLog, WorkerPool, WorkflowRun
from apps.jobs.realtime.consumer import RunEventsConsumer
from apps.jobs.realtime.routing import websocket_urlpatterns
from apps.jobs.realtime.tickets import issue_ticket, consume_ticket, CONSUME_SCRIPT


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.time = 0

    def set(self, key, value, *, ex, nx):
        assert ex == 60 and nx is True
        self.values[key] = (value, self.time + ex)
        return True

    def eval(self, script, keys, key):
        assert script == CONSUME_SCRIPT and keys == 1
        value = self.values.pop(key, None)
        return value[0] if value and value[1] > self.time else None


@pytest.fixture
def ticket_store():
    store = FakeRedis()
    with patch("apps.jobs.realtime.tickets.redis_client", return_value=store):
        yield store


def test_tickets_are_single_use_bound_and_expiring(ticket_store):
    ticket = issue_ticket(user_id=1, run_id=2)
    assert consume_ticket(ticket, run_id=2) == 1
    assert consume_ticket(ticket, run_id=2) is None
    wrong_run = issue_ticket(user_id=1, run_id=2)
    assert consume_ticket(wrong_run, run_id=3) is None
    assert consume_ticket(wrong_run, run_id=2) is None
    expired = issue_ticket(user_id=1, run_id=2)
    ticket_store.time += 61
    assert consume_ticket(expired, run_id=2) is None


@pytest.fixture
def run(user):
    user.is_superuser = True
    user.save()
    pool = WorkerPool.objects.create(
        code="realtime", name="Realtime", queue_name="test"
    )
    return WorkflowRun.objects.create(worker_pool=pool, triggered_by=user)


@pytest.mark.django_db(transaction=True)
def test_notify_only_after_commit(run):
    with patch("apps.jobs.realtime.publisher.publish_events_available") as notify:
        with transaction.atomic():
            log = append_run_event(
                run_id=run.id, event_key="event", event={"event_type": "test"}
            )
            notify.assert_not_called()
        notify.assert_called_once_with(run.id, log.sequence)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("layer", [None, RuntimeError("transport unavailable")])
def test_transport_failure_cannot_rollback_events(run, layer):
    with patch(
        "apps.jobs.realtime.publisher.get_channel_layer",
        side_effect=layer if isinstance(layer, Exception) else None,
        return_value=layer,
    ):
        append_run_event(run_id=run.id, event_key="event", event={"event_type": "test"})
    assert JobEventLog.objects.filter(workflow_run=run).count() == 1


@pytest.mark.django_db(transaction=True)
def test_websocket_subscription_isolated_and_ticket_not_reusable(
    run, user, ticket_store
):
    ticket = issue_ticket(user_id=user.id, run_id=run.id)

    async def scenario():
        app = URLRouter(websocket_urlpatterns)
        socket = WebsocketCommunicator(
            app, "/ws/jobs/runs/", headers=[(b"origin", b"http://localhost:9527")]
        )
        assert (await socket.connect())[0]
        await socket.send_json_to(
            {"type": "subscribe", "run_id": run.id, "ticket": ticket}
        )
        assert await socket.receive_json_from() == {
            "type": "subscribed",
            "run_id": run.id,
        }
        layer = get_channel_layer()
        await layer.group_send(
            f"jobs.run.{run.id + 1}",
            {"type": "events.available", "run_id": run.id + 1, "sequence": 1},
        )
        assert await socket.receive_nothing(timeout=0.05)
        await layer.group_send(
            f"jobs.run.{run.id}",
            {"type": "events.available", "run_id": run.id, "sequence": 2},
        )
        assert await socket.receive_json_from() == {
            "type": "events_available",
            "run_id": run.id,
            "sequence": 2,
        }
        second = WebsocketCommunicator(
            app, "/ws/jobs/runs/", headers=[(b"origin", b"http://localhost:9527")]
        )
        assert (await second.connect())[0]
        await second.send_json_to(
            {"type": "subscribe", "run_id": run.id, "ticket": ticket}
        )
        assert (await second.receive_json_from())["code"] == "forbidden"
        await second.disconnect()
        await socket.disconnect()

    with override_settings(JOBS_REALTIME_ALLOWED_ORIGINS=["http://localhost:9527"]):
        async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "path,origin",
    [
        ("/ws/jobs/runs/", b"http://untrusted.invalid"),
        ("/ws/jobs/runs/?token=jwt", b"http://localhost:9527"),
    ],
)
def test_origin_and_query_tokens_are_rejected(path, origin):
    async def scenario():
        socket = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns), path, headers=[(b"origin", origin)]
        )
        assert (await socket.connect())[0] is False
        await socket.disconnect()

    with override_settings(JOBS_REALTIME_ALLOWED_ORIGINS=["http://localhost:9527"]):
        async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_ticket_cannot_subscribe_as_another_owner(run, user, ticket_store):
    user.is_superuser = False
    user.save()
    run.triggered_by = None
    run.save()
    ticket = issue_ticket(user_id=user.id, run_id=run.id)

    async def scenario():
        socket = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns),
            "/ws/jobs/runs/",
            headers=[(b"origin", b"http://localhost:9527")],
        )
        assert (await socket.connect())[0]
        await socket.send_json_to(
            {"type": "subscribe", "run_id": run.id, "ticket": ticket}
        )
        assert (await socket.receive_json_from())["code"] == "forbidden"
        await socket.disconnect()

    async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_rollback_does_not_notify(run):
    with patch("apps.jobs.realtime.publisher.publish_events_available") as notify:
        with pytest.raises(RuntimeError):
            with transaction.atomic():
                append_run_event(
                    run_id=run.id, event_key="rolled-back", event={"event_type": "test"}
                )
                raise RuntimeError("rollback")
        notify.assert_not_called()
    assert not JobEventLog.objects.filter(workflow_run=run).exists()


@pytest.mark.django_db
def test_ticket_endpoint_and_redis_outage_keep_rest_available(run, user, ticket_store):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user)
    response = client.post(f"/api/v1/tasks/runs/{run.id}/realtime-ticket")
    assert response.status_code == 200
    assert response.data["data"]["expires_in"] == 60
    assert consume_ticket(response.data["data"]["ticket"], run_id=run.id) == user.id
    with patch(
        "apps.jobs.realtime.tickets.redis_client",
        side_effect=ConnectionError("test outage"),
    ):
        assert (
            client.post(f"/api/v1/tasks/runs/{run.id}/realtime-ticket").status_code
            == 503
        )
        assert client.get(f"/api/v1/tasks/runs/{run.id}/events").status_code == 200


class GateCache:
    """可控的 NX 语义：仅首次 add 成功，之后全部被抑制。"""

    def __init__(self):
        self.gate_open = True

    def add(self, key, value, timeout):
        if self.gate_open:
            self.gate_open = False
            return True
        return False


@pytest.mark.django_db
def test_notifications_are_coalesced_per_run(run):
    """窗口内多条事件合并：前沿立即发一条，静默结束后补发最新 sequence。"""
    sends = []
    with patch.object(publisher, "cache", GateCache()), patch.object(
        publisher, "DEBOUNCE_SECONDS", 0.05
    ), patch.object(
        publisher, "_send", side_effect=lambda run_id, seq: sends.append((run_id, seq))
    ):
        publisher.publish_events_available(run.id, 1)
        publisher.publish_events_available(run.id, 2)
        publisher.publish_events_available(run.id, 3)
        assert sends == [(run.id, 1)]
        time_mod.sleep(0.3)
        assert sends == [(run.id, 1), (run.id, 3)]


@pytest.mark.django_db
def test_notification_leading_edge_suppresses_trailing(run):
    """静默期内再次前沿通知会取消尾部补发，避免冗余。"""
    sends = []
    gate = GateCache()
    with patch.object(publisher, "cache", gate), patch.object(
        publisher, "DEBOUNCE_SECONDS", 0.05
    ), patch.object(
        publisher, "_send", side_effect=lambda run_id, seq: sends.append((run_id, seq))
    ):
        publisher.publish_events_available(run.id, 1)
        publisher.publish_events_available(run.id, 2)
        gate.gate_open = True
        publisher.publish_events_available(run.id, 3)
        time_mod.sleep(0.2)
        assert sends == [(run.id, 1), (run.id, 3)]


@pytest.mark.django_db
def test_notification_cache_outage_degrades_to_per_event(run):
    class BrokenCache:
        def add(self, *args):
            raise ConnectionError("cache outage")

    sends = []
    with patch.object(publisher, "cache", BrokenCache()), patch.object(
        publisher, "_send", side_effect=lambda run_id, seq: sends.append((run_id, seq))
    ):
        publisher.publish_events_available(run.id, 1)
        publisher.publish_events_available(run.id, 2)
    assert sends == [(run.id, 1), (run.id, 2)]


@pytest.mark.django_db(transaction=True)
def test_consumer_reuses_authorization_within_ttl(run, user, ticket_store):
    """TTL 内的多条通知不重复触发数据库鉴权查询。"""
    calls = {"n": 0}
    original = RunEventsConsumer.still_authorized

    async def counting(self):
        calls["n"] += 1
        return await original(self)

    ticket = issue_ticket(user_id=user.id, run_id=run.id)

    async def scenario():
        socket = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns),
            "/ws/jobs/runs/",
            headers=[(b"origin", b"http://localhost:9527")],
        )
        assert (await socket.connect())[0]
        await socket.send_json_to(
            {"type": "subscribe", "run_id": run.id, "ticket": ticket}
        )
        assert await socket.receive_json_from() == {
            "type": "subscribed",
            "run_id": run.id,
        }
        layer = get_channel_layer()
        await layer.group_send(
            f"jobs.run.{run.id}",
            {"type": "events.available", "run_id": run.id, "sequence": 1},
        )
        assert await socket.receive_json_from() == {
            "type": "events_available",
            "run_id": run.id,
            "sequence": 1,
        }
        await layer.group_send(
            f"jobs.run.{run.id}",
            {"type": "events.available", "run_id": run.id, "sequence": 2},
        )
        assert await socket.receive_json_from() == {
            "type": "events_available",
            "run_id": run.id,
            "sequence": 2,
        }
        await socket.disconnect()
        assert calls["n"] == 0

    with override_settings(JOBS_REALTIME_ALLOWED_ORIGINS=["http://localhost:9527"]):
        with patch.object(RunEventsConsumer, "still_authorized", counting):
            async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_revoked_permission_closes_connection(run, user, ticket_store):
    """TTL 到期后复核失败（权限被回收）时主动断开 4403。"""
    ticket = issue_ticket(user_id=user.id, run_id=run.id)

    async def scenario():
        socket = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns),
            "/ws/jobs/runs/",
            headers=[(b"origin", b"http://localhost:9527")],
        )
        assert (await socket.connect())[0]
        await socket.send_json_to(
            {"type": "subscribe", "run_id": run.id, "ticket": ticket}
        )
        assert await socket.receive_json_from() == {
            "type": "subscribed",
            "run_id": run.id,
        }
        await get_channel_layer().group_send(
            f"jobs.run.{run.id}",
            {"type": "events.available", "run_id": run.id, "sequence": 1},
        )
        output = await socket.receive_output()
        assert output["type"] == "websocket.close"
        assert output["code"] == 4403

    with override_settings(JOBS_REALTIME_ALLOWED_ORIGINS=["http://localhost:9527"]):
        with patch.object(
            RunEventsConsumer, "still_authorized", return_value=False
        ), patch("apps.jobs.realtime.consumer.AUTH_RECHECK_SECONDS", 0.0):
            async_to_sync(scenario)()

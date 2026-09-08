"""Single-use user/run tickets, consumed atomically in Redis."""

import hashlib
import json
import secrets

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from redis import Redis

TTL_SECONDS = 60
CONSUME_SCRIPT = "local v = redis.call('GET', KEYS[1]); if v then redis.call('DEL', KEYS[1]); end; return v"


def redis_client():
    url = getattr(settings, "JOBS_REALTIME_REDIS_URL", "")
    if not url:
        raise ImproperlyConfigured("Realtime ticket Redis is not configured")
    return Redis.from_url(
        url, socket_connect_timeout=1, socket_timeout=1, decode_responses=True
    )


def _key(ticket):
    return "jobs:ticket:" + hashlib.sha256(ticket.encode()).hexdigest()


def issue_ticket(*, user_id, run_id):
    client = redis_client()
    for _ in range(3):
        ticket = secrets.token_urlsafe(32)
        if client.set(
            _key(ticket),
            json.dumps({"user_id": user_id, "run_id": run_id}),
            ex=TTL_SECONDS,
            nx=True,
        ):
            return ticket
    raise RuntimeError("Could not allocate realtime ticket")


def consume_ticket(ticket, *, run_id):
    if not isinstance(ticket, str) or not 40 <= len(ticket) <= 128:
        return None
    value = redis_client().eval(CONSUME_SCRIPT, 1, _key(ticket))
    if not value:
        return None
    payload = json.loads(value)
    if payload.get("run_id") != run_id or type(payload.get("user_id")) is not int:
        return None
    return payload["user_id"]

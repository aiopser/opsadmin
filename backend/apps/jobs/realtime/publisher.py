"""运行事件实时通知。

通知只是「有新事件，请补拉」的提示，数据完整性由 REST 游标补拉保证，
因此同一 run 的事件可以合并：前沿立即发一条，窗口内后续事件静默，
静默结束后补发最新 sequence 一条（压测单 run 可达 50+ eps，逐条
group_send 会压垮 channel layer 并造成通知积压丢失）。
"""

import asyncio
import logging
import threading

from channels.layers import get_channel_layer
from django.core.cache import cache

logger = logging.getLogger(__name__)

# 同一 run 的通知合并窗口（秒）。
DEBOUNCE_SECONDS = 1

_notify_lock = threading.Lock()
_pending_sequences: dict = {}
_trailing_timers: dict = {}

_sender_loop: asyncio.AbstractEventLoop = None
_sender_loop_lock = threading.Lock()


def _get_sender_loop():
    """独立的常驻事件循环：group_send 不再与发布线程共享主循环而串行排队。"""
    global _sender_loop
    with _sender_loop_lock:
        if _sender_loop is None or _sender_loop.is_closed():
            _sender_loop = asyncio.new_event_loop()
            threading.Thread(
                target=_sender_loop.run_forever,
                name="jobs-realtime-notify",
                daemon=True,
            ).start()
        return _sender_loop


def _log_send_failure(future):
    try:
        exc = future.exception()
    except Exception:  # pragma: no cover - 回调自身异常
        return
    if exc is not None:
        logger.warning("Run event notification unavailable: %s", type(exc).__name__)


def _send(run_id, sequence):
    try:
        layer = get_channel_layer()
        if layer is None:
            return
        future = asyncio.run_coroutine_threadsafe(
            layer.group_send(
                f"jobs.run.{run_id}",
                {"type": "events.available", "run_id": run_id, "sequence": sequence},
            ),
            _get_sender_loop(),
        )
        future.add_done_callback(_log_send_failure)
    except Exception as exc:
        logger.warning("Run event notification unavailable: %s", type(exc).__name__)


def _flush_trailing(run_id):
    with _notify_lock:
        _trailing_timers.pop(run_id, None)
        sequence = _pending_sequences.pop(run_id, None)
    if sequence is not None:
        _send(run_id, sequence)


def _suppress(run_id, sequence):
    with _notify_lock:
        previous = _pending_sequences.get(run_id)
        _pending_sequences[run_id] = max(sequence, previous or 0)
        if run_id in _trailing_timers:
            return
        timer = threading.Timer(DEBOUNCE_SECONDS, _flush_trailing, args=(run_id,))
        timer.daemon = True
        _trailing_timers[run_id] = timer
    timer.start()


def publish_events_available(run_id, sequence):
    try:
        notified = cache.add(f"jobs:rt:notify:{run_id}", sequence, DEBOUNCE_SECONDS)
    except Exception:
        notified = True  # 缓存不可用时退化为逐条通知
    if notified:
        with _notify_lock:
            timer = _trailing_timers.pop(run_id, None)
            _pending_sequences.pop(run_id, None)
        if timer:
            timer.cancel()
        _send(run_id, sequence)
    else:
        _suppress(run_id, sequence)

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def publish_events_available(run_id, sequence):
    try:
        layer = get_channel_layer()
        if layer is not None:
            async_to_sync(layer.group_send)(
                f"jobs.run.{run_id}",
                {"type": "events.available", "run_id": run_id, "sequence": sequence},
            )
    except Exception as exc:
        logger.warning("Run event notification unavailable: %s", type(exc).__name__)

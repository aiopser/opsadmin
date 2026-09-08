"""Bounded immutable output chunks stored through the configured shared storage."""

import logging
import re
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.db import transaction
from django.db.models import Sum

from common.redaction import redact_text
from .models import RunLogChunk, WorkflowRun

logger = logging.getLogger(__name__)


def _validate_name(storage, run_id: int, name: str) -> str:
    if not re.fullmatch(rf"job-logs/run-{run_id}/[0-9]+-[a-f0-9]{{32}}\.log", name):
        raise SuspiciousFileOperation("Invalid log artifact path")
    if hasattr(storage, "location"):
        if (
            not Path(storage.path(name))
            .resolve()
            .is_relative_to(Path(storage.location).resolve())
        ):
            raise SuspiciousFileOperation("Log artifact escaped its storage root")
    return name


@transaction.atomic
def archive_stdout(*, run_id: int, sequence: int, text: str):
    WorkflowRun.objects.select_for_update().get(pk=run_id)
    existing = RunLogChunk.objects.filter(
        workflow_run_id=run_id, sequence=sequence
    ).first()
    if existing or not text:
        return existing
    limit = max(int(settings.JOBS_LOG_MAX_BYTES), 1)
    used = (
        RunLogChunk.objects.filter(workflow_run_id=run_id).aggregate(
            total=Sum("byte_count")
        )["total"]
        or 0
    )
    remaining = max(limit - used, 0)
    if not remaining:
        RunLogChunk.objects.filter(workflow_run_id=run_id).update(truncated=True)
        return None
    # Limit before encoding, so an arbitrarily large callback cannot allocate an unbounded byte buffer.
    safe = redact_text(text)
    raw = safe[:remaining].encode("utf-8")
    truncated = len(safe) > remaining or len(raw) > remaining
    if truncated:
        clipped = raw[:remaining].decode("utf-8", errors="ignore")
        clipped = re.sub(r"\x1b\[[0-?]*[ -/]*$", "", clipped)
        raw = clipped.encode("utf-8")
    storage = storages["job_logs"]
    name = f"job-logs/run-{run_id}/{sequence}-{uuid4().hex}.log"
    name = storage.save(name, ContentFile(raw), max_length=256)
    _validate_name(storage, run_id, name)
    try:
        return RunLogChunk.objects.create(
            workflow_run_id=run_id,
            sequence=sequence,
            storage_name=name,
            byte_count=len(raw),
            truncated=truncated,
        )
    except Exception:
        storage.delete(name)
        raise


def archive_event_stdout(run_id: int, sequence: int, event: dict) -> None:
    if event.get("no_log"):
        return
    result = event.get("result") or {}
    parts = [str(result[key]) for key in ("stdout", "stderr", "msg") if result.get(key)]
    if not parts:
        return
    try:
        text = "\n".join(parts)
        if not text.endswith("\n"):
            text += "\n"
        archive_stdout(run_id=run_id, sequence=sequence, text=text)
    except Exception as exc:
        logger.warning("Run output archive unavailable: %s", type(exc).__name__)


def iter_run_stdout(run_id: int, *, block_size: int = 65536) -> Iterator[bytes]:
    if not 1 <= block_size <= 65536:
        raise ValueError("Invalid log block size")
    storage = storages["job_logs"]
    for chunk in (
        RunLogChunk.objects.filter(workflow_run_id=run_id)
        .order_by("sequence")
        .iterator(chunk_size=100)
    ):
        name = _validate_name(storage, run_id, chunk.storage_name)
        with storage.open(name, "rb") as stream:
            while data := stream.read(block_size):
                yield data

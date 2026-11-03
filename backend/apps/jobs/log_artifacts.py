"""Bounded immutable output chunks stored through the configured shared storage."""

import logging
import re
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.db.models import F, Q, Sum
from django.utils import timezone
from django.utils.module_loading import import_string

from apps.cmdb.crypto import decrypt_secret, encrypt_secret
from common.redaction import redact_text
from .models import JobEventLog, RunLogArchiveRequest, RunLogChunk, WorkflowRun

logger = logging.getLogger(__name__)

RECOVER_BATCH_SIZE = 100
PENDING_RETRY_AFTER_SECONDS = 600


def job_log_storage():
    """Return the dedicated run-log storage from STORAGES["job_logs"].

    Works on Django 3.2 (where STORAGES is a project setting) and stays
    compatible once the framework adopts STORAGES natively (4.2+).
    """
    config = (getattr(settings, "STORAGES", None) or {}).get("job_logs")
    if not config:
        return default_storage
    return import_string(config["BACKEND"])(**(config.get("OPTIONS") or {}))


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


def _mark_chunk(run_id: int, sequence: int, error: str) -> None:
    """Persist a durable FAILED state so the recovery sweep retries idempotently."""
    RunLogChunk.objects.filter(workflow_run_id=run_id, sequence=sequence).update(
        status=RunLogChunk.Status.FAILED,
        last_error=str(error)[:255],
        updated_at=timezone.now(),
    )


@transaction.atomic
def _reserve_chunk(run_id: int, sequence: int, text: str):
    """Reserve capacity and stage a PENDING row in a short DB-only transaction.

    Storage I/O stays outside so a slow backend never extends the run-row lock.
    Returns (chunk, raw, truncated); chunk is None when the run is at capacity.
    """
    WorkflowRun.objects.select_for_update().get(pk=run_id)
    existing = RunLogChunk.objects.filter(
        workflow_run_id=run_id, sequence=sequence
    ).first()
    if existing and existing.status == RunLogChunk.Status.ARCHIVED:
        return existing, b"", False
    if not text:
        return existing, b"", False
    limit = max(int(settings.JOBS_LOG_MAX_BYTES), 1)
    used = (
        RunLogChunk.objects.filter(workflow_run_id=run_id).aggregate(
            total=Sum("byte_count")
        )["total"]
        or 0
    )
    # PENDING/FAILED rows still hold reserved bytes; recycle them on retry.
    remaining = max(limit - used, 0)
    if existing:
        remaining += existing.byte_count
    if not remaining:
        RunLogChunk.objects.filter(workflow_run_id=run_id).update(truncated=True)
        return None, b"", False
    # Limit before encoding, so an arbitrarily large callback cannot allocate an unbounded byte buffer.
    safe = redact_text(text)
    raw = safe[:remaining].encode("utf-8")
    truncated = len(safe) > remaining or len(raw) > remaining
    if truncated:
        clipped = raw[:remaining].decode("utf-8", errors="ignore")
        clipped = re.sub(r"\x1b\[[0-?]*[ -/]*$", "", clipped)
        raw = clipped.encode("utf-8")
    if existing:
        existing.byte_count = len(raw)
        existing.status = RunLogChunk.Status.PENDING
        existing.last_error = ""
        existing.save(
            update_fields=["byte_count", "status", "last_error", "updated_at"]
        )
        return existing, raw, truncated
    chunk = RunLogChunk.objects.create(
        workflow_run_id=run_id,
        sequence=sequence,
        byte_count=len(raw),
        status=RunLogChunk.Status.PENDING,
    )
    return chunk, raw, truncated


def archive_stdout(*, run_id: int, sequence: int, text: str):
    chunk, raw, truncated = _reserve_chunk(run_id=run_id, sequence=sequence, text=text)
    if chunk is None:
        return None
    if not raw:
        return chunk
    storage = job_log_storage()
    name = f"job-logs/run-{run_id}/{sequence}-{uuid4().hex}.log"
    try:
        name = storage.save(name, ContentFile(raw), max_length=256)
        _validate_name(storage, run_id, name)
    except Exception as exc:
        _mark_chunk(run_id, sequence, f"storage write failed: {type(exc).__name__}")
        raise
    try:
        chunk.storage_name = name
        chunk.byte_count = len(raw)
        chunk.truncated = truncated
        chunk.status = RunLogChunk.Status.ARCHIVED
        chunk.last_error = ""
        chunk.save(
            update_fields=[
                "storage_name",
                "byte_count",
                "truncated",
                "status",
                "last_error",
                "updated_at",
            ]
        )
    except Exception:
        storage.delete(name)
        _mark_chunk(run_id, sequence, "database finalize failed")
        raise
    return chunk


def queue_event_stdout_archive(run_id: int, sequence: int, event: dict) -> None:
    """Stage redacted output inside the caller's event transaction.

    加密内容与字节预留在事件事务内一并提交，落盘交给 Celery worker，
    事件生产者不做存储 I/O。字节预算在这里按“已预留 + 已落盘”软性裁剪，
    最终以 _reserve_chunk 的落盘复核为准。
    """
    if event.get("no_log"):
        return
    result = event.get("result") or {}
    parts = [str(result[key]) for key in ("stdout", "stderr", "msg") if result.get(key)]
    if not parts:
        return
    requests = RunLogArchiveRequest.objects.filter(workflow_run_id=run_id)
    if requests.filter(sequence=sequence).exists():
        return
    reserved = requests.aggregate(total=Sum("reserved_bytes"))["total"] or 0
    stored = (
        RunLogChunk.objects.filter(workflow_run_id=run_id)
        .exclude(sequence__in=requests.values("sequence"))
        .aggregate(total=Sum("byte_count"))["total"]
        or 0
    )
    remaining = max(int(settings.JOBS_LOG_MAX_BYTES) - reserved - stored, 0)
    if not remaining:
        RunLogChunk.objects.filter(workflow_run_id=run_id).update(truncated=True)
        return
    text = redact_text("\n".join(parts))
    if not text.endswith("\n"):
        text += "\n"
    raw = text[:remaining].encode("utf-8")
    truncated = len(text) > remaining or len(raw) > remaining
    text = raw[:remaining].decode("utf-8", errors="ignore")
    encrypted = encrypt_secret(text)
    try:
        # savepoint：唯一约束兜底并发，撞车说明该 sequence 已入队
        with transaction.atomic():
            request = RunLogArchiveRequest.objects.create(
                workflow_run_id=run_id,
                sequence=sequence,
                content_encrypted=encrypted,
                reserved_bytes=len(text.encode("utf-8")),
                content_truncated=truncated,
            )
    except IntegrityError:
        return
    transaction.on_commit(
        lambda request_id=request.id: _publish_archive_request(request_id)
    )


def _publish_archive_request(request_id: int) -> None:
    from apps.jobs.tasks import archive_pending_run_logs

    try:
        archive_pending_run_logs.delay(request_id)
    except Exception as exc:
        logger.warning("Run output archive dispatch unavailable: %s", type(exc).__name__)


def process_archive_request(request_id: int) -> bool:
    now = timezone.now()
    claimed = RunLogArchiveRequest.objects.filter(
        pk=request_id,
        status=RunLogArchiveRequest.Status.PENDING,
        next_attempt_at__lte=now,
    ).update(status=RunLogArchiveRequest.Status.PROCESSING, updated_at=now)
    if not claimed:
        return False
    request = RunLogArchiveRequest.objects.get(pk=request_id)
    try:
        chunk = archive_stdout(
            run_id=request.workflow_run_id,
            sequence=request.sequence,
            text=decrypt_secret(request.content_encrypted),
        )
        if chunk and request.content_truncated:
            RunLogChunk.objects.filter(pk=chunk.id).update(truncated=True)
    except Exception as exc:
        retries = request.retry_count + 1
        RunLogArchiveRequest.objects.filter(
            pk=request.id, status=RunLogArchiveRequest.Status.PROCESSING, updated_at=now
        ).update(
            status=(
                RunLogArchiveRequest.Status.FAILED
                if retries >= 8
                else RunLogArchiveRequest.Status.PENDING
            ),
            retry_count=retries,
            next_attempt_at=now + timedelta(seconds=min(2**retries, 300)),
            last_error_type=type(exc).__name__[:128],
            updated_at=timezone.now(),
        )
        logger.warning("Run output archive unavailable: %s", type(exc).__name__)
        return False
    RunLogArchiveRequest.objects.filter(
        pk=request.id, status=RunLogArchiveRequest.Status.PROCESSING, updated_at=now
    ).update(
        status=RunLogArchiveRequest.Status.STORED,
        content_encrypted="",
        last_error_type="",
        updated_at=timezone.now(),
    )
    return True


def recover_pending_archives(now=None, limit=RECOVER_BATCH_SIZE):
    """Compensate abandoned archive requests: reset stale claims, drain due rows."""
    now = now or timezone.now()
    stale_processing = RunLogArchiveRequest.objects.filter(
        status=RunLogArchiveRequest.Status.PROCESSING,
        updated_at__lt=now - timedelta(minutes=5),
    )
    stale_processing.filter(retry_count__gte=7).update(
        status=RunLogArchiveRequest.Status.FAILED,
        retry_count=F("retry_count") + 1,
        last_error_type="WorkerLost",
    )
    stale_processing.filter(retry_count__lt=7).update(
        status=RunLogArchiveRequest.Status.PENDING,
        retry_count=F("retry_count") + 1,
        next_attempt_at=now,
        last_error_type="WorkerLost",
    )
    ids = list(
        RunLogArchiveRequest.objects.filter(
            status=RunLogArchiveRequest.Status.PENDING,
            next_attempt_at__lte=now,
        )
        .order_by("next_attempt_at", "id")
        .values_list("id", flat=True)[:limit]
    )
    return sum(int(process_archive_request(request_id)) for request_id in ids)


def rearchive_failed_chunks(now=None):
    """Rebuild output text from persisted events and retry failed/stuck writes."""
    now = now or timezone.now()
    retry_before = now - timedelta(seconds=PENDING_RETRY_AFTER_SECONDS)
    stale = list(
        RunLogChunk.objects.filter(
            Q(status=RunLogChunk.Status.FAILED)
            | Q(status=RunLogChunk.Status.PENDING, updated_at__lt=retry_before)
        )
        .order_by("updated_at")[:RECOVER_BATCH_SIZE]
    )
    retried = 0
    for chunk in stale:
        event = JobEventLog.objects.filter(
            workflow_run_id=chunk.workflow_run_id, sequence=chunk.sequence
        ).first()
        parts = []
        if event:
            result = (event.payload.get("event_data") or {}).get("res") or {}
            if isinstance(result, dict):
                parts = [
                    str(result[key])
                    for key in ("stdout", "stderr", "msg")
                    if result.get(key)
                ]
        if not parts:
            # No recoverable output (e.g. no_log): drop the placeholder row.
            chunk.delete()
            continue
        text = "\n".join(parts)
        if not text.endswith("\n"):
            text += "\n"
        try:
            archive_stdout(
                run_id=chunk.workflow_run_id, sequence=chunk.sequence, text=text
            )
            retried += 1
        except Exception as exc:
            logger.warning("Run output rearchive unavailable: %s", type(exc).__name__)
    return retried


def purge_expired_archives(now=None):
    """Delete archived chunks past the retention window, files before rows."""
    now = now or timezone.now()
    retention_days = getattr(settings, "JOBS_LOG_RETENTION_DAYS", 30)
    cutoff = now - timedelta(days=retention_days)
    expired = list(
        RunLogChunk.objects.filter(
            status=RunLogChunk.Status.ARCHIVED,
            created_at__lt=cutoff,
        )
        .order_by("created_at")
        .only("workflow_run_id", "sequence", "storage_name")[:RECOVER_BATCH_SIZE]
    )
    if not expired:
        return 0
    storage = job_log_storage()
    purged = 0
    for chunk in expired:
        try:
            if chunk.storage_name:
                name = _validate_name(storage, chunk.workflow_run_id, chunk.storage_name)
                if storage.exists(name):
                    storage.delete(name)
            chunk.delete()
            purged += 1
        except Exception as exc:
            logger.warning("Run log purge unavailable: %s", type(exc).__name__)
            # Keep the row so the next pass retries the delete.
    return purged


def iter_run_stdout(run_id: int, *, block_size: int = 65536) -> Iterator[bytes]:
    if not 1 <= block_size <= 65536:
        raise ValueError("Invalid log block size")
    storage = job_log_storage()
    for chunk in (
        RunLogChunk.objects.filter(
            workflow_run_id=run_id, status=RunLogChunk.Status.ARCHIVED
        )
        .order_by("sequence")
        .iterator(chunk_size=100)
    ):
        name = _validate_name(storage, run_id, chunk.storage_name)
        with storage.open(name, "rb") as stream:
            while data := stream.read(block_size):
                yield data

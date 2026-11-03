"""Worker heartbeat and task fencing; health never authorizes a second apply."""
from datetime import timedelta
import os
import time
import json
import subprocess
from uuid import uuid4
from pathlib import Path

from celery import signals, shared_task
from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from .contracts import ProvisioningError
from .models import (
    ProvisioningWorker,
    ProvisioningPlan,
    ProvisioningAttempt,
    ProvisioningRequest,
    ProvisioningHealthIncident,
)


def runtime_checks():
    binary = Path(getattr(settings, "PROVISIONING_TERRAFORM_BINARY", ""))
    config = Path(getattr(settings, "PROVISIONING_CLI_CONFIG", ""))
    result = {
        "linux": os.name == "posix",
        "configured": binary.is_absolute()
        and binary.is_file()
        and config.is_absolute()
        and config.is_file(),
        "versionMatched": False,
        "providerLocks": False,
    }
    template_root = Path(getattr(settings, "PROVISIONING_TEMPLATE_ROOT", ""))
    if template_root.is_absolute():
        locks = list(template_root.glob("*/.terraform.lock.hcl"))
        result["providerLocks"] = bool(locks) and all(
            lock.is_file() and not lock.is_symlink() for lock in locks
        )
    if result["linux"] and result["configured"]:
        try:
            completed = subprocess.run(
                [str(binary), "version", "-json"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                env={
                    key: value
                    for key, value in os.environ.items()
                    if key in {"PATH", "HOME", "SSL_CERT_FILE", "SSL_CERT_DIR"}
                },
            )
            result["versionMatched"] = (
                completed.returncode == 0
                and len(completed.stdout) <= 1024 * 1024
                and json.loads(completed.stdout).get("terraform_version")
                == getattr(settings, "PROVISIONING_TERRAFORM_VERSION", "")
            )
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    return result


_identity = ""
_epoch = uuid4().hex
_queues = []
_last_heartbeat = 0.0


def record_worker_heartbeat(worker_id, epoch, queues, checks):
    ProvisioningWorker.objects.update_or_create(
        identity=worker_id[:128],
        defaults={
            "epoch": epoch[:64],
            "queues": queues,
            "checks": checks,
            "last_seen_at": timezone.now(),
        },
    )


def health_snapshot():
    now = timezone.now()
    workers = [
        {
            "id": row.identity,
            "online": row.last_seen_at > now - timedelta(seconds=90)
            and "provisioning" in row.queues,
            "lastSeenAt": row.last_seen_at,
            "checks": row.checks,
        }
        for row in ProvisioningWorker.objects.order_by("identity")
    ]
    return {
        "workers": workers,
        "queued": ProvisioningAttempt.objects.filter(status="queued").count(),
        "uncertain": ProvisioningAttempt.objects.filter(
            status="needs_reconciliation"
        ).count(),
        "incidents": list(
            ProvisioningHealthIncident.objects.filter(status="open").values(
                "id", "kind", "message", "created_at"
            )
        ),
        "observedAt": now,
    }


def claim_lease(kind, object_id):
    token = uuid4().hex
    model = ProvisioningPlan if kind == "plan" else ProvisioningAttempt
    if not model.objects.filter(pk=object_id, status="running").update(
        execution_token=token, lease_expires_at=timezone.now() + timedelta(seconds=90)
    ):
        raise ProvisioningError("任务已结束，不能取得执行租约")
    return token


def renew_lease(kind, object_id, token):
    model = ProvisioningPlan if kind == "plan" else ProvisioningAttempt
    return bool(
        model.objects.filter(
            pk=object_id, status="running", execution_token=token
        ).update(lease_expires_at=timezone.now() + timedelta(seconds=90))
    )


def lease_callback(kind, object_id, token):
    return lambda: renew_lease(kind, object_id, token)


@transaction.atomic
def _incident(kind, active, message):
    incident, _ = ProvisioningHealthIncident.objects.get_or_create(
        fingerprint=kind,
        defaults={"kind": kind, "message": message, "status": "resolved"},
    )
    incident = ProvisioningHealthIncident.objects.select_for_update().get(
        pk=incident.pk
    )
    status = "open" if active else "resolved"
    if incident.status != status:
        incident.status = status
        incident.message = message
        incident.save(update_fields=["status", "message", "updated_at"])
        template_id = getattr(
            settings, "PROVISIONING_MONITOR_NOTIFICATION_TEMPLATE_ID", None
        )
        if template_id:
            from apps.automation.failure_alerts import freeze_failure_alert
            from apps.automation.models import (
                NotificationRecord,
                NotificationChannel,
                NotificationTemplate,
            )
            from apps.jobs.alerts import _enqueue_alert

            frozen = freeze_failure_alert({"templateId": template_id})
            snapshot = frozen.get("templateSnapshot", {})
            record, created = NotificationRecord.objects.get_or_create(
                alert_key=f"provisioning-health:{incident.pk}:{incident.updated_at.isoformat()}:{status}",
                defaults={
                    "template": NotificationTemplate.objects.filter(
                        pk=template_id
                    ).first(),
                    "channel": NotificationChannel.objects.filter(
                        pk=snapshot.get("channelId")
                    ).first(),
                    "template_snapshot": snapshot,
                    "context": {
                        "title": "资源交付运行状况",
                        "delivery": {
                            "requestId": 0,
                            "name": kind,
                            "phase": status,
                            "region": "",
                            "message": message,
                        },
                    },
                },
            )
            if created:
                transaction.on_commit(lambda: _enqueue_alert(record.pk))


@shared_task(name="provisioning.monitor")
def monitor_provisioning():
    now = timezone.now()
    ProvisioningPlan.objects.filter(status="running", lease_expires_at__lt=now).update(
        status="failed", error_message="计划执行租约失效，请重新生成"
    )
    for attempt in ProvisioningAttempt.objects.filter(
        status="running", lease_expires_at__lt=now
    )[:100]:
        if ProvisioningAttempt.objects.filter(
            pk=attempt.pk,
            status="running",
            execution_token=attempt.execution_token,
            lease_expires_at__lt=now,
        ).update(status="needs_reconciliation", error_message="执行租约失效，请核实云资源结果"):
            ProvisioningRequest.objects.filter(pk=attempt.plan.request_id).update(
                execution_status="needs_reconciliation"
            )
    snapshot = health_snapshot()
    enabled = getattr(settings, "PROVISIONING_ENABLED", False)
    _incident(
        "worker_unavailable",
        enabled and not any(row["online"] for row in snapshot["workers"]),
        "无在线专用 Worker，请检查 provisioning 队列",
    )
    storage_ready = True
    if enabled:
        from .state_protection import check_protection_storage

        try:
            check_protection_storage()
        except Exception:
            storage_ready = False
    _incident("protection_storage", not storage_ready, "state 存储、备份或密钥配置异常")
    runtime_ready = any(
        row["online"]
        and all(
            row["checks"].get(check)
            for check in ["configured", "linux", "versionMatched", "providerLocks"]
        )
        for row in snapshot["workers"]
    )
    _incident(
        "runtime_configuration",
        enabled and not runtime_ready,
        "固定版本 Terraform 或 Provider 镜像配置不可用",
    )
    _incident(
        "queue_backlog",
        ProvisioningAttempt.objects.filter(
            status="queued", created_at__lt=now - timedelta(seconds=300)
        ).exists(),
        "资源创建队列积压超过 5 分钟",
    )
    _incident("uncertain_execution", snapshot["uncertain"] > 0, "存在执行结果待核实的资源申请")
    from .models import ProvisioningStateVersion
    from .state_protection import verify_active_states

    verify_active_states()

    _incident(
        "state_backup",
        ProvisioningRequest.objects.filter(
            execution_status="success", active_state_version__isnull=True
        ).exists()
        or ProvisioningStateVersion.objects.filter(active_requests__isnull=False)
        .exclude(protection_status="protected")
        .exists(),
        "存在 state 备份异常",
    )
    return snapshot


@signals.worker_ready.connect(weak=False)
def worker_ready(sender=None, **kwargs):
    global _identity, _queues
    _identity = getattr(sender, "hostname", "")
    consumer = getattr(sender, "task_consumer", None)
    _queues = [q.name for q in getattr(consumer, "queues", [])]
    heartbeat()


@signals.heartbeat_sent.connect(weak=False)
def heartbeat(**kwargs):
    global _last_heartbeat
    if (
        not _identity
        or "provisioning" not in _queues
        or time.monotonic() - _last_heartbeat < 15
    ):
        return
    _last_heartbeat = time.monotonic()
    try:
        close_old_connections()
        record_worker_heartbeat(
            _identity,
            _epoch,
            _queues,
            runtime_checks(),
        )
    except Exception:
        # Heartbeat storage failure cannot crash the Celery main process.
        pass


@signals.worker_shutdown.connect(weak=False)
def worker_shutdown(**kwargs):
    if not _identity:
        return
    try:
        ProvisioningWorker.objects.filter(identity=_identity, epoch=_epoch).update(
            last_seen_at=timezone.now() - timedelta(seconds=91)
        )
    except Exception:
        pass

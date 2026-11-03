"""Worker-routed, actor-scoped temporary reads. Never persist plaintext in logs."""
import base64
import difflib
import hashlib
import json
from datetime import timedelta

from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.cmdb.crypto import encrypt_secret, decrypt_secret
from apps.cmdb.execution import execute_asset_module
from apps.cmdb.targets import resolve_targets, target_snapshot_fingerprint
from apps.jobs.worker_pools import (
    resolve_worker_pool,
    region_for_targets,
    queue_for_pool,
)
from common.auth.rbac import verify_permission
from .models import RemoteFileRead, ConsulTemplateFile
from .templates import validate_template_path

MAX_BYTES = 256 * 1024
READ_PERMISSION_PATH = "/api/v1/consul/templates/read-remote"
READ_PROGRAM = r"""
import os, sys, stat, base64, hashlib, json
path, limit = sys.argv[1], int(sys.argv[2])
try:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("not_regular")
        raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("too_large")
        raw.decode("utf-8")
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("changed")
    result = {"exists": True, "data": base64.b64encode(raw).decode(), "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
except FileNotFoundError:
    result = {"exists": False, "sha256": "missing", "size": 0}
except PermissionError:
    result = {"error": "permission"}
except UnicodeError:
    result = {"error": "encoding"}
except ValueError as exc:
    result = {"error": str(exc)}
except OSError:
    result = {"error": "io"}
print(json.dumps(result))
"""


def template_revision(row):
    return hashlib.sha256(
        json.dumps(
            [
                row.host_id,
                row.path,
                row.content,
                row.reload_command,
                row.updated_at.isoformat(),
            ],
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def authorize(actor):
    if (
        not actor
        or not actor.is_active
        or not actor.job_status
        or not verify_permission(actor, READ_PERMISSION_PATH, "POST")[0]
    ):
        raise PermissionDenied("缺少远端配置读取权限或账号已停用")


def targets_for(actor, host_id):
    targets = resolve_targets(actor=actor, host_ids=[host_id], group_ids=[])
    if targets[0]["connection_type"] != "ssh":
        raise ValidationError("仅支持 Linux SSH 主机")
    from apps.cmdb.models import AssetHost

    if not AssetHost.objects.filter(pk=host_id, os_family="linux").exists():
        raise ValidationError("仅支持 Linux SSH 主机")
    return targets


@transaction.atomic
def schedule_read(actor, host_id, path, template_id=None, revision=""):
    authorize(actor)
    path = validate_template_path(path)
    if not path.endswith((".hcl", ".ctmpl")):
        raise ValidationError("仅可读取 .hcl 配置或 .ctmpl 模板文件")
    targets = targets_for(actor, host_id)
    template = None
    if template_id:
        template = (
            ConsulTemplateFile.objects.select_for_update()
            .filter(pk=template_id)
            .first()
        )
        if template is None:
            raise ValidationError("配置文件记录已删除")
        if (template.host_id, template.path, template_revision(template)) != (
            host_id,
            path,
            revision,
        ):
            raise ValidationError("配置已变化，请刷新后重新比较")
    # Lock the actor to bound parallel reads without racing two requests.
    get_user_model().objects.select_for_update().get(pk=actor.pk)
    if (
        RemoteFileRead.objects.filter(
            actor=actor, status__in=["queued", "running"], expires_at__gt=timezone.now()
        ).count()
        >= 3
    ):
        raise ValidationError("已有读取任务进行中，请等待后重试")
    pool = resolve_worker_pool(
        actor=actor,
        pool_id=None,
        execution_kind="module",
        target_region=region_for_targets(targets),
    )
    row = RemoteFileRead.objects.create(
        actor=actor,
        host_id=host_id,
        worker_pool=pool,
        path=path,
        template=template,
        template_revision=template_revision(template) if template else "",
        target_fingerprint=target_snapshot_fingerprint(targets),
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    transaction.on_commit(lambda: publish_read(row.pk))
    return row


def publish_read(read_id):
    from .tasks import read_remote_file

    row = RemoteFileRead.objects.select_related("worker_pool").get(pk=read_id)
    try:
        read_remote_file.apply_async(
            args=[str(read_id)],
            queue=queue_for_pool(row.worker_pool),
            soft_time_limit=75,
            time_limit=90,
        )
    except Exception:
        RemoteFileRead.objects.filter(pk=read_id, status="queued").update(
            error="队列暂不可用，等待自动重试"
        )


def execute_read(read_id):
    if not RemoteFileRead.objects.filter(
        pk=read_id, status="queued", expires_at__gt=timezone.now()
    ).update(status="running", updated_at=timezone.now()):
        return
    row = RemoteFileRead.objects.select_related("actor").get(pk=read_id)
    try:
        authorize(row.actor)
        targets = targets_for(row.actor, row.host_id)
        resolve_worker_pool(
            actor=row.actor, pool_id=row.worker_pool_id, execution_kind="module"
        )
        if target_snapshot_fingerprint(targets) != row.target_fingerprint:
            raise ValidationError("主机连接配置已变化，请重新读取")
        payload = {}

        def event_received(event):
            if event.event_type == "host_ok":
                stdout = event.result.get("stdout", "{}")
                if len(stdout) > MAX_BYTES * 2:
                    raise ValidationError("读取结果超过大小上限")
                payload.update(json.loads(stdout))

        result = execute_asset_module(
            actor=row.actor,
            host_id=row.host_id,
            module="ansible.builtin.command",
            module_args=json.dumps(
                {"argv": ["python3", "-c", READ_PROGRAM, row.path, str(MAX_BYTES)]}
            ),
            timeout=60,
            on_event=event_received,
        )
        if result.status != "success":
            raise ValidationError("主机连接或执行失败，请检查网络、SSH 凭据和 python3")
        errors = {
            "permission": "文件无读取权限",
            "encoding": "文件不是有效 UTF-8 文本",
            "not_regular": "目标不是普通文件",
            "too_large": "文件超过256 KiB读取上限",
            "changed": "文件在读取时发生变化，请重试",
            "io": "文件读取失败或为符号链接",
        }
        if payload.get("error"):
            raise ValidationError(errors.get(payload["error"], "远端文件读取失败"))
        if type(payload.get("exists")) is not bool:
            raise ValidationError("读取结果格式错误")
        content = ""
        checksum = "missing"
        if payload["exists"]:
            raw = base64.b64decode(payload.get("data", ""), validate=True)
            if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != payload.get(
                "sha256"
            ):
                raise ValidationError("读取内容校验失败或超过大小上限")
            content, checksum = raw.decode("utf-8"), payload["sha256"]
        row.actor.refresh_from_db()
        authorize(row.actor)
        resolve_worker_pool(
            actor=row.actor, pool_id=row.worker_pool_id, execution_kind="module"
        )
        if (
            target_snapshot_fingerprint(targets_for(row.actor, row.host_id))
            != row.target_fingerprint
        ):
            raise ValidationError("主机连接配置已变化，请重新读取")
        RemoteFileRead.objects.filter(
            pk=read_id, status="running", expires_at__gt=timezone.now()
        ).update(
            status="succeeded",
            exists=payload["exists"],
            checksum=checksum,
            size=len(content.encode()),
            content_encrypted=encrypt_secret(content),
            error="",
            updated_at=timezone.now(),
        )
    except Exception as exc:
        message = "读取失败，请检查执行节点、网络、主机权限和文件路径"
        if isinstance(exc, ValidationError):
            message = "；".join(str(item) for item in exc.detail)[:256]
        if isinstance(exc, PermissionDenied):
            message = "读取权限已失效"
        RemoteFileRead.objects.filter(pk=read_id, status="running").update(
            status="failed",
            error=message,
            content_encrypted="",
            updated_at=timezone.now(),
        )


def read_result(row, actor):
    authorize(actor)
    if row.actor_id != actor.pk:
        raise PermissionDenied("只能查看本人发起的读取结果")
    resolve_worker_pool(
        actor=actor, pool_id=row.worker_pool_id, execution_kind="module"
    )
    if (
        target_snapshot_fingerprint(targets_for(actor, row.host_id))
        != row.target_fingerprint
    ):
        raise ValidationError("主机连接配置已变化，请重新读取")
    expired = row.expires_at <= timezone.now()
    return {
        "id": str(row.pk),
        "status": "expired" if expired else row.status,
        "exists": row.exists,
        "content": decrypt_secret(row.content_encrypted)
        if not expired and row.status == "succeeded" and row.exists
        else None,
        "checksum": row.checksum,
        "size": row.size,
        "error": "读取结果已过期，请重新读取" if expired else row.error,
    }


def compare_read(row, actor, content):
    result = read_result(row, actor)
    if result["status"] != "succeeded":
        raise ValidationError("请先完成远端读取")
    if len(content.encode()) > MAX_BYTES:
        raise ValidationError("内容超过256 KiB上限")
    remote = result["content"] or ""
    lines = difflib.unified_diff(
        remote.splitlines(keepends=True),
        content.splitlines(keepends=True),
        fromfile="远端当前文件",
        tofile="待下发内容",
    )
    diff = "".join(
        line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
        for line in lines
    )
    return {"changed": remote != content or not result["exists"], "diff": diff}


def deploy_baseline(template, actor, read_id):
    row = RemoteFileRead.objects.filter(pk=read_id).first()
    if not row:
        raise ValidationError("请先读取远端并确认差异")
    result = read_result(row, actor)
    if (
        result["status"] != "succeeded"
        or row.template_id != template.pk
        or row.template_revision != template_revision(template)
    ):
        raise ValidationError("预览已过期或配置已变化，请重新比较")
    if (row.host_id, row.path) != (template.host_id, template.path):
        raise ValidationError("预览主机或路径不匹配")
    if (
        target_snapshot_fingerprint(targets_for(actor, row.host_id))
        != row.target_fingerprint
    ):
        raise ValidationError("主机连接配置已变化，请重新比较")
    return result["checksum"]


def recover_reads():
    now = timezone.now()
    RemoteFileRead.objects.filter(expires_at__lte=now).exclude(status="expired").update(
        status="expired", content_encrypted="", error="读取结果已过期"
    )
    RemoteFileRead.objects.filter(
        status="running", updated_at__lt=now - timedelta(minutes=2)
    ).update(status="failed", content_encrypted="", error="读取超时，请检查 Worker 后重试")
    for row in RemoteFileRead.objects.filter(
        status="queued", expires_at__gt=now, updated_at__lt=now - timedelta(seconds=30)
    ).order_by("created_at")[:50]:
        RemoteFileRead.objects.filter(pk=row.pk, status="queued").update(updated_at=now)
        publish_read(row.pk)
    RemoteFileRead.objects.filter(expires_at__lt=now - timedelta(days=1)).delete()

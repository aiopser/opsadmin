import base64
import hashlib
import json
import os
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .contracts import ProvisioningError, canonical_digest
from .models import (
    ProvisioningArtifact,
    ProvisioningAttempt,
    ProvisioningRequest,
    ProvisioningStateVersion,
)
from .state_crypto import StateKeyring
from .terraform import ArtifactStore


def check_protection_storage():
    StateKeyring()
    primary = ArtifactStore()
    backup = ArtifactStore(backup=True)
    if (
        primary.root == backup.root
        or primary.root in backup.root.parents
        or backup.root in primary.root.parents
    ):
        raise ProvisioningError("主制品与备份必须使用独立私有目录")
    for root in [primary.root, backup.root]:
        import tempfile

        descriptor, name = tempfile.mkstemp(prefix=".probe-", dir=root)
        os.close(descriptor)
        os.unlink(name)


def parse_state(files):
    try:
        raw = base64.b64decode(files["terraform.tfstate"], validate=True)
        if len(raw) > 16 * 1024 * 1024:
            raise ProvisioningError("state 超过 16 MiB 限制")
        state = json.loads(raw)
        lineage, serial = state["lineage"], state["serial"]
        if (
            not isinstance(lineage, str)
            or not 1 <= len(lineage) <= 128
            or type(serial) is not int
            or serial < 0
            or state.get("version") != 4
        ):
            raise ValueError()
        return state, hashlib.sha256(raw).hexdigest()
    except (KeyError, ValueError, TypeError):
        raise ProvisioningError("缺少可校验的 Terraform state，需核实执行结果") from None


def write_backup(payload):
    store = ArtifactStore(backup=True)
    key = store.put(payload)
    if store.get(key) != payload:
        raise ProvisioningError("备份回读校验失败")
    return key


def _register(record, attempt, payload, key, storage, purpose="state", expires_at=None):
    store = ArtifactStore(backup=storage == "backup")
    return ProvisioningArtifact.objects.create(
        request=record,
        attempt=attempt,
        storage=storage,
        purpose=purpose,
        key=key,
        digest=canonical_digest(payload),
        byte_size=(store.root / key).stat().st_size,
        key_id=settings.PROVISIONING_STATE_ACTIVE_KEY_ID,
        expires_at=expires_at,
    )


def capture_state(attempt_id, files, *, force_version=False, execution_token=None):
    state, digest = parse_state(files)
    # A failing backup must still leave a primary recovery copy.
    StateKeyring()
    attempt = ProvisioningAttempt.objects.select_related(
        "plan__request__credential"
    ).get(pk=attempt_id)
    record = attempt.plan.request
    previous = (
        record.state_versions.filter(
            attempt=attempt, digest=digest, protection_status="protected"
        )
        .order_by("-version")
        .first()
    )
    if previous and not force_version:
        try:
            read_state_files(previous)
            read_state_files(previous, backup=True)
            return previous
        except (OSError, ProvisioningError):
            pass
    payload = {
        "files": files,
        "requestId": record.pk,
        "attemptId": attempt.pk,
        "sourceId": record.credential.source_id,
    }
    primary_store = ArtifactStore()
    primary_key = primary_store.put(payload)
    backup_key, error = None, ""
    try:
        check_protection_storage()
        backup_key = write_backup(payload)
    except Exception:
        error = "独立备份失败，已保留主副本；请修复备份后再进行资源变更"
    with transaction.atomic():
        record = ProvisioningRequest.objects.select_for_update().get(pk=record.pk)
        attempt = ProvisioningAttempt.objects.select_for_update().get(pk=attempt_id)
        if execution_token is not None and (
            attempt.status != "running"
            or attempt.execution_token != execution_token
            or not attempt.lease_expires_at
            or attempt.lease_expires_at <= timezone.now()
        ):
            raise ProvisioningError("执行租约已失效，仅保留独立制品待核实")
        existing = (
            record.state_versions.filter(attempt=attempt, digest=digest)
            .order_by("-version")
            .first()
        )
        if existing and existing.protection_status == "protected" and not force_version:
            try:
                read_state_files(existing)
                read_state_files(existing, backup=True)
                return existing
            except (OSError, ProvisioningError):
                # Repair a missing primary by creating a new version from verified input.
                pass
        latest = record.state_versions.order_by("-version").first()
        if latest and (
            latest.lineage != state["lineage"]
            or state["serial"] < latest.serial
            or (state["serial"] == latest.serial and latest.digest != digest)
        ):
            raise ProvisioningError("state lineage 或版本冲突，保留制品待人工核实")
        primary = _register(record, attempt, payload, primary_key, "main")
        backup = (
            _register(record, attempt, payload, backup_key, "backup")
            if backup_key
            else None
        )
        number = (
            record.state_versions.aggregate(value=Max("version"))["value"] or 0
        ) + 1
        version = ProvisioningStateVersion.objects.create(
            request=record,
            attempt=attempt,
            version=number,
            lineage=state["lineage"],
            serial=state["serial"],
            digest=digest,
            primary_artifact=primary,
            backup_artifact=backup,
            protection_status="protected" if backup else "degraded",
            verified_at=timezone.now() if backup else None,
            message=error,
        )
        if attempt.status != "needs_reconciliation" and not force_version:
            record.active_state_version = version
            record.state_generation += 1
            record.save(
                update_fields=["active_state_version", "state_generation", "updated_at"]
            )
        ProvisioningAttempt.objects.filter(pk=attempt.pk).update(
            recovery_artifact_key=primary_key
        )
        return version


def read_state_files(version, backup=False):
    artifact = version.backup_artifact if backup else version.primary_artifact
    if not artifact or artifact.cleanup_status != "retained":
        raise ProvisioningError("可恢复制品不存在")
    payload = ArtifactStore(backup=backup).get(artifact.key)
    if (
        canonical_digest(payload) != artifact.digest
        or payload.get("requestId") != version.request_id
        or payload.get("attemptId") != version.attempt_id
        or payload.get("sourceId") != version.request.credential.source_id
    ):
        raise ProvisioningError("state 制品归属或摘要校验失败")
    _, digest = parse_state(payload["files"])
    if digest != version.digest:
        raise ProvisioningError("state 内容摘要不匹配")
    return payload["files"]


def assert_write_protected(record):
    check_protection_storage()
    if (
        record.active_state_version_id
        and record.active_state_version.protection_status != "protected"
    ):
        raise ProvisioningError("state 备份异常，请先修复保护状态")
    if record.active_state_version_id:
        read_state_files(record.active_state_version)
        read_state_files(record.active_state_version, backup=True)


def protection_summary(record):
    version = record.active_state_version
    if not version:
        return {
            "status": "not_applicable"
            if record.execution_status == "not_started"
            else "unverified",
            "versionId": None,
            "verifiedAt": None,
            "message": "尚无可校验的 state 版本",
        }
    return {
        "status": version.protection_status,
        "versionId": version.pk,
        "verifiedAt": version.verified_at,
        "message": version.message,
    }


def verify_active_states(limit=100):
    """Rotate checks by update time so a damaged copy cannot starve other states."""
    versions = list(
        ProvisioningStateVersion.objects.filter(active_requests__isnull=False)
        .select_related("primary_artifact", "backup_artifact", "request__credential")
        .order_by("updated_at", "pk")[:limit]
    )
    for version in versions:
        now = timezone.now()
        values = {"updated_at": now}
        try:
            read_state_files(version)
            read_state_files(version, backup=True)
            values.update(protection_status="protected", verified_at=now, message="")
        except Exception:
            values.update(
                protection_status="degraded", message="主副本或备份校验失败，请检查私有存储、历史密钥及文件完整性"
            )
        # A restore may have switched the active version while files were checked.
        ProvisioningStateVersion.objects.filter(
            pk=version.pk, updated_at=version.updated_at, active_requests__isnull=False
        ).update(**values)

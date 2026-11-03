"""Evidence-bound human resolution of an interrupted create, without cloud writes."""

from datetime import timedelta
import ipaddress
import secrets

from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import BasePermission

from common.auth.rbac import verify_permission
from apps.cmdb.models import AssetHost, AssetSource
from apps.cmdb.sync_inventory import cloud_inventory_values
from .contracts import ProvisioningError, canonical_digest
from .models import (
    ProvisioningAttempt,
    ProvisioningRequest,
    ProvisioningResolutionPreview,
)
from .providers import read_instances
from .reconciliation import state_instance_ids, upsert_observed_assets
from .services import event
from .state_protection import capture_state, read_state_files
from .terraform import ArtifactStore


def can_review(actor):
    from django.contrib.auth import get_user_model

    current = (
        get_user_model()
        .objects.filter(pk=getattr(actor, "pk", None), is_active=True, job_status=True)
        .first()
    )
    return bool(
        current and verify_permission(current, "/api/v1/provisioning/review", "GET")[0]
    )


class ProvisioningReviewPermission(BasePermission):
    message = "需要资源申请复核权限"

    def has_permission(self, request, view):
        return can_review(request.user)


def _validate(record, attempt, actor):
    if not can_review(actor):
        raise ProvisioningError("无资源申请复核权限")
    if actor.pk in {record.created_by_id, attempt.actor_id}:
        raise ProvisioningError("请由申请人和执行人之外的复核人核实结案")
    if (
        record.execution_status != "needs_reconciliation"
        or attempt.status != "needs_reconciliation"
    ):
        raise ProvisioningError("仅可人工核实结果未知的执行")
    if not attempt.apply_started_at:
        raise ProvisioningError("没有发起 apply 的执行证据，不能承认云资源")
    if record.plans.filter(attempt__status__in=["queued", "running"]).exists() or (
        attempt.lease_expires_at and attempt.lease_expires_at > timezone.now()
    ):
        raise ProvisioningError("写任务或执行租约尚未结束，禁止人工结案")
    source = record.credential.source
    if (
        not source.is_active
        or source.source_type != "cloud"
        or source.cloud_provider != record.version.template.provider
        or record.region not in source.regions
    ):
        raise ProvisioningError("读取云账号、平台或地域无效")


def _state(record, attempt, version):
    latest = record.state_versions.order_by("-version").first()
    if (
        not latest
        or latest.pk != version.pk
        or version.request_id != record.pk
        or version.attempt_id != attempt.pk
        or version.protection_status != "protected"
    ):
        raise ProvisioningError("仅可核实本次执行最新且独立备份完整的 state")
    # Both copies must still pass ownership, encryption, digest and serial checks.
    files = read_state_files(version)
    read_state_files(version, backup=True)
    ids = state_instance_ids(files, record.version.template.provider)
    count = record.parameters.get("count")
    if type(count) is not int or not ids or len(ids) != count:
        raise ProvisioningError("state 的实例数量不完整，保留待核实；禁止重新 apply")
    return ids


def _observe(record, ids):
    assets = {}
    try:
        observed = read_instances(record.credential.source, record.region, ids)
    except ProvisioningError:
        raise
    except Exception:
        raise ProvisioningError("云资源回读失败，请检查只读权限与网络后重新预览") from None
    for item in observed:
        instance_id = item.get("source_id")
        if instance_id not in ids or instance_id in assets:
            raise ProvisioningError("云端返回了不属于本次 state 的实例或重复身份")
        values = cloud_inventory_values(record.credential.source, item)
        try:
            ipaddress.ip_address(values.get("internal_ip", ""))
        except ValueError:
            raise ProvisioningError("云端实例缺少有效私网 IP，暂不可结案") from None
        if (
            not values.get("hostname")
            or values.get("region", record.region) != record.region
            or values.get("cloud_state")
            in {"deleted", "terminated", "deleting", "terminating"}
        ):
            raise ProvisioningError("云端实例属性或运行状态不可交付")
        assets[instance_id] = item
    if set(assets) != set(ids):
        raise ProvisioningError("云端未完整返回 state 中的所有实例，暂不可结案")
    return assets


def _evidence(record, attempt, version, assets):
    return {
        "requestId": record.pk,
        "attemptId": attempt.pk,
        "stateVersionId": version.pk,
        "stateDigest": version.digest,
        "serial": version.serial,
        "lineage": version.lineage,
        "stateGeneration": record.state_generation,
        "requestRevision": record.revision,
        "region": record.region,
        "templateVersionId": record.version_id,
        "credentialId": record.credential_id,
        "parametersDigest": canonical_digest(record.parameters),
        "sourceId": record.credential.source_id,
        "sourceUpdatedAt": record.credential.source.updated_at.isoformat(),
        "instanceIds": sorted(assets),
        "observedAssets": [
            {
                "instanceId": key,
                **{
                    field: value
                    for field, value in cloud_inventory_values(
                        record.credential.source, assets[key]
                    ).items()
                    if field
                    in {
                        "hostname",
                        "internal_ip",
                        "external_ip",
                        "os_family",
                        "cloud_state",
                        "region",
                    }
                },
            }
            for key in sorted(assets)
        ],
    }


def _records(request_id):
    record = ProvisioningRequest.objects.select_related(
        "credential__source", "version__template"
    ).get(pk=request_id)
    attempt = (
        ProvisioningAttempt.objects.filter(plan__request=record)
        .select_related("plan")
        .order_by("-pk")
        .first()
    )
    if not attempt:
        raise ProvisioningError("没有可核实的执行记录")
    return record, attempt


def preview_resolution(request_id, actor, state_version_id=None):
    record, attempt = _records(request_id)
    _validate(record, attempt, actor)
    if state_version_id is None:
        version = record.state_versions.order_by("-version").first()
        if version is None:
            if not attempt.recovery_artifact_key:
                raise ProvisioningError("缺少 state 证据，请恢复执行归档；禁止重新 apply 或直接改库")
            # Only the worker's internal archive is accepted; no client-supplied state/IDs.
            files = ArtifactStore().get(attempt.recovery_artifact_key)["files"]
            version = capture_state(attempt.pk, files)
        elif (
            version.attempt_id == attempt.pk and version.protection_status == "degraded"
        ):
            # Repair protection from the verified latest primary; never select an
            # older serial or restore an alternate state to resolve uncertainty.
            version = capture_state(attempt.pk, read_state_files(version))
    else:
        version = record.state_versions.filter(pk=state_version_id).first()
    if version is None:
        raise ProvisioningError("state 版本不属于本申请")
    ids = _state(record, attempt, version)
    assets = _observe(record, ids)
    evidence = _evidence(record, attempt, version, assets)
    with transaction.atomic():
        source = AssetSource.objects.select_for_update().get(
            pk=record.credential.source_id
        )
        current = (
            ProvisioningRequest.objects.select_for_update()
            .select_related("credential__source", "version__template")
            .get(pk=record.pk)
        )
        locked = ProvisioningAttempt.objects.select_for_update().get(pk=attempt.pk)
        _validate(current, locked, actor)
        _state(current, locked, version)
        if (
            source.updated_at != record.credential.source.updated_at
            or _evidence(current, locked, version, assets) != evidence
        ):
            raise ProvisioningError("核实期间申请或云账号已变化，请重新预览")
        preview = ProvisioningResolutionPreview.objects.create(
            request=current,
            attempt=locked,
            state_version=version,
            actor=actor,
            generation=current.state_generation,
            source_updated_at=source.updated_at,
            evidence=evidence,
            digest=canonical_digest({"actor": actor.pk, "evidence": evidence}),
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        event(
            current,
            actor,
            "resolution_preview",
            "已回读云资源并生成待核实结案证据",
            locked.plan,
            evidence=evidence,
        )
        return preview


def confirm_resolution(preview_id, actor, digest, evidence_reference, comment):
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or not isinstance(evidence_reference, str)
        or not 1 <= len(evidence_reference.strip()) <= 300
        or not isinstance(comment, str)
        or not 1 <= len(comment.strip()) <= 500
    ):
        raise ProvisioningError("请填写有效预览摘要、外部证据编号和核实说明")
    preview = ProvisioningResolutionPreview.objects.select_related("state_version").get(
        pk=preview_id
    )
    record, attempt = _records(preview.request_id)
    _validate(record, attempt, actor)
    if (
        preview.actor_id != actor.pk
        or preview.status != "pending"
        or preview.expires_at <= timezone.now()
        or not secrets.compare_digest(preview.digest, digest)
    ):
        raise ProvisioningError("核实预览已失效，请重新预览")
    ids = _state(record, attempt, preview.state_version)
    observed_at = timezone.now()
    assets = _observe(record, ids)
    with transaction.atomic():
        source = AssetSource.objects.select_for_update().get(
            pk=record.credential.source_id
        )
        current = (
            ProvisioningRequest.objects.select_for_update()
            .select_related("credential__source", "version__template")
            .get(pk=record.pk)
        )
        locked = ProvisioningAttempt.objects.select_for_update().get(pk=attempt.pk)
        preview = (
            ProvisioningResolutionPreview.objects.select_for_update()
            .select_related("state_version")
            .get(pk=preview.pk)
        )
        _validate(current, locked, actor)
        _state(current, locked, preview.state_version)
        evidence = _evidence(current, locked, preview.state_version, assets)
        if (
            preview.status != "pending"
            or preview.actor_id != actor.pk
            or preview.attempt_id != locked.pk
            or preview.expires_at <= timezone.now()
            or preview.generation != current.state_generation
            or preview.source_updated_at != source.updated_at
            or evidence != preview.evidence
            or not secrets.compare_digest(
                preview.digest,
                canonical_digest({"actor": actor.pk, "evidence": evidence}),
            )
        ):
            raise ProvisioningError("云端或控制状态已变化，请重新预览核实")
        if AssetHost.objects.filter(
            asset_source=source, source_id__in=ids, last_observed_at__gt=observed_at
        ).exists():
            raise ProvisioningError("已有更新的云端资产观测，请重新预览核实")
        locked.instance_ids = ids
        locked.asset_ids = upsert_observed_assets(source, assets, observed_at)
        locked.status = "reconciled"
        locked.error_message = ""
        locked.execution_token = secrets.token_hex(24)
        locked.reconciliation_token = secrets.token_hex(24)
        locked.finished_at = timezone.now()
        locked.save(
            update_fields=[
                "instance_ids",
                "asset_ids",
                "status",
                "error_message",
                "execution_token",
                "reconciliation_token",
                "finished_at",
                "updated_at",
            ]
        )
        current.execution_status = "success"
        current.inventory_status = "success"
        current.active_state_version = preview.state_version
        current.state_generation += 1
        current.save(
            update_fields=[
                "execution_status",
                "inventory_status",
                "active_state_version",
                "state_generation",
                "updated_at",
            ]
        )
        current.plans.filter(status="ready").update(status="superseded")
        preview.status = "consumed"
        preview.evidence_reference = evidence_reference.strip()
        preview.comment = comment.strip()
        preview.confirmed_at = timezone.now()
        preview.save(
            update_fields=[
                "status",
                "evidence_reference",
                "comment",
                "confirmed_at",
                "updated_at",
            ]
        )
        event(
            current,
            actor,
            "manually_reconciled",
            "已依据受保护 state 与云端回读证据人工核实成功并结案",
            locked.plan,
            evidence={
                **evidence,
                "previewId": str(preview.pk),
                "previewDigest": preview.digest,
                "evidenceReference": preview.evidence_reference,
                "comment": preview.comment,
            },
        )
        return preview

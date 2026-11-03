import base64
import ipaddress
import json
import secrets

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.cmdb.models import AssetHost
from apps.cmdb.sync_inventory import cloud_inventory_values
from apps.cmdb.tasks import _host_defaults
from .contracts import ProvisioningError
from .models import ProvisioningAttempt, ProvisioningRequest
from common.auth.rbac import verify_permission
from .terraform import ArtifactStore
from .providers import read_instances
from .services import event


def state_instance_ids(files, provider):
    encoded = files.get("terraform.tfstate")
    if not encoded:
        raise ProvisioningError("未找到执行状态，需要人工核实云资源")
    state = json.loads(base64.b64decode(encoded))
    resource_type = (
        "alicloud_instance" if provider == "aliyun" else "tencentcloud_instance"
    )
    return sorted(
        {
            str(item["attributes"]["id"])
            for resource in state.get("resources", [])
            if resource.get("mode") == "managed"
            and resource.get("type") == resource_type
            for item in resource.get("instances", [])
            if item.get("attributes", {}).get("id")
        }
    )


def upsert_observed_assets(source, assets, observed_at):
    """Caller holds the source lock shared with ordinary cloud synchronization."""
    asset_ids = []
    for instance_id, item in assets.items():
        host = AssetHost.objects.filter(
            asset_source=source, source_id=instance_id
        ).first()
        if host and host.last_observed_at and host.last_observed_at > observed_at:
            asset_ids.append(host.pk)
            continue
        values = cloud_inventory_values(source, item, host=host)
        if host is None:
            host = AssetHost(**_host_defaults(item, source, observed_at))
        for field, value in values.items():
            setattr(host, field, value)
        host.last_observed_at = observed_at
        host.last_synced_at = timezone.now()
        host.save()
        asset_ids.append(host.pk)
    return asset_ids


def claim_reconciliation(attempt_id, *, force=False):
    with transaction.atomic():
        attempt = ProvisioningAttempt.objects.select_related("plan").get(pk=attempt_id)
        record = ProvisioningRequest.objects.select_for_update().get(
            pk=attempt.plan.request_id
        )
        attempt = ProvisioningAttempt.objects.select_for_update().get(pk=attempt_id)
        if attempt.status not in {"applied", "needs_reconciliation", "reconciled"}:
            return None
        if (
            not force
            and attempt.status == "reconciled"
            and record.inventory_status == "success"
        ):
            return None
        token = secrets.token_hex(24)
        ProvisioningAttempt.objects.filter(pk=attempt.pk).update(
            reconciliation_token=token,
            status="applied" if attempt.status == "reconciled" else attempt.status,
        )
        ProvisioningRequest.objects.filter(pk=record.pk).update(
            inventory_status="pending"
        )
        return token


def queue_reconciliation(attempt_id, actor_id=None, *, force=False):
    token = claim_reconciliation(attempt_id, force=force)
    if not token:
        return False
    try:
        reconcile_attempt.apply_async(
            args=[attempt_id, actor_id, token], queue="provisioning"
        )
    except Exception:
        with transaction.atomic():
            attempt = ProvisioningAttempt.objects.select_related("plan").get(
                pk=attempt_id
            )
            record = ProvisioningRequest.objects.select_for_update().get(
                pk=attempt.plan.request_id
            )
            if not (
                ProvisioningAttempt.objects.filter(
                    pk=attempt_id, reconciliation_token=token
                )
                .exclude(status="reconciled")
                .update(reconciliation_token=secrets.token_hex(24))
            ):
                return False
            ProvisioningRequest.objects.filter(pk=record.pk).update(
                inventory_status="failed"
            )
        raise ProvisioningError("回读任务投递失败，请检查专用 Worker 队列") from None
    return True


@shared_task(name="provisioning.reconcile", bind=True, max_retries=5)
def reconcile_attempt(self, attempt_id, actor_id=None, token=None):
    token = token or claim_reconciliation(attempt_id)
    if not token:
        return
    attempt = ProvisioningAttempt.objects.select_related(
        "plan__request__credential__source", "plan__request__version__template"
    ).get(pk=attempt_id)
    record = attempt.plan.request
    if attempt.reconciliation_token != token or attempt.status not in {
        "applied",
        "needs_reconciliation",
        "reconciled",
    }:
        return
    try:
        from django.contrib.auth import get_user_model

        actor = (
            get_user_model()
            .objects.filter(
                pk=actor_id or attempt.actor_id, is_active=True, job_status=True
            )
            .first()
        )
        if (
            actor is None
            or not verify_permission(
                actor, f"/api/v1/provisioning/requests/{record.pk}/reconcile", "POST"
            )[0]
        ):
            raise ProvisioningError("回读纳管授权已失效")
        if not record.credential.source.is_active:
            raise ProvisioningError("云账号已停用")
        if record.active_state_version_id:
            from .state_protection import read_state_files

            files = read_state_files(record.active_state_version)
        else:
            files = ArtifactStore().get(attempt.recovery_artifact_key)["files"]
        ids = state_instance_ids(files, record.version.template.provider)
        if not ids:
            raise ProvisioningError("执行状态中没有可核实的实例 ID，请人工核实")
        # Inventory reads use the account's read credential, never the write secret.
        # Restrict the collector to the request region; do not synchronize unrelated assets.
        source = record.credential.source
        observed_at = timezone.now()
        source_revision = source.updated_at
        assets = {
            item["source_id"]: item
            for item in read_instances(source, record.region, ids)
            if item["source_id"] in ids
        }
        if set(assets) != set(ids):
            raise ProvisioningError("云资源暂未完整返回，等待再次回读")
        for item in assets.values():
            try:
                ipaddress.ip_address(item.get("internal_ip", ""))
            except ValueError:
                raise ProvisioningError("云资源尚无有效私网 IP，等待再次回读") from None
        with transaction.atomic():
            # Same source lock as ordinary synchronization; retries keep manual fields.
            locked_source = type(source).objects.select_for_update().get(pk=source.pk)
            if (
                locked_source.updated_at != source_revision
                or not locked_source.is_active
            ):
                raise ProvisioningError("云账号配置已变化，请重新回读")
            current = ProvisioningRequest.objects.select_for_update().get(pk=record.pk)
            locked = ProvisioningAttempt.objects.select_for_update().get(pk=attempt_id)
            if (
                locked.reconciliation_token != token
                or current.state_generation != record.state_generation
            ):
                return
            actor = (
                get_user_model()
                .objects.filter(pk=actor.pk, is_active=True, job_status=True)
                .first()
            )
            if (
                actor is None
                or not verify_permission(
                    actor,
                    f"/api/v1/provisioning/requests/{record.pk}/reconcile",
                    "POST",
                )[0]
            ):
                raise ProvisioningError("回读纳管授权已失效")
            asset_ids = upsert_observed_assets(source, assets, observed_at)
            complete = (
                len(ids) == record.parameters["count"]
                and current.execution_status == "success"
            )
            locked.instance_ids = ids
            locked.asset_ids = asset_ids
            locked.status = "reconciled" if complete else "needs_reconciliation"
            locked.error_message = ""
            locked.save(
                update_fields=[
                    "instance_ids",
                    "asset_ids",
                    "status",
                    "error_message",
                    "updated_at",
                ]
            )
            ProvisioningRequest.objects.filter(pk=record.pk).update(
                inventory_status="success" if complete else "partial"
            )
            event(
                record,
                actor,
                "inventory_success" if complete else "inventory_partial",
                "已完成云资源回读纳管" if complete else "已纳管已知资源，剩余结果待核实",
                attempt.plan,
            )
            from .notifications import notify

            notify(
                record,
                "inventory_success" if complete else "inventory_partial",
                attempt.plan_id,
                "主机资产已回读纳管" if complete else "部分资源已纳管，请核实其余创建结果",
            )
    except Exception as exc:
        message = (
            str(exc) if isinstance(exc, ProvisioningError) else "云 API 回读失败，请检查读取权限与网络"
        )
        retrying = self.request.retries < 5
        with transaction.atomic():
            current = ProvisioningRequest.objects.select_for_update().get(pk=record.pk)
            if (
                current.state_generation != record.state_generation
                or not ProvisioningAttempt.objects.filter(
                    pk=attempt_id,
                    reconciliation_token=token,
                )
                .exclude(status="reconciled")
                .update(error_message=message)
            ):
                return
            ProvisioningRequest.objects.filter(pk=record.pk).update(
                inventory_status="pending" if retrying else "failed"
            )
        from .notifications import notify

        if not retrying:
            notify(record, "inventory_failed", attempt.plan_id, message)
        delays = [10, 30, 60, 120, 300]
        if self.request.retries < len(delays):
            raise self.retry(
                exc=ProvisioningError(message),
                countdown=delays[self.request.retries],
                args=[attempt_id, actor_id, token],
            )

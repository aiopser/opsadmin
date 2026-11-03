try:
    from celery import shared_task
except ImportError:

    def shared_task(*decorator_args, **decorator_kwargs):
        def wrapper(func):
            func.delay = func
            return func

        return wrapper


import shutil
import tempfile

from django.db import transaction
from django.utils import timezone

from .models import AssetHost, AssetSource, AssetSyncRecord, CloudImportPreview
from .sync_inventory import cloud_inventory_values, inventory_changes


@shared_task(name="cmdb.collect_cloud_import_preview")
def collect_cloud_import_preview(preview_id):
    from .cloud import CloudCollectionError, collect_cloud_assets
    from .sync_preview import cloud_asset_digest

    preview = (
        CloudImportPreview.objects.select_related("source")
        .filter(pk=preview_id)
        .first()
    )
    if preview is None or preview.status != "pending":
        return
    try:
        if preview.source.updated_at != preview.source_updated_at:
            raise CloudCollectionError("云账号配置已变化，请重新预览")
        assets = collect_cloud_assets(preview.source)
    except CloudCollectionError as exc:
        preview.status = "failed"
        preview.error_message = str(exc)[:255]
        preview.save(update_fields=["status", "error_message", "updated_at"])
        return
    except Exception:
        preview.status = "failed"
        preview.error_message = "云资产拉取失败，请检查区域、只读凭据及网络连通性"
        preview.save(update_fields=["status", "error_message", "updated_at"])
        return
    preview.assets = assets
    preview.digest = cloud_asset_digest(assets)
    preview.status = "ready"
    preview.save(update_fields=["assets", "digest", "status", "updated_at"])


def _value(item, *names, default=None):
    for name in names:
        if name in item and item[name] not in (None, ""):
            return item[name]
    return default


def _host_defaults(item, source, synced_at):
    public_cloud = (
        source.source_type == AssetSource.SourceType.CLOUD
        and source.cloud_provider
        in (AssetSource.CloudProvider.ALIYUN, AssetSource.CloudProvider.TENCENT)
    )
    os_family = _value(item, "os_family", "osFamily", default=AssetHost.OSFamily.LINUX)
    connection_type = _value(
        item,
        "connection_type",
        "connectionType",
        default=AssetHost.ConnectionType.WINRM
        if os_family == AssetHost.OSFamily.WINDOWS
        else AssetHost.ConnectionType.SSH,
    )
    return {
        "hostname": _value(item, "hostname", "name"),
        "internal_ip": _value(
            item, "internal_ip", "internalIp", "primary_ip", "primaryIp", "ip"
        ),
        "external_ip": _value(item, "external_ip", "externalIp", "public_ip"),
        "asset_type": AssetHost.AssetType.CLOUD_INSTANCE
        if public_cloud
        else _value(
            item, "asset_type", "assetType", default=AssetHost.AssetType.SERVER
        ),
        "os_family": _value(
            item, "os_family", "osFamily", default=AssetHost.OSFamily.LINUX
        ),
        "os_type": _value(item, "os_type", "osType", default=""),
        "image_name": _value(item, "image_name", "imageName", default=""),
        "cpu_cores": _value(item, "cpu_cores", "cpuCores", default=0),
        "memory_mb": _value(item, "memory_mb", "memoryMb", default=0),
        "system_disk_gb": _value(item, "system_disk_gb", "systemDiskGb", default=0),
        "data_disk_gb": _value(item, "data_disk_gb", "dataDiskGb", default=0),
        "disk_summary": _value(item, "disk_summary", "diskSummary", default={}),
        "region": _value(item, "region", default=""),
        "environment": _value(item, "environment", default=""),
        "status": _value(item, "status", default=AssetHost.HostStatus.ACTIVE),
        "connection_type": connection_type,
        "connection_port": _value(
            item,
            "connection_port",
            "connectionPort",
            default=5986 if connection_type == AssetHost.ConnectionType.WINRM else 22,
        ),
        "credential_ref_id": _value(item, "credential_ref", "credentialRef"),
        "owner_team": _value(item, "owner_team", "ownerTeam", default=""),
        "app_code": _value(item, "app_code", "appCode", default=""),
        "ansible_connection_vars": _value(
            item, "ansible_connection_vars", "ansibleConnectionVars", default={}
        ),
        "metadata": _value(item, "metadata", default={}),
        "asset_source": source,
        "source_type": source.source_type,
        "source_id": str(_value(item, "source_id", "sourceId", "id", default="")),
        "last_synced_at": synced_at,
    }


@shared_task(name="cmdb.sync_asset_source")
def sync_asset_source(record_id):
    started_at = timezone.now()
    if not AssetSyncRecord.objects.filter(pk=record_id, status="queued").update(
        status="running", started_at=started_at, updated_at=started_at
    ):
        return {"recordId": record_id, "claimed": False}
    record = AssetSyncRecord.objects.select_related("source").get(id=record_id)

    source = record.source
    created_count = updated_count = skipped_count = 0
    errors = []
    synced_at = timezone.now()
    changes = []
    if record.trigger == "scheduled":
        from .sync_automation import collect_scheduled_inventory

        if not collect_scheduled_inventory(record):
            return {"recordId": record.pk, "status": record.status}
    if not source.is_active:
        from .sync_automation import fail_sync

        fail_sync(record, "资产来源已停用，未写入资产")
        return {"recordId": record.pk, "status": record.status}
    synced_at = timezone.now()
    observed_at = record.observed_at or record.created_at
    for index, item in enumerate(record.payload or [], start=1):
        try:
            changed = True
            if not isinstance(item, dict):
                raise ValueError("asset item must be an object")
            defaults = _host_defaults(item, source, synced_at)
            if not defaults["hostname"] or not defaults["internal_ip"]:
                raise ValueError("hostname and internal_ip are required")
            source_id = defaults.pop("source_id")
            if source.source_type == AssetSource.SourceType.CLOUD and not source_id:
                raise ValueError("cloud assets require source_id")
            if source_id:
                lookup = {"asset_source": source, "source_id": source_id}
            else:
                lookup = {
                    "hostname": defaults["hostname"],
                    "internal_ip": defaults["internal_ip"],
                }
            with transaction.atomic():
                if source.source_type == AssetSource.SourceType.CLOUD:
                    current_source = AssetSource.objects.select_for_update().get(
                        pk=source.pk
                    )
                    if (
                        not AssetSyncRecord.objects.select_for_update()
                        .filter(pk=record.pk, status="running")
                        .first()
                    ):
                        return {"recordId": record.pk, "claimed": False}
                    if record.trigger == "scheduled":
                        from .sync_automation import (
                            fail_sync,
                            scheduled_sync_authorized,
                        )

                        if not scheduled_sync_authorized(current_source):
                            fail_sync(record, "周期同步授权已失效，未继续写入资产")
                            return {"recordId": record.pk, "status": record.status}
                    expected_revision = record.collection_scope.get("sourceUpdatedAt")
                    if not current_source.is_active or (
                        expected_revision
                        and current_source.updated_at.isoformat() != expected_revision
                    ):
                        raise ValueError("云账号配置已变化，请重新读取")
                    defaults.update(cloud_inventory_values(source, item))
                    defaults["last_observed_at"] = observed_at
                    host, created = AssetHost.objects.select_for_update().get_or_create(
                        **lookup, defaults=defaults
                    )
                    if not created:
                        if (
                            host.last_observed_at
                            and host.last_observed_at > observed_at
                        ):
                            skipped_count += 1
                            continue
                        # Cloud providers own inventory attributes, not the
                        # connection credentials or manually assigned business data.
                        updates = {
                            **cloud_inventory_values(source, item, host),
                            "last_synced_at": synced_at,
                            "last_observed_at": observed_at,
                        }
                        field_changes = inventory_changes(
                            host, cloud_inventory_values(source, item, host)
                        )
                        changed = bool(field_changes)
                        if field_changes:
                            changes.append(
                                {
                                    "hostId": host.pk,
                                    "sourceId": source_id,
                                    "hostname": host.hostname,
                                    "action": "update",
                                    "fields": field_changes,
                                }
                            )
                        for key, value in updates.items():
                            setattr(host, key, value)
                        host.save(update_fields=[*updates, "updated_at"])
                else:
                    if (
                        not AssetSyncRecord.objects.select_for_update()
                        .filter(pk=record.pk, status="running")
                        .first()
                    ):
                        return {"recordId": record.pk, "claimed": False}
                    _, created = AssetHost.objects.update_or_create(
                        **lookup,
                        defaults={**defaults, "source_id": source_id},
                    )
            if created:
                created_count += 1
                if source.source_type == AssetSource.SourceType.CLOUD:
                    changes.append(
                        {
                            "hostId": host.pk,
                            "sourceId": source_id,
                            "hostname": defaults["hostname"],
                            "action": "create",
                            "fields": [],
                        }
                    )
            elif changed:
                updated_count += 1
            else:
                skipped_count += 1
        except Exception as exc:
            skipped_count += 1
            from common.redaction import redact_text

            errors.append(redact_text(f"item {index}: {exc}"))

    finished_at = timezone.now()
    if errors:
        record.status = (
            AssetSyncRecord.Status.PARTIAL
            if created_count or updated_count
            else AssetSyncRecord.Status.FAILED
        )
    else:
        record.status = AssetSyncRecord.Status.SUCCEEDED
    record.finished_at = finished_at
    record.created_count = created_count
    record.updated_count = updated_count
    record.skipped_count = skipped_count
    record.error_message = "\n".join(errors)
    from common.redaction import redact_value

    record.changes = redact_value(changes)
    # Recovery owns the terminal result once it fences a timed-out worker.
    if not AssetSyncRecord.objects.filter(pk=record.pk, status="running").update(
        status=record.status,
        finished_at=finished_at,
        created_count=created_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
        error_message=record.error_message,
        changes=record.changes,
        updated_at=finished_at,
    ):
        return {"recordId": record.pk, "claimed": False}
    if record.status == "succeeded":
        AssetSource.objects.filter(id=source.id).update(last_synced_at=finished_at)
    from .sync_automation import queue_sync_failure_alert

    queue_sync_failure_alert(record)
    return {
        "recordId": record.id,
        "status": record.status,
        "created": created_count,
        "updated": updated_count,
        "skipped": skipped_count,
    }


@shared_task(name="cmdb.schedule_cloud_syncs")
def schedule_cloud_syncs():
    from .sync_automation import queue_due_cloud_syncs

    return {"queued": queue_due_cloud_syncs()}


@shared_task(name="cmdb.discover_host_facts")
def discover_host_facts(host_id, actor_id):
    """Collect hardware/OS facts from a host via Ansible setup module."""
    host = AssetHost.objects.select_related("credential_ref").get(id=host_id)
    credential = host.credential_ref
    if not credential:
        return {"hostId": host_id, "status": "skipped", "reason": "no credential"}

    private_data_dir = ""
    try:
        from django.contrib.auth import get_user_model
        from .execution import execute_asset_module

        actor = get_user_model().objects.get(pk=actor_id)
        facts = {}

        def collect(event):
            if event.event_type == "host_ok" and isinstance(
                event.result.get("ansible_facts"), dict
            ):
                facts.update(event.result["ansible_facts"])

        result = execute_asset_module(
            actor=actor,
            host_id=host_id,
            module="ansible.windows.setup"
            if host.connection_type == "winrm"
            else "ansible.builtin.setup",
            module_args="gather_subset=!all,!min,hardware,network",
            on_event=collect,
        )
        if result.status != "success":
            return {
                "hostId": host_id,
                "status": "failed",
                "reason": "setup module failed",
            }

        if not facts:
            return {
                "hostId": host_id,
                "status": "failed",
                "reason": "no facts collected",
            }

        # Map facts to model fields
        update_fields = {}
        cpu = facts.get("ansible_processor_vcpus") or facts.get(
            "ansible_processor_count", 0
        )
        if cpu:
            update_fields["cpu_cores"] = int(cpu)

        mem_mb = facts.get("ansible_memtotal_mb")
        if mem_mb:
            update_fields["memory_mb"] = int(mem_mb)

        os_type = ""
        distro = facts.get("ansible_distribution", "")
        version = facts.get("ansible_distribution_version", "")
        if distro:
            os_type = f"{distro} {version}".strip()
        if os_type:
            update_fields["os_type"] = os_type[:64]

        # Disk: use mount info or block devices
        devices = facts.get("ansible_devices", {})
        if devices:
            total_gb = 0
            for dev_info in devices.values():
                size_str = dev_info.get("size", "0 GB")
                try:
                    size_val = float(
                        size_str.replace("GB", "").replace("TB", "000").strip()
                    )
                    total_gb += int(size_val)
                except (ValueError, AttributeError):
                    pass
            if total_gb > 0 and not host.system_disk_gb:
                update_fields["system_disk_gb"] = total_gb

        update_fields["last_discovered_at"] = timezone.now()
        AssetHost.objects.filter(id=host_id).update(**update_fields)
        return {
            "hostId": host_id,
            "status": "success",
            "fields": list(update_fields.keys()),
        }

    except Exception as exc:
        return {"hostId": host_id, "status": "error", "reason": str(exc)}
    finally:
        if private_data_dir:
            shutil.rmtree(private_data_dir, ignore_errors=True)


@shared_task(name="cmdb.execute_asset_probe")
def execute_asset_probe(probe_id, attempt):
    """Claim and run a queued AssetProbe on this worker.

    The compare-and-set claim fences duplicate deliveries (republished
    messages racing the original). Probe failures are business results and
    are recorded on the row instead of raising, so the queue does not retry
    them.
    """
    from .models import AssetProbe

    claimed = AssetProbe.objects.filter(
        pk=probe_id,
        attempt=attempt,
        status=AssetProbe.Status.PENDING,
    ).update(status=AssetProbe.Status.RUNNING, updated_at=timezone.now())
    if not claimed:
        return {"probeId": probe_id, "claimed": False}
    probe = AssetProbe.objects.select_related("triggered_by").get(pk=probe_id)
    if probe.triggered_by_id is None:
        _finish_probe(probe, AssetProbe.Status.FAILED, error="probe owner was removed")
        return {"probeId": probe_id, "status": AssetProbe.Status.FAILED}
    try:
        from .execution import execute_asset_module

        result = execute_asset_module(
            actor=probe.triggered_by,
            host_id=probe.host_id,
            module=probe.module,
            module_args=probe.module_args,
            timeout=probe.timeout_seconds,
            on_event=lambda event: None,
        )
    except Exception as exc:
        try:
            from celery.exceptions import SoftTimeLimitExceeded

            timed_out = isinstance(exc, SoftTimeLimitExceeded)
        except ImportError:
            timed_out = False
        error = "probe timed out" if timed_out else str(exc)[:512]
        _finish_probe(probe, AssetProbe.Status.FAILED, error=error)
        return {"probeId": probe_id, "status": AssetProbe.Status.FAILED}
    success = result.status == "success"
    _finish_probe(
        probe,
        AssetProbe.Status.SUCCESS if success else AssetProbe.Status.FAILED,
        result={
            "runnerStatus": result.status,
            "returnCode": result.return_code,
            "error": result.error or "",
        },
        error="" if success else (result.error or "probe failed"),
    )
    return {"probeId": probe_id, "status": "success" if success else "failed"}


def _finish_probe(probe, status, *, result=None, error=""):
    probe.status = status
    probe.result = result or {}
    probe.error = error
    probe.save(update_fields=["status", "result", "error", "updated_at"])


@shared_task(name="cmdb.recover_stale_asset_probes")
def recover_stale_asset_probes():
    from .probes import recover_stale_probes

    return {"recovered": recover_stale_probes()}

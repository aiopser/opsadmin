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

from .models import AssetHost, AssetSource, AssetSyncRecord


def _value(item, *names, default=None):
    for name in names:
        if name in item and item[name] not in (None, ""):
            return item[name]
    return default


def _host_defaults(item, source, synced_at):
    return {
        "hostname": _value(item, "hostname", "name"),
        "primary_ip": _value(item, "primary_ip", "primaryIp", "ip"),
        "asset_type": _value(
            item, "asset_type", "assetType", default=AssetHost.AssetType.SERVER
        ),
        "os_family": _value(
            item, "os_family", "osFamily", default=AssetHost.OSFamily.LINUX
        ),
        "os_type": _value(item, "os_type", "osType", default=""),
        "image_name": _value(item, "image_name", "imageName", default=""),
        "environment": _value(item, "environment", default=""),
        "status": _value(item, "status", default=AssetHost.HostStatus.ACTIVE),
        "connection_type": _value(
            item,
            "connection_type",
            "connectionType",
            default=AssetHost.ConnectionType.SSH,
        ),
        "connection_port": _value(
            item, "connection_port", "connectionPort", default=22
        ),
        "credential_ref_id": _value(item, "credential_ref", "credentialRef"),
        "service_node_id": _value(item, "service_node", "serviceNode"),
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
    record = AssetSyncRecord.objects.select_related("source").get(id=record_id)
    started_at = timezone.now()
    record.status = AssetSyncRecord.Status.RUNNING
    record.started_at = started_at
    record.save(update_fields=["status", "started_at", "updated_at"])

    source = record.source
    created_count = updated_count = skipped_count = 0
    errors = []
    synced_at = timezone.now()
    for index, item in enumerate(record.payload or [], start=1):
        try:
            if not isinstance(item, dict):
                raise ValueError("asset item must be an object")
            defaults = _host_defaults(item, source, synced_at)
            if not defaults["hostname"] or not defaults["primary_ip"]:
                raise ValueError("hostname and primary_ip are required")
            source_id = defaults.pop("source_id")
            if source_id:
                lookup = {"asset_source": source, "source_id": source_id}
            else:
                lookup = {
                    "hostname": defaults["hostname"],
                    "primary_ip": defaults["primary_ip"],
                }
            with transaction.atomic():
                _, created = AssetHost.objects.update_or_create(
                    **lookup,
                    defaults={**defaults, "source_id": source_id},
                )
            if created:
                created_count += 1
            else:
                updated_count += 1
        except Exception as exc:
            skipped_count += 1
            errors.append(f"item {index}: {exc}")

    finished_at = timezone.now()
    record.status = (
        AssetSyncRecord.Status.FAILED
        if skipped_count and not (created_count or updated_count)
        else AssetSyncRecord.Status.SUCCEEDED
    )
    record.finished_at = finished_at
    record.created_count = created_count
    record.updated_count = updated_count
    record.skipped_count = skipped_count
    record.error_message = "\n".join(errors)
    record.save(
        update_fields=[
            "status",
            "finished_at",
            "created_count",
            "updated_count",
            "skipped_count",
            "error_message",
            "updated_at",
        ]
    )
    AssetSource.objects.filter(id=source.id).update(last_synced_at=finished_at)
    return {
        "recordId": record.id,
        "status": record.status,
        "created": created_count,
        "updated": updated_count,
        "skipped": skipped_count,
    }


@shared_task(name="cmdb.discover_host_facts")
def discover_host_facts(host_id, actor_id):
    """Collect hardware/OS facts from a host via Ansible setup module."""
    host = AssetHost.objects.select_related("credential_ref", "default_gateway").get(
        id=host_id
    )
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
            if event.event_type == "host_ok" and isinstance(event.result.get("ansible_facts"), dict):
                facts.update(event.result["ansible_facts"])

        result = execute_asset_module(
            actor=actor, host_id=host_id, module="ansible.windows.setup" if host.connection_type == "winrm" else "ansible.builtin.setup",
            module_args="gather_subset=!all,!min,hardware,network", on_event=collect,
        )
        if result.status != "success":
            return {"hostId": host_id, "status": "failed", "reason": "setup module failed"}

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

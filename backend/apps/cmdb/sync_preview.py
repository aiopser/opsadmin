"""Read-only preview of an asset-source import. No missing hosts are removed."""

import hashlib
import json

from .models import AssetHost, AssetSource
from .sync_inventory import cloud_inventory_values, inventory_changes


def cloud_asset_digest(assets):
    """Stable across provider response ordering, sensitive to any asset change."""
    rows = sorted(
        json.dumps(asset, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        for asset in assets
    )
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()


def preview_asset_sync(source, assets):
    if not isinstance(assets, list) or len(assets) > 1000:
        raise ValueError("assets must be a JSON array of at most 1000 items")

    rows = []
    seen = set()
    cloud_hosts = {}
    if source.source_type == AssetSource.SourceType.CLOUD:
        source_ids = [str(item.get("source_id") or item.get("sourceId") or item.get("id") or "") for item in assets if isinstance(item, dict)]
        cloud_hosts = {host.source_id: host for host in AssetHost.objects.filter(asset_source=source, source_id__in=source_ids)}
    for index, item in enumerate(assets, start=1):
        changes = []
        values = {}
        if not isinstance(item, dict):
            rows.append({"index": index, "hostname": "", "internalIp": "", "sourceId": "", "action": "invalid", "reason": "主机必须是对象", "changes": [], "specs": {}})
            continue
        hostname = str(item.get("hostname") or item.get("name") or "").strip()
        ip = str(
            item.get("internal_ip")
            or item.get("internalIp")
            or item.get("primary_ip")
            or item.get("primaryIp")
            or item.get("ip")
            or ""
        ).strip()
        source_id = str(
            item.get("source_id") or item.get("sourceId") or item.get("id") or ""
        ).strip()
        key = ("source", source_id) if source_id else ("host", hostname, ip)
        if source.source_type == AssetSource.SourceType.CLOUD and not source_id:
            action, reason = "invalid", "云资产必须提供实例 ID"
        elif not hostname or not ip:
            action, reason = "invalid", "主机名和内网 IP 必填"
        elif key in seen:
            action, reason = "invalid", "本次清单中的匹配键重复"
        else:
            seen.add(key)
            if source.source_type == AssetSource.SourceType.CLOUD:
                host = cloud_hosts.get(source_id)
            elif source_id:
                host = AssetHost.objects.filter(asset_source=source, source_id=source_id).first()
            else:
                host = AssetHost.objects.filter(hostname=hostname, internal_ip=ip).first()
            action, reason = ("update", "") if host else ("create", "")
            if source.source_type == AssetSource.SourceType.CLOUD:
                try:
                    values = cloud_inventory_values(source, item, host)
                    changes = inventory_changes(host, values) if host else []
                    if host and not changes:
                        action, reason = "unchanged", "与当前资产一致，无需同步"
                except (ValueError, TypeError):
                    action, reason = "invalid", "主机规格格式无效"
        rows.append(
            {
                "index": index,
                "hostname": hostname,
                "internalIp": ip,
                "sourceId": source_id,
                "action": action,
                "reason": reason,
                "changes": changes,
                "specs": {
                    key: values[key] for key in ("cpu_cores", "memory_mb", "system_disk_gb", "data_disk_gb", "region")
                    if key in values and values[key] is not None
                },
            }
        )
    return {
        "total": len(rows),
        "create": sum(row["action"] == "create" for row in rows),
        "update": sum(row["action"] == "update" for row in rows),
        "invalid": sum(row["action"] == "invalid" for row in rows),
        "unchanged": sum(row["action"] == "unchanged" for row in rows),
        "rows": rows,
    }

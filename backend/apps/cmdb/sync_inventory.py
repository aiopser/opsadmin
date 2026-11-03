"""Cloud-owned inventory fields shared by preview and synchronization."""

import re

from .models import AssetSource


INVENTORY_FIELDS = {
    "hostname": ("主机名称", ("hostname", "name")),
    "internal_ip": (
        "内网 IP",
        ("internal_ip", "internalIp", "primary_ip", "primaryIp", "ip"),
    ),
    "external_ip": ("外网 IP", ("external_ip", "externalIp", "public_ip")),
    "asset_type": ("资产类型", ("asset_type", "assetType")),
    "os_family": ("操作系统类型", ("os_family", "osFamily")),
    "os_type": ("操作系统", ("os_type", "osType")),
    "image_name": ("镜像", ("image_name", "imageName")),
    "cpu_cores": ("CPU 核数", ("cpu_cores", "cpuCores")),
    "memory_mb": ("内存（MiB）", ("memory_mb", "memoryMb")),
    "system_disk_gb": ("系统盘（GiB）", ("system_disk_gb", "systemDiskGb")),
    "data_disk_gb": ("数据盘（GiB）", ("data_disk_gb", "dataDiskGb")),
    "disk_summary": ("磁盘明细", ("disk_summary", "diskSummary")),
    "region": ("地域", ("region",)),
    "cloud_state": ("云运行状态", ("cloud_state", "cloudState")),
}
INTEGER_FIELDS = {"cpu_cores", "memory_mb", "system_disk_gb", "data_disk_gb"}


def cloud_inventory_values(source, item, host=None):
    values = {}
    for field, (_, aliases) in INVENTORY_FIELDS.items():
        for alias in aliases:
            if alias not in item or item[alias] is None:
                continue
            value = item[alias]
            if field in INTEGER_FIELDS:
                if isinstance(value, bool) or not re.fullmatch(r"\d+", str(value).strip()):
                    raise ValueError(f"{field} 必须为非负整数")
                value = int(value)
                if value < 0:
                    raise ValueError(f"{field} 不可为负数")
            if field == "external_ip":
                value = value or None
            values[field] = value
            break
    if source.cloud_provider in (
        AssetSource.CloudProvider.ALIYUN,
        AssetSource.CloudProvider.TENCENT,
    ):
        values["asset_type"] = "cloud_instance"
    elif source.cloud_provider in {"vmware", "openstack", "pve"}:
        values["asset_type"] = "virtual_machine"
    metadata = item.get("metadata")
    if isinstance(metadata, dict) and metadata:
        if not values.get("region") and metadata.get("region"):
            values["region"] = metadata["region"]
        values["metadata"] = {**(getattr(host, "metadata", None) or {}), **metadata}
    return values


def inventory_changes(host, values):
    return [
        {
            "field": field,
            "label": INVENTORY_FIELDS[field][0]
            if field in INVENTORY_FIELDS
            else "云平台信息",
            "before": getattr(host, field),
            "after": value,
        }
        for field, value in values.items()
        if getattr(host, field) != value
    ]

"""Pure validation for the create-only delivery contract."""
import hashlib
import json
import re


class ProvisioningError(ValueError):
    pass


RESOURCE_TYPES = {"aliyun": "alicloud_instance", "tencent": "tencentcloud_instance"}
PARAMETERS = {
    "count",
    "name",
    "image_id",
    "instance_type",
    "zone",
    "vpc_id",
    "subnet_id",
    "security_group_ids",
    "system_disk_gb",
}


def canonical_digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def validate_inputs(parameters, provider):
    if provider not in RESOURCE_TYPES or not isinstance(parameters, dict):
        raise ProvisioningError("仅支持阿里云 ECS、腾讯云 CVM 的参数对象")
    if set(parameters) - PARAMETERS:
        raise ProvisioningError("存在不支持的申请参数")
    count = parameters.get("count")
    if type(count) is not int or not 1 <= count <= 20:
        raise ProvisioningError("每次申请数量必须为 1 至 20 台")
    for key in PARAMETERS - {"count", "security_group_ids", "system_disk_gb"}:
        value = parameters.get(key)
        if not isinstance(value, str) or not re.fullmatch(
            r"[\w.\-\u4e00-\u9fff]{1,128}", value
        ):
            raise ProvisioningError(f"请填写有效的 {key}")
    groups = parameters.get("security_group_ids")
    if (
        not isinstance(groups, list)
        or not 1 <= len(groups) <= 5
        or any(
            not isinstance(item, str) or not re.fullmatch(r"[\w-]{1,128}", item)
            for item in groups
        )
    ):
        raise ProvisioningError("请选择 1 至 5 个安全组")
    disk = parameters.get("system_disk_gb")
    if type(disk) is not int or not 20 <= disk <= 2048:
        raise ProvisioningError("系统盘大小必须为 20 至 2048 GiB")
    return dict(parameters)


def summarize_plan(plan, provider):
    if not isinstance(plan, dict) or provider not in RESOURCE_TYPES:
        raise ProvisioningError("无效的变更计划")
    rows = []
    for resource in plan.get("resource_changes", []):
        if resource.get("mode") == "data":
            continue
        if (
            resource.get("change", {}).get("actions") != ["create"]
            or resource.get("type") != RESOURCE_TYPES[provider]
        ):
            raise ProvisioningError("首期仅允许新建主机，禁止修改、删除或替换资源")
        rows.append(
            {
                "address": resource["address"],
                "type": resource["type"],
                "action": "create",
            }
        )
    if not 1 <= len(rows) <= 20:
        raise ProvisioningError("计划必须包含 1 至 20 台新增主机")
    return rows


def validate_resource_scope(record):
    constraints = record.version.constraints
    if constraints.get("schemaVersion") == 2:
        from .catalog.policy import validate_selectors

        validate_selectors(constraints)
        if record.credential.source_id not in constraints["selectors"][
            "sourceIds"
        ] or record.region not in constraints.get("regions", []):
            raise ProvisioningError("云账号或地域不在模板允许范围内")
        return
    networks = constraints.get("networks", [])
    values = record.parameters
    matches = [
        item
        for item in networks
        if isinstance(item, dict)
        and item.get("source_id") == record.credential.source_id
        and item.get("region") == record.region
        and all(
            item.get(key) == values.get(key) for key in ["vpc_id", "subnet_id", "zone"]
        )
    ]
    if not matches or not any(
        set(values["security_group_ids"]).issubset(
            set(item.get("security_group_ids", []))
        )
        for item in matches
    ):
        raise ProvisioningError("网络与安全组不在此云账号的模板授权范围内")
    for key in ["image_id", "instance_type"]:
        if values[key] not in constraints.get(f"allowed_{key}s", []):
            raise ProvisioningError(f"{key} 不在资源模板允许范围内")

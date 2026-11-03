from django.utils import timezone

from ..contracts import ProvisioningError, canonical_digest
from .service import list_catalog


def _selected(record, actor, kind, identity):
    query = {
        "kind": kind,
        "versionId": record.version_id,
        "credentialId": record.credential_id,
        "region": record.region,
        "resourceId": identity,
        "zone": record.parameters["zone"],
        "vpcId": record.parameters["vpc_id"],
        "instanceType": record.parameters["instance_type"],
    }
    for _ in range(5):
        page = list_catalog(actor, query, refresh=True)
        for row in page["items"]:
            if row["id"] == identity and (
                kind != "availability"
                or row["attributes"].get("zone") == record.parameters["zone"]
            ):
                if row.get("available") is False:
                    raise ProvisioningError(f"资源 {identity} 当前不可用，请重新选择")
                return row
        if not page["hasMore"]:
            break
        query["cursor"] = page["nextCursor"]
    raise ProvisioningError(f"无法在授权范围内校验 {kind}：{identity}，请缩小模板范围后重新选择")


def resolve_request_resources(record, actor, *, refresh=True):
    # Published legacy allowlists retain their original contract.
    if record.version.constraints.get("schemaVersion") != 2:
        return {}
    values = record.parameters
    result = {
        kind: _selected(record, actor, kind, values[field])
        for kind, field in [
            ("zones", "zone"),
            ("vpcs", "vpc_id"),
            ("subnets", "subnet_id"),
            ("images", "image_id"),
            ("instance_types", "instance_type"),
            ("availability", "instance_type"),
        ]
    }
    result["security_groups"] = [
        _selected(record, actor, "security_groups", group)
        for group in values["security_group_ids"]
    ]
    subnet = result["subnets"]["attributes"]
    if subnet.get("vpcId") != values["vpc_id"] or subnet.get("zone") != values["zone"]:
        raise ProvisioningError("子网与所选 VPC 或可用区不一致")
    if any(
        row["attributes"].get("vpcId") not in {None, "", values["vpc_id"]}
        for row in result["security_groups"]
    ):
        raise ProvisioningError("安全组不属于所选 VPC")
    if subnet.get("remaining") is not None and subnet["remaining"] < values["count"]:
        raise ProvisioningError("子网可用 IP 数不足")
    image_arch = result["images"]["attributes"].get("architecture")
    type_arch = result["instance_types"]["attributes"].get("architecture")
    if image_arch and type_arch and image_arch != type_arch:
        raise ProvisioningError("镜像与实例规格架构不兼容")
    if (
        result["images"].get("available") is not True
        or result["availability"].get("available") is not True
    ):
        raise ProvisioningError("镜像或规格的可用性尚未确认，请稍后重试")
    result["policyDigest"] = canonical_digest(record.version.constraints)
    result["observedAt"] = timezone.now().isoformat()
    return result


def validate_resolved_resources(record, actor):
    resolve_request_resources(record, actor, refresh=True)

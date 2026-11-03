from ..contracts import ProvisioningError


def validate_selectors(constraints):
    if constraints.get("schemaVersion") != 2:
        return
    selectors = constraints.get("selectors")
    allowed = {
        "sourceIds",
        "networkTags",
        "securityGroupTags",
        "imageSources",
        "imageOs",
        "imageNamePrefix",
        "cpuMin",
        "cpuMax",
        "memoryMinMiB",
        "memoryMaxMiB",
        "families",
    }
    if not isinstance(selectors, dict) or set(selectors) - allowed:
        raise ProvisioningError("资源发现规则包含不支持的字段")
    sources = selectors.get("sourceIds")
    if (
        not isinstance(sources, list)
        or not sources
        or len(sources) > 50
        or any(type(i) is not int or i < 1 for i in sources)
    ):
        raise ProvisioningError("资源发现规则必须限定云账号")
    for key in ["networkTags", "securityGroupTags"]:
        tags = selectors.get(key, {})
        if (
            not isinstance(tags, dict)
            or len(tags) > 10
            or any(
                not isinstance(k, str)
                or not isinstance(v, str)
                or not 1 <= len(k) <= 128
                or len(v) > 256
                for k, v in tags.items()
            )
        ):
            raise ProvisioningError("标签规则无效")
    for key in ["imageSources", "imageOs", "families"]:
        values = selectors.get(key, [])
        if (
            not isinstance(values, list)
            or len(values) > 50
            or any(not isinstance(v, str) or not 1 <= len(v) <= 128 for v in values)
        ):
            raise ProvisioningError("镜像或规格规则无效")
    if (
        not isinstance(selectors.get("imageNamePrefix", ""), str)
        or len(selectors.get("imageNamePrefix", "")) > 128
    ):
        raise ProvisioningError("镜像名称前缀无效")
    for low, high in [("cpuMin", "cpuMax"), ("memoryMinMiB", "memoryMaxMiB")]:
        for key in [low, high]:
            if key in selectors and (
                type(selectors[key]) is not int or not 1 <= selectors[key] <= 1048576
            ):
                raise ProvisioningError("规格范围无效")
        if selectors.get(low, 1) > selectors.get(high, 1048576):
            raise ProvisioningError("规格范围上下限不一致")


def permitted(row, kind, constraints, source_id, region):
    if constraints.get("schemaVersion") == 2:
        rule = constraints["selectors"]
        if source_id not in rule["sourceIds"]:
            return False
        attrs = row["attributes"]
        tags = (
            rule.get(
                "securityGroupTags" if kind == "security_groups" else "networkTags", {}
            )
            if kind in {"vpcs", "subnets", "security_groups"}
            else {}
        )
        if any(row.get("_tags", {}).get(key) != value for key, value in tags.items()):
            return False
        if kind == "images":
            return (
                (
                    not rule.get("imageSources")
                    or attrs.get("source") in rule["imageSources"]
                )
                and (not rule.get("imageOs") or attrs.get("os") in rule["imageOs"])
                and row["name"].startswith(rule.get("imageNamePrefix", ""))
            )
        if kind == "instance_types":
            if rule.get("families") and attrs.get("family") not in rule["families"]:
                return False
            for attribute, low, high in [
                ("cpu", "cpuMin", "cpuMax"),
                ("memoryMiB", "memoryMinMiB", "memoryMaxMiB"),
            ]:
                if (low in rule or high in rule) and (
                    attrs.get(attribute) is None
                    or not rule.get(low, 0)
                    <= attrs[attribute]
                    <= rule.get(high, 1048576)
                ):
                    return False
        return True
    if kind in {"images", "instance_types"}:
        key = "allowed_image_ids" if kind == "images" else "allowed_instance_types"
        return row["id"] in constraints.get(key, [])
    networks = [
        n
        for n in constraints.get("networks", [])
        if n.get("source_id") == source_id and n.get("region") == region
    ]
    field = {
        "zones": "zone",
        "vpcs": "vpc_id",
        "subnets": "subnet_id",
        "security_groups": "security_group_ids",
    }.get(kind)
    if field:
        return any(
            row["id"] in n.get(field, [])
            if field == "security_group_ids"
            else row["id"] == n.get(field)
            for n in networks
        )
    return True

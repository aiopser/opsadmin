"""Bounded ECS/VPC Describe APIs; no cloud writer is imported here."""
from .types import item, tags_of


def client_factory(credentials, region, service):
    from alibabacloud_tea_openapi.models import Config

    if service == "vpc":
        from alibabacloud_vpc20160428.client import Client
    else:
        from alibabacloud_ecs20140526.client import Client
    return Client(
        Config(
            access_key_id=credentials["access_key_id"],
            access_key_secret=credentials["access_key_secret"],
            endpoint=f"{service}.{region}.aliyuncs.com",
            connect_timeout=3000,
            read_timeout=5000,
        )
    )


def normalize(kind, row):
    tags = tags_of(
        row.get("Tags", {}).get("Tag", []),
        "Key" if kind in {"vpcs", "subnets"} else "TagKey",
        "Value" if kind in {"vpcs", "subnets"} else "TagValue",
    )
    if kind == "zones":
        return item(row["ZoneId"], row.get("LocalName"))
    if kind == "images":
        status = row.get("Status")
        return item(
            row["ImageId"],
            row.get("ImageName"),
            available=True
            if status == "Available"
            else False
            if status in {"UnAvailable", "Creating", "CreateFailed"}
            else None,
            reason="镜像尚不可用" if status and status != "Available" else "",
            os=row.get("OSType"),
            architecture=row.get("Architecture"),
            source=row.get("ImageOwnerAlias"),
        )
    if kind == "instance_types":
        return item(
            row["InstanceTypeId"],
            cpu=row.get("CpuCoreCount"),
            memoryMiB=int(row["MemorySize"] * 1024)
            if row.get("MemorySize") is not None
            else None,
            architecture=row.get("CpuArchitecture"),
            family=row.get("InstanceTypeFamily"),
        )
    if kind == "vpcs":
        return item(
            row["VpcId"], row.get("VpcName"), tags=tags, cidr=row.get("CidrBlock")
        )
    if kind == "subnets":
        return item(
            row["VSwitchId"],
            row.get("VSwitchName"),
            tags=tags,
            vpcId=row.get("VpcId"),
            zone=row.get("ZoneId"),
            cidr=row.get("CidrBlock"),
            remaining=row.get("AvailableIpAddressCount"),
        )
    return item(
        row["SecurityGroupId"],
        row.get("SecurityGroupName"),
        tags=tags,
        vpcId=row.get("VpcId"),
    )


def fetch_page(credentials, query, token):
    from alibabacloud_ecs20140526 import models as ecs
    from alibabacloud_vpc20160428 import models as vpc

    kind = query.kind
    page_size = (
        min(query.page_size, 50) if kind in {"vpcs", "subnets"} else query.page_size
    )
    if kind == "availability":
        request = ecs.DescribeAvailableResourceRequest(
            region_id=query.region,
            zone_id=query.zone or None,
            instance_type=query.instance_type or None,
            destination_resource="InstanceType",
            instance_charge_type="PostPaid",
            network_category="vpc",
        )
        body = (
            client_factory(credentials, query.region, "ecs")
            .describe_available_resource(request)
            .body.to_map()
        )
        rows = []
        for zone in body.get("AvailableZones", {}).get("AvailableZone", []):
            for resources in zone.get("AvailableResources", {}).get(
                "AvailableResource", []
            ):
                for resource in resources.get("SupportedResources", {}).get(
                    "SupportedResource", []
                ):
                    status = resource.get("Status")
                    rows.append(
                        item(
                            resource.get("Value", query.instance_type),
                            available=True
                            if status == "Available"
                            else False
                            if status == "SoldOut"
                            else None,
                            reason="当前可用区售罄" if status == "SoldOut" else "",
                            zone=zone.get("ZoneId"),
                            remaining=None,
                        )
                    )
        offset = int(token or 0)
        return {
            "items": rows[offset : offset + query.page_size],
            "next": str(offset + query.page_size)
            if offset + query.page_size < len(rows)
            else None,
            "warnings": ["可用性不是库存预留，精确余量未知"],
        }
    if kind == "quota":
        client_factory(credentials, query.region, "ecs").describe_account_attributes(
            ecs.DescribeAccountAttributesRequest(region_id=query.region)
        )
        return {
            "items": [item("instances", "实例配额", remaining=None, unit="台")],
            "next": None,
            "warnings": ["账号属性不代表当前规格的可分配余量，剩余台数未知"],
        }
    page = int(token or 1) if kind not in {"instance_types", "security_groups"} else 1
    base = {"region_id": query.region}
    if kind == "zones":
        method, request, service = (
            "describe_zones",
            ecs.DescribeZonesRequest(**base),
            "ecs",
        )
        path = ("Zones", "Zone")
    elif kind == "images":
        method, request, service = (
            "describe_images",
            ecs.DescribeImagesRequest(
                **base,
                page_number=page,
                page_size=page_size,
                image_id=query.resource_id or None,
                instance_type=query.instance_type or None,
            ),
            "ecs",
        )
        path = ("Images", "Image")
    elif kind == "instance_types":
        method, request, service = (
            "describe_instance_types",
            ecs.DescribeInstanceTypesRequest(
                max_results=query.page_size,
                next_token=token,
                instance_types=[query.resource_id] if query.resource_id else None,
            ),
            "ecs",
        )
        path = ("InstanceTypes", "InstanceType")
    elif kind == "vpcs":
        method, request, service = (
            "describe_vpcs",
            vpc.DescribeVpcsRequest(
                **base,
                page_number=page,
                page_size=page_size,
                vpc_id=query.resource_id or None,
            ),
            "vpc",
        )
        path = ("Vpcs", "Vpc")
    elif kind == "subnets":
        method, request, service = (
            "describe_vswitches",
            vpc.DescribeVSwitchesRequest(
                **base,
                page_number=page,
                page_size=page_size,
                vpc_id=query.vpc_id or None,
                zone_id=query.zone or None,
                v_switch_id=query.resource_id or None,
            ),
            "vpc",
        )
        path = ("VSwitches", "VSwitch")
    else:
        method, request, service = (
            "describe_security_groups",
            ecs.DescribeSecurityGroupsRequest(
                **base,
                max_results=query.page_size,
                next_token=token,
                vpc_id=query.vpc_id or None,
                security_group_id=query.resource_id or None,
            ),
            "ecs",
        )
        path = ("SecurityGroups", "SecurityGroup")
    body = getattr(client_factory(credentials, query.region, service), method)(
        request
    ).body.to_map()
    rows = body.get(path[0], {}).get(path[1], [])
    if kind in {"instance_types", "security_groups"}:
        next_page = body.get("NextToken") or None
    elif kind == "zones":
        # Zones returns a small finite collection; locally paginate without truncation.
        offset = (page - 1) * query.page_size
        next_page = str(page + 1) if offset + query.page_size < len(rows) else None
        rows = rows[offset : offset + query.page_size]
    else:
        next_page = (
            str(page + 1) if page * page_size < body.get("TotalCount", 0) else None
        )
    return {"items": [normalize(kind, row) for row in rows], "next": next_page}

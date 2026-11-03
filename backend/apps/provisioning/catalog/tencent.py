import json

from .types import item, tags_of


def client_factory(credentials, region, service):
    from tencentcloud.common.credential import Credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile

    if service == "vpc":
        from tencentcloud.vpc.v20170312.vpc_client import VpcClient as Client
    else:
        from tencentcloud.cvm.v20170312.cvm_client import CvmClient as Client
    return Client(
        Credential(credentials["access_key_id"], credentials["access_key_secret"]),
        region,
        ClientProfile(httpProfile=HttpProfile(reqTimeout=5)),
    )


def normalize(kind, row):
    tags = tags_of(row.get("TagSet", []))
    if kind == "zones":
        status = row.get("ZoneState")
        return item(
            row["Zone"],
            row.get("ZoneName"),
            available=True
            if status == "AVAILABLE"
            else False
            if status == "UNAVAILABLE"
            else None,
        )
    if kind == "images":
        status = row.get("ImageState")
        os_name = str(row.get("OsName") or row.get("Platform") or "").lower()
        return item(
            row["ImageId"],
            row.get("ImageName"),
            available=True
            if status == "NORMAL"
            else False
            if status in {"CREATING", "CREATEFAILED", "USING", "SYNCING", "IMPORTING"}
            else None,
            os="windows" if "windows" in os_name else "linux" if os_name else None,
            architecture=row.get("Architecture"),
            source=row.get("ImageType"),
        )
    if kind == "instance_types":
        return item(
            row["InstanceType"],
            cpu=row.get("CPU"),
            memoryMiB=int(row["Memory"] * 1024)
            if row.get("Memory") is not None
            else None,
            family=row.get("InstanceFamily"),
            zone=row.get("Zone"),
            architecture=None,
        )
    if kind == "vpcs":
        return item(
            row["VpcId"], row.get("VpcName"), tags=tags, cidr=row.get("CidrBlock")
        )
    if kind == "subnets":
        return item(
            row["SubnetId"],
            row.get("SubnetName"),
            tags=tags,
            vpcId=row.get("VpcId"),
            zone=row.get("Zone"),
            cidr=row.get("CidrBlock"),
            remaining=row.get("AvailableIpAddressCount"),
        )
    # Tencent security groups are region/project scoped, not owned by a single VPC.
    return item(
        row["SecurityGroupId"], row.get("SecurityGroupName"), tags=tags, vpcId=None
    )


def fetch_page(credentials, query, token):
    from tencentcloud.cvm.v20170312 import models as cvm
    from tencentcloud.vpc.v20170312 import models as vpc

    kind = query.kind
    service = "vpc" if kind in {"vpcs", "subnets", "security_groups"} else "cvm"
    methods = {
        "zones": ("DescribeZones", "ZoneSet"),
        "images": ("DescribeImages", "ImageSet"),
        "instance_types": ("DescribeInstanceTypeConfigs", "InstanceTypeConfigSet"),
        "vpcs": ("DescribeVpcs", "VpcSet"),
        "subnets": ("DescribeSubnets", "SubnetSet"),
        "security_groups": ("DescribeSecurityGroups", "SecurityGroupSet"),
        "availability": ("DescribeZoneInstanceConfigInfos", "InstanceTypeQuotaSet"),
        "quota": ("DescribeAccountQuota", "AccountQuotaOverview"),
    }
    method, collection = methods[kind]
    request = getattr(vpc if service == "vpc" else cvm, method + "Request")()
    values = {}
    filters = []
    if kind in {"instance_types", "availability", "subnets"} and query.zone:
        filters.append({"Name": "zone", "Values": [query.zone]})
    if kind == "subnets" and query.vpc_id:
        filters.append({"Name": "vpc-id", "Values": [query.vpc_id]})
    if kind == "availability":
        filters.append({"Name": "instance-charge-type", "Values": ["POSTPAID_BY_HOUR"]})
        if query.instance_type:
            filters.append({"Name": "instance-type", "Values": [query.instance_type]})
    if filters:
        values["Filters"] = filters
    if query.resource_id and kind in {"images", "vpcs", "subnets", "security_groups"}:
        values[
            {
                "images": "ImageIds",
                "vpcs": "VpcIds",
                "subnets": "SubnetIds",
                "security_groups": "SecurityGroupIds",
            }[kind]
        ] = [query.resource_id]
    if kind == "images" and query.instance_type:
        values["InstanceType"] = query.instance_type
    paginated = kind in {"images", "vpcs", "subnets", "security_groups"}
    offset = int(token or 0)
    if paginated:
        values.update(Offset=offset, Limit=query.page_size)
    request.from_json_string(json.dumps(values))
    body = json.loads(
        getattr(client_factory(credentials, query.region, service), method)(
            request
        ).to_json_string()
    )
    if kind == "quota":
        return {
            "items": [item("instances", "账号配额", remaining=None, unit="台")],
            "next": None,
            "warnings": ["账号配额概览不能换算为当前机型可用台数，余量未知"],
        }
    rows = body.get(collection) or []
    if kind == "availability":
        normalized = [
            item(
                row["InstanceType"],
                available=True
                if row.get("Status") == "SELL"
                else False
                if row.get("Status") == "SOLD_OUT"
                else None,
                reason="当前可用区售罄" if row.get("Status") == "SOLD_OUT" else "",
                zone=row.get("Zone"),
                remaining=None,
            )
            for row in rows
        ]
    else:
        normalized = [normalize(kind, row) for row in rows]
    if not paginated:
        if query.resource_id:
            normalized = [row for row in normalized if row["id"] == query.resource_id]
        total = len(normalized)
        normalized = normalized[offset : offset + query.page_size]
    else:
        total = body.get("TotalCount", offset + len(rows))
    return {
        "items": normalized,
        "next": str(offset + query.page_size)
        if offset + query.page_size < total
        else None,
    }

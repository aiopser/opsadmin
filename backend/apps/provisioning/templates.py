"""Generate the initial, create-only provider bundles for operator review."""
import re

from .contracts import ProvisioningError


def template_configuration(provider, provider_version, terraform_version):
    if provider not in {"aliyun", "tencent"} or any(
        not re.fullmatch(r"\d+\.\d+\.\d+", value)
        for value in [provider_version, terraform_version]
    ):
        raise ProvisioningError("请选择支持的平台并填写明确的 CLI、Provider 三段版本号")
    alias = "alicloud" if provider == "aliyun" else "tencentcloud"
    variables = {
        name: {"type": "string"}
        for name in [
            "name",
            "image_id",
            "instance_type",
            "zone",
            "vpc_id",
            "subnet_id",
            "region",
            "request_id",
        ]
    }
    variables.update(
        instance_count={"type": "number"},
        system_disk_gb={"type": "number"},
        security_group_ids={"type": "list(string)"},
    )
    if provider == "aliyun":
        data_type = "alicloud_vswitches"
        query = {
            "ids": ["${var.subnet_id}"],
            "vpc_id": "${var.vpc_id}",
            "zone_id": "${var.zone}",
        }
        condition = "${length(data.alicloud_vswitches.selected.vswitches) == 1}"
        resource = {
            "count": "${var.instance_count}",
            "instance_name": '${format("%s-%02d", var.name, count.index + 1)}',
            "image_id": "${var.image_id}",
            "instance_type": "${var.instance_type}",
            "availability_zone": "${var.zone}",
            "vswitch_id": "${var.subnet_id}",
            "security_groups": "${var.security_group_ids}",
            "system_disk_size": "${var.system_disk_gb}",
            "system_disk_category": "cloud_essd",
            "instance_charge_type": "PostPaid",
            "internet_max_bandwidth_out": 0,
        }
    else:
        data_type = "tencentcloud_vpc_subnets"
        query = {
            "subnet_id": "${var.subnet_id}",
            "vpc_id": "${var.vpc_id}",
            "availability_zone": "${var.zone}",
        }
        condition = (
            "${length(data.tencentcloud_vpc_subnets.selected.instance_list) == 1}"
        )
        resource = {
            "count": "${var.instance_count}",
            "instance_name": '${format("%s-%02d", var.name, count.index + 1)}',
            "image_id": "${var.image_id}",
            "instance_type": "${var.instance_type}",
            "availability_zone": "${var.zone}",
            "vpc_id": "${var.vpc_id}",
            "subnet_id": "${var.subnet_id}",
            "security_groups": "${var.security_group_ids}",
            "system_disk_size": "${var.system_disk_gb}",
            "system_disk_type": "CLOUD_PREMIUM",
            "instance_charge_type": "POSTPAID_BY_HOUR",
            "allocate_public_ip": False,
        }
    resource["tags"] = {"devops_request_id": "${var.request_id}"}
    resource["lifecycle"] = {
        "prevent_destroy": True,
        "precondition": [
            {"condition": condition, "error_message": "子网不属于当前账号、VPC 或可用区"}
        ],
    }
    return {
        "terraform": {
            "required_version": f"= {terraform_version}",
            "required_providers": {
                alias: {
                    "source": "aliyun/alicloud"
                    if provider == "aliyun"
                    else "tencentcloudstack/tencentcloud",
                    "version": f"= {provider_version}",
                }
            },
        },
        "variable": variables,
        "provider": {alias: {"region": "${var.region}"}},
        "data": {data_type: {"selected": query}},
        "resource": {f"{alias}_instance": {"host": resource}},
    }

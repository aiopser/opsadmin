from unittest.mock import Mock, patch
import json
import pytest


@pytest.mark.parametrize(
    "provider,row",
    [
        (
            "aliyun",
            {"InstanceTypeId": "ecs.c6.large", "CpuCoreCount": 2, "MemorySize": 4},
        ),
        ("tencent", {"InstanceType": "S5.MEDIUM4", "CPU": 2, "Memory": 4}),
    ],
)
def test_instance_config_is_not_inventory(provider, row):
    from .catalog import aliyun, tencent

    result = {"aliyun": aliyun, "tencent": tencent}[provider].normalize(
        "instance_types", row
    )
    assert result["attributes"]["memoryMiB"] == 4096
    assert result["available"] is None


def test_aliyun_subnet_keeps_missing_capacity_unknown():
    from .catalog.aliyun import normalize

    result = normalize(
        "subnets",
        {"VSwitchId": "vsw-one", "VpcId": "vpc-one", "ZoneId": "cn-shanghai-a"},
    )
    assert result["attributes"]["remaining"] is None
    assert result["attributes"]["vpcId"] == "vpc-one"


def test_tencent_uses_bounded_api_pagination():
    from .catalog.tencent import fetch_page
    from .catalog.types import CatalogQuery

    client = Mock()
    client.DescribeSubnets.return_value.to_json_string.return_value = json.dumps(
        {"TotalCount": 101, "SubnetSet": [{"SubnetId": "subnet-one"}]}
    )
    with patch("apps.provisioning.catalog.tencent.client_factory", return_value=client):
        result = fetch_page(
            {},
            CatalogQuery("subnets", "ap-shanghai", page_size=50, vpc_id="vpc-one"),
            "50",
        )
    assert result["next"] == "100"
    request = client.DescribeSubnets.call_args.args[0]
    assert request.Offset == 50 and request.Limit == 50


def test_unknown_availability_is_not_success():
    from .catalog.aliyun import fetch_page
    from .catalog.types import CatalogQuery

    client = Mock()
    client.describe_available_resource.return_value.body.to_map.return_value = {
        "AvailableZones": {
            "AvailableZone": [
                {
                    "ZoneId": "a",
                    "AvailableResources": {
                        "AvailableResource": [
                            {
                                "SupportedResources": {
                                    "SupportedResource": [
                                        {
                                            "Value": "ecs.one",
                                            "Status": "NewFutureStatus",
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                }
            ]
        }
    }
    with patch("apps.provisioning.catalog.aliyun.client_factory", return_value=client):
        result = fetch_page({}, CatalogQuery("availability", "cn-shanghai"), None)
    assert result["items"][0]["available"] is None


def test_aliyun_network_tags_use_vpc_field_names():
    from .catalog.aliyun import normalize
    from .catalog.policy import permitted

    row = normalize(
        "vpcs", {"VpcId": "vpc-one", "Tags": {"Tag": [{"Key": "env", "Value": "test"}]}}
    )
    assert permitted(
        row,
        "vpcs",
        {
            "schemaVersion": 2,
            "selectors": {"sourceIds": [1], "networkTags": {"env": "test"}},
        },
        1,
        "cn-shanghai",
    )


def test_aliyun_vpc_limits_page_size_and_keeps_cursor():
    from .catalog.aliyun import fetch_page
    from .catalog.types import CatalogQuery

    client = Mock()
    client.describe_vpcs.return_value.body.to_map.return_value = {
        "TotalCount": 120,
        "Vpcs": {"Vpc": [{"VpcId": "vpc-one"}]},
    }
    with patch("apps.provisioning.catalog.aliyun.client_factory", return_value=client):
        result = fetch_page(
            {}, CatalogQuery("vpcs", "cn-shanghai", page_size=100), None
        )
    assert client.describe_vpcs.call_args.args[0].page_size == 50
    assert result["next"] == "2"

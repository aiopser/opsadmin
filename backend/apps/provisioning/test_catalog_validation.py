from unittest.mock import patch
import pytest
from .test_contract import request_record
from .contracts import ProvisioningError


def resources():
    return {
        "zones": [{"id": "zone", "attributes": {}}],
        "vpcs": [{"id": "vpc", "attributes": {}}],
        "subnets": [
            {
                "id": "subnet",
                "attributes": {"zone": "zone", "vpcId": "vpc", "remaining": 2},
            }
        ],
        "security_groups": [{"id": "sg", "attributes": {"vpcId": "vpc"}}],
        "images": [
            {"id": "image", "available": True, "attributes": {"architecture": "x86_64"}}
        ],
        "instance_types": [{"id": "type", "attributes": {"architecture": "x86_64"}}],
        "availability": [
            {"id": "type", "available": True, "attributes": {"zone": "zone"}}
        ],
    }


@pytest.mark.parametrize("mutation", ["wrong_vpc", "sold_out", "wrong_arch", "missing"])
def test_dynamic_plan_refuses_unsafe_resources(request_record, mutation):
    from .catalog.validation import resolve_request_resources

    record = request_record
    record.version.constraints = {
        "schemaVersion": 2,
        "regions": [record.region],
        "selectors": {"sourceIds": [record.credential.source_id]},
    }
    record.parameters = {
        "zone": "zone",
        "vpc_id": "vpc",
        "subnet_id": "subnet",
        "security_group_ids": ["sg"],
        "image_id": "image",
        "instance_type": "type",
        "count": 1,
    }
    rows = resources()
    if mutation == "wrong_vpc":
        rows["subnets"][0]["attributes"]["vpcId"] = "other"
    if mutation == "sold_out":
        rows["availability"][0]["available"] = False
    if mutation == "wrong_arch":
        rows["images"][0]["attributes"]["architecture"] = "arm64"
    if mutation == "missing":
        rows["images"] = []
    with patch(
        "apps.provisioning.catalog.validation.list_catalog",
        side_effect=lambda actor, query, **kw: {
            "items": rows[query["kind"]],
            "hasMore": False,
            "observedAt": "now",
        },
    ):
        with pytest.raises(ProvisioningError):
            resolve_request_resources(record, record.created_by, refresh=True)

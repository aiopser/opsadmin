import base64
import json
from unittest.mock import patch

from .test_contract import request_record, ready_plan
from .models import ProvisioningAttempt


def test_inventory_retry_never_recreates_host(request_record):
    from .reconciliation import reconcile_attempt
    from apps.cmdb.models import AssetHost

    record = request_record
    record.execution_status = "success"
    record.save()
    attempt = ProvisioningAttempt.objects.create(
        plan=ready_plan(record),
        actor=record.created_by,
        idempotency_key="done",
        status="applied",
        recovery_artifact_key="x",
    )
    state = {
        "resources": [
            {
                "mode": "managed",
                "type": "alicloud_instance",
                "instances": [{"attributes": {"id": "i-created"}}],
            }
        ]
    }
    files = {"terraform.tfstate": base64.b64encode(json.dumps(state).encode()).decode()}
    asset = {
        "source_id": "i-created",
        "hostname": "created",
        "internal_ip": "10.9.8.7",
        "cpu_cores": 2,
    }
    with patch("apps.provisioning.reconciliation.ArtifactStore") as store, patch(
        "apps.provisioning.reconciliation.read_instances", return_value=[asset]
    ), patch("apps.provisioning.tasks.TerraformRunner") as writer:
        store.return_value.get.return_value = {"files": files}
        reconcile_attempt(attempt.pk)
        reconcile_attempt(attempt.pk)
    writer.assert_not_called()
    assert AssetHost.objects.filter(source_id="i-created").count() == 1
    record.refresh_from_db()
    assert record.inventory_status == "success"


def test_stopping_writer_does_not_block_readback(request_record):
    from .reconciliation import reconcile_attempt

    record = request_record
    record.credential.is_active = False
    record.credential.save()
    record.version.template.is_active = False
    record.version.template.save()
    attempt = ProvisioningAttempt.objects.create(
        plan=ready_plan(record),
        actor=record.created_by,
        idempotency_key="readonly",
        status="applied",
        recovery_artifact_key="x",
    )
    state = {
        "resources": [
            {
                "mode": "managed",
                "type": "alicloud_instance",
                "instances": [{"attributes": {"id": "i-existing"}}],
            }
        ]
    }
    files = {"terraform.tfstate": base64.b64encode(json.dumps(state).encode()).decode()}
    with patch("apps.provisioning.reconciliation.ArtifactStore") as store, patch(
        "apps.provisioning.reconciliation.read_instances",
        return_value=[
            {"source_id": "i-existing", "hostname": "web", "internal_ip": "10.2.2.2"}
        ],
    ) as read:
        store.return_value.get.return_value = {"files": files}
        reconcile_attempt(attempt.pk)
    read.assert_called_once()


def test_plan_network_scope_is_bound_to_source(request_record):
    import pytest
    from .contracts import validate_resource_scope, ProvisioningError

    request_record.parameters = {
        "vpc_id": "vpc-one",
        "subnet_id": "subnet-one",
        "zone": "zone-one",
        "security_group_ids": ["sg-one"],
        "image_id": "img",
        "instance_type": "small",
    }
    request_record.version.constraints = {
        "networks": [
            {
                "source_id": request_record.credential.source_id + 1,
                "region": request_record.region,
                **request_record.parameters,
            }
        ]
    }
    with pytest.raises(ProvisioningError, match="授权范围"):
        validate_resource_scope(request_record)

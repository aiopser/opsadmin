from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from .test_contract import request_record, ready_plan
from .models import ProvisioningAttempt
from .contracts import ProvisioningError
from .services import confirm_plan, approve_plan, execute_plan


def test_repeated_execute_queues_one_attempt(request_record, settings):
    settings.PROVISIONING_ENABLED = True
    plan = ready_plan(request_record)
    approver = get_user_model().objects.create_superuser(username="approver")
    confirm_plan(request_record.pk, request_record.created_by, plan.pk, plan.digest)
    approve_plan(request_record.pk, approver, plan.pk, plan.digest)
    with patch("apps.provisioning.tasks.apply_plan.apply_async"):
        first = execute_plan(
            request_record.pk,
            request_record.created_by,
            plan.pk,
            plan.digest,
            "same-key",
        )
        second = execute_plan(
            request_record.pk,
            request_record.created_by,
            plan.pk,
            plan.digest,
            "same-key",
        )
    assert first.pk == second.pk
    assert ProvisioningAttempt.objects.count() == 1


def test_execution_without_approval_is_rejected(request_record, settings):
    settings.PROVISIONING_ENABLED = True
    plan = ready_plan(request_record)
    confirm_plan(request_record.pk, request_record.created_by, plan.pk, plan.digest)
    with pytest.raises(ProvisioningError, match="审批"):
        execute_plan(
            request_record.pk,
            request_record.created_by,
            plan.pk,
            plan.digest,
            "unapproved",
        )


def test_other_users_cannot_read_private_request(request_record):
    user = get_user_model().objects.create_user(username="another")
    client = APIClient()
    client.force_authenticate(user)
    with patch("common.auth.rbac.verify_permission", return_value=(True, "")), patch(
        "apps.provisioning.views.verify_permission", return_value=(False, "")
    ):
        response = client.get(f"/api/v1/provisioning/requests/{request_record.pk}")
    assert response.status_code == 404


def test_request_detail_has_no_private_artifact(request_record):
    ready_plan(request_record)
    client = APIClient()
    client.force_authenticate(request_record.created_by)
    response = client.get(f"/api/v1/provisioning/requests/{request_record.pk}")
    assert response.status_code == 200
    assert "artifact_key" not in str(response.data)


def test_worker_duplicate_delivery_never_replays_apply(request_record):
    from .tasks import apply_plan

    plan = ready_plan(request_record)
    attempt = ProvisioningAttempt.objects.create(
        plan=plan,
        actor=request_record.created_by,
        idempotency_key="claimed",
        status="running",
    )
    with patch("apps.provisioning.tasks.TerraformRunner") as runner:
        apply_plan(attempt.pk)
    runner.assert_not_called()


def test_api_creates_valid_request_but_cannot_disable_approval(request_record):
    from .models import ResourceTemplateVersion

    values = {
        "count": 1,
        "name": "web",
        "image_id": "img-one",
        "instance_type": "ecs.small",
        "zone": "cn-shanghai-a",
        "vpc_id": "vpc-one",
        "subnet_id": "vsw-one",
        "security_group_ids": ["sg-one"],
        "system_disk_gb": 40,
    }
    version = ResourceTemplateVersion.objects.create(
        template=request_record.version.template,
        number=2,
        status="published",
        constraints={
            "regions": [request_record.region],
            "allowed_image_ids": ["img-one"],
            "allowed_instance_types": ["ecs.small"],
            "networks": [
                {
                    "source_id": request_record.credential.source_id,
                    "region": request_record.region,
                    "zone": values["zone"],
                    "vpc_id": values["vpc_id"],
                    "subnet_id": values["subnet_id"],
                    "security_group_ids": values["security_group_ids"],
                }
            ],
        },
    )
    client = APIClient()
    client.force_authenticate(request_record.created_by)
    response = client.post(
        "/api/v1/provisioning/requests",
        {
            "name": "Valid application",
            "version": version.pk,
            "credential": request_record.credential_id,
            "region": request_record.region,
            "parameters": values,
            "requires_approval": False,
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    assert response.data["data"]["requires_approval"] is True
    assert response.data["data"]["execution_status"] == "not_started"


def test_paginated_list_matches_frontend_contract(request_record):
    client = APIClient()
    client.force_authenticate(request_record.created_by)
    response = client.get("/api/v1/provisioning/requests?pageNum=1&pageSize=10")
    assert response.status_code == 200
    assert response.data["data"]["list"][0]["id"] == request_record.pk
    assert response.data["data"]["total"] == 1

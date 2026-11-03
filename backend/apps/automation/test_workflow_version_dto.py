"""Public workflow version input/output contract consumed by the editor."""

import pytest
from rest_framework.test import APIClient

from apps.automation.models import WorkflowTemplate, WorkflowVersion


@pytest.mark.django_db
def test_workflow_version_updates_and_clears_camel_case_configuration(user):
    user.is_superuser = True
    user.save()
    version = WorkflowVersion.objects.create(
        workflow=WorkflowTemplate.objects.create(
            name="DTO workflow", code="dto-workflow"
        ),
        version=1,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    url = f"/api/v1/automation/workflow-versions/{version.pk}"
    values = {
        "inputSchema": {"fields": [{"name": "release_tag", "required": True}]},
    }
    for payload in (values, {"inputSchema": {}}):
        response = client.patch(url, payload, format="json")
        assert response.status_code == 200
        version.refresh_from_db()
        assert version.input_schema == payload["inputSchema"]
        detail = client.get(url)
        assert detail.data["data"]["inputSchema"] == payload["inputSchema"]

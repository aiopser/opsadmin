from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.automation.models import CommandAtom, CommandVersion


@pytest.mark.django_db
def test_failed_publish_keeps_previous_published_version(user):
    user.is_superuser = True
    user.save()
    command = CommandAtom.objects.create(
        name="Publish rollback", code="publish-rollback", resource_kind="module"
    )
    old = CommandVersion.objects.create(
        command=command,
        version=1,
        command_type="ansible_module",
        content="ansible.builtin.ping",
        status="published",
    )
    draft = CommandVersion.objects.create(
        command=command,
        version=2,
        command_type="ansible_module",
        content="ansible.builtin.ping",
    )
    client = APIClient()
    client.force_authenticate(user=user)
    with patch.object(
        CommandVersion, "publish", side_effect=RuntimeError("publish failed")
    ):
        response = client.post(
            f"/api/v1/automation/command-versions/{draft.pk}/publish", {}, format="json"
        )
    assert response.status_code == 500
    old.refresh_from_db()
    draft.refresh_from_db()
    assert old.status == "published"
    assert draft.status == "draft"


@pytest.mark.django_db
def test_archived_version_cannot_be_republished(user):
    user.is_superuser = True
    user.save()
    command = CommandAtom.objects.create(
        name="Archived", code="archived-publish", resource_kind="module"
    )
    archived = CommandVersion.objects.create(
        command=command,
        version=1,
        command_type="ansible_module",
        content="ansible.builtin.ping",
        status="archived",
    )
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        f"/api/v1/automation/command-versions/{archived.pk}/publish", {}, format="json"
    )
    assert response.status_code == 400
    archived.refresh_from_db()
    assert archived.status == "archived"


@pytest.mark.django_db
def test_direct_version_create_cannot_bypass_publish_action(user):
    user.is_superuser = True
    user.save()
    command = CommandAtom.objects.create(
        name="Publish gate", code="publish-gate", resource_kind="module"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/v1/automation/command-versions",
        {
            "command": command.pk,
            "version": 1,
            "command_type": "ansible_module",
            "content": "ansible.builtin.ping",
            "status": "published",
        },
        format="json",
    )
    assert response.status_code == 400
    assert not command.versions.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["published", "archived"])
def test_historical_versions_cannot_be_deleted(user, status):
    user.is_superuser = True
    user.save()
    command = CommandAtom.objects.create(
        name="Historical", code="history-delete", resource_kind="module"
    )
    version = CommandVersion.objects.create(
        command=command,
        version=1,
        command_type="ansible_module",
        content="ansible.builtin.ping",
        status=status,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.delete(f"/api/v1/automation/command-versions/{version.pk}")
    assert response.status_code == 400
    assert CommandVersion.objects.filter(pk=version.pk).exists()

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.jobs.events import append_run_event
from apps.jobs.models import WorkerPool, WorkflowRun
from apps.permission.models import Permission, Role
from apps.permission.services import CasbinEnforcerService, sync_casbin_rules


@pytest.fixture
def event_client(user):
    role = Role.objects.create(name="Event reader")
    role.permission.add(
        Permission.objects.create(
            name="Read events",
            code="test.events.read",
            type="api",
            path="/api/v1/tasks/runs/:id/events",
            method="GET",
        )
    )
    user.role.add(role)
    sync_casbin_rules()
    CasbinEnforcerService.reload()
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def run(user):
    pool = WorkerPool.objects.create(code="event-api", name="Events", queue_name="test")
    return WorkflowRun.objects.create(
        worker_pool=pool,
        triggered_by=user,
        queue_deadline_at=timezone.now() + timedelta(hours=1),
    )


@pytest.mark.django_db
def test_event_pages_have_monotonic_cursor_and_no_duplicates(event_client, run):
    for index in range(3):
        append_run_event(
            run_id=run.id,
            event_key=str(index),
            event={"event_type": "test", "message": str(index)},
        )
    response = event_client.get(f"/api/v1/tasks/runs/{run.id}/events?cursor=0&limit=2")
    assert response.status_code == 200
    data = response.data["data"]
    assert [event["sequence"] for event in data["events"]] == [1, 2]
    assert data["next_cursor"] == 2
    assert data["has_more"] is True
    assert data["snapshot_version"] == 3
    second = event_client.get(
        f"/api/v1/tasks/runs/{run.id}/events?cursor=2&limit=2"
    ).data["data"]
    assert [event["sequence"] for event in second["events"]] == [3]
    assert second["has_more"] is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    ["after_id=1", "after_id=", "cursor=-1", "cursor=x", "limit=0", "limit=1001"],
)
def test_invalid_and_removed_event_parameters_are_rejected(event_client, run, query):
    assert (
        event_client.get(f"/api/v1/tasks/runs/{run.id}/events?{query}").status_code
        == 400
    )


@pytest.mark.django_db
def test_run_owner_scope_is_enforced(event_client, run):
    run.triggered_by = None
    run.save()
    assert event_client.get(f"/api/v1/tasks/runs/{run.id}/events").status_code == 404


@pytest.mark.django_db
def test_terminal_empty_page_and_removed_global_endpoint(event_client, run):
    run.status = "success"
    run.save()
    data = event_client.get(f"/api/v1/tasks/runs/{run.id}/events").data["data"]
    assert data["terminal"] is True
    assert data["events"] == []
    assert data["next_cursor"] == 0
    assert event_client.get("/api/v1/jobs/events").status_code == 404

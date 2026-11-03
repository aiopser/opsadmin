from datetime import timedelta
from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.exceptions import NotFound

from apps.jobs.idempotency import execution_idempotent
from apps.jobs.models import ExecutionRequestKey


@pytest.mark.django_db
def test_replay_compaction_retains_tombstone_and_never_executes_again(user):
    calls = []

    @execution_idempotent
    def handler(view, request):
        calls.append(request.data)
        return Response({"code": "00000", "data": {"id": 123}, "msg": None})

    request = SimpleNamespace(
        user=user,
        path="/test/execute",
        headers={},
        data={"executionRequestId": "test-compact-key", "value": "confidential"},
    )
    assert handler(None, request).status_code == 200
    row = ExecutionRequestKey.objects.get()
    assert "confidential" not in row.request_hash
    ExecutionRequestKey.objects.filter(pk=row.pk).update(
        created_at=timezone.now() - timedelta(days=91)
    )
    call_command("compact_execution_requests", stdout=StringIO())
    assert handler(None, request).status_code == 200
    call_command("compact_execution_requests", execute=True, stdout=StringIO())
    assert handler(None, request).status_code == 410
    assert len(calls) == 1
    row.refresh_from_db()
    assert row.response_encrypted == ""


@pytest.mark.django_db
def test_failed_request_can_be_retried_without_leaving_a_key(user):
    @execution_idempotent
    def handler(view, request):
        return Response({"code": "A0400", "msg": "rejected"}, status=400)

    request = SimpleNamespace(
        user=user,
        path="/test/execute",
        headers={},
        data={"executionRequestId": "test-failure-key"},
    )
    assert handler(None, request).status_code == 400
    assert ExecutionRequestKey.objects.count() == 0


@pytest.mark.django_db
def test_node_retry_replay_rechecks_current_run_scope(user, django_user_model):
    from unittest.mock import patch
    from rest_framework.test import APIClient
    from apps.jobs.models import NodeRun, WorkerPool, WorkflowRun
    from apps.permission.models import Role

    owner = django_user_model.objects.create_user(username="other-run-owner")
    role = Role.objects.create(
        name="review-replay-all", code="review-replay-all", job_data_scope="all"
    )
    user.role.add(role)
    pool = WorkerPool.objects.create(
        code="review-replay", name="Review replay", queue_name="test"
    )
    run = WorkflowRun.objects.create(
        triggered_by=owner, worker_pool=pool, status="failed"
    )
    node = NodeRun.objects.create(
        workflow_run=run, status="failed", node_name="other-scope-node"
    )
    client = APIClient()
    client.force_authenticate(user)
    endpoint = f"/api/v1/jobs/node-runs/{node.pk}/retry"
    payload = {"executionRequestId": "review-scope-replay"}
    with patch("common.auth.rbac.verify_permission", return_value=(True, "")), patch(
        "apps.jobs.views.retry_failed_node", return_value=node
    ):
        first = client.post(endpoint, payload, format="json")
        assert first.status_code == 200, first.data
        allowed_replay = client.post(endpoint, payload, format="json")
        assert allowed_replay.status_code == 200
        assert allowed_replay["Idempotency-Replayed"] == "true"
        role.job_data_scope = "own"
        role.save()
        assert client.get(f"/api/v1/jobs/node-runs/{node.pk}").status_code == 404
        assert (
            client.post(
                endpoint, {"executionRequestId": "review-new-key"}, format="json"
            ).status_code
            == 404
        )
        replay = client.post(endpoint, payload, format="json")
        assert replay.status_code == 404, replay.data


@pytest.mark.django_db
def test_replay_rechecks_detail_object_scope_after_access_is_revoked(user):
    class DetailView:
        lookup_url_kwarg = None
        lookup_field = "pk"
        permitted = True

        def get_object(self):
            if not self.permitted:
                raise NotFound()

    @execution_idempotent
    def handler(view, request, pk=None):
        view.get_object()
        return Response({"code": "00000", "data": {"id": 123}})

    view = DetailView()
    request = SimpleNamespace(
        user=user,
        path="/test/123/retry",
        headers={},
        data={"executionRequestId": "test-revoked-key"},
    )
    assert handler(view, request, pk="123").status_code == 200
    view.permitted = False
    with pytest.raises(NotFound):
        handler(view, request, pk="123")

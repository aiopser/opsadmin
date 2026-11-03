import pytest
from unittest.mock import patch
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.permissions import IsAuthenticated

from apps.audit_center.models import DomainAuditEvent
from apps.audit_center.views import LoginEventViewSet


@pytest.mark.django_db
def test_login_attempts_are_recorded_without_credentials(api_client, user):
    user.set_password("correct-password")
    user.save()

    failed = api_client.post("/api/v1/auth/login", {"username": user.username, "password": "wrong-password"})
    assert failed.status_code == 401
    succeeded = api_client.post("/api/v1/auth/login", {"username": user.username, "password": "correct-password"})
    assert succeeded.status_code == 200

    events = list(DomainAuditEvent.objects.filter(action__in=("auth.login.success", "auth.login.failure")).order_by("id"))
    assert [event.action for event in events] == ["auth.login.failure", "auth.login.success"]
    assert all(event.resource_id == user.username for event in events)
    assert all("password" not in str(event.before) + str(event.after) for event in events)


@pytest.mark.django_db
def test_login_event_list_filters_and_is_read_only(user):
    DomainAuditEvent.objects.create(domain="security", action="auth.login.failure", resource_type="login", resource_id="alice", result="failure")
    DomainAuditEvent.objects.create(domain="security", action="auth.login.success", resource_type="login", resource_id="bob", result="success")
    DomainAuditEvent.objects.create(domain="security", action="other", resource_type="login", resource_id="alice")
    factory = APIRequestFactory()
    list_view = LoginEventViewSet.as_view({"get": "list"}, permission_classes=[IsAuthenticated])
    request = factory.get("/api/v1/audit/login-events", {"username": "alice", "result": "failure"})
    force_authenticate(request, user)
    response = list_view(request)
    assert response.data["data"]["total"] == 1
    assert response.data["data"]["list"][0]["username"] == "alice"
    assert response.data["data"]["list"][0]["result"] == "failure"
    assert "before" not in response.data["data"]["list"][0]


@pytest.mark.django_db
def test_login_event_api_requires_permission_and_rejects_mutation(api_client, user):
    path = "/api/v1/audit/login-events"
    api_client.force_authenticate(user)
    assert api_client.get(path).status_code == 403
    user.is_superuser = True
    user.save(update_fields=["is_superuser"])
    assert api_client.get(path).status_code == 200
    assert api_client.post(path, {}, format="json").status_code == 405
    assert api_client.get(path, {"ipAddress": "not-an-ip"}).status_code == 400
    assert api_client.get(path, {"startDate": "2026-02-30"}).status_code == 400


@pytest.mark.django_db
def test_internal_login_failure_keeps_error_details_out_of_log(api_client):
    with patch("common.auth.jwt.MyTokenSerializer.is_valid", side_effect=RuntimeError("internal-secret-marker")):
        api_client.post("/api/v1/auth/login", {"username": "alice", "password": "secret"})
    event = DomainAuditEvent.objects.get(action="auth.login.failure")
    assert event.after == {"reason": "internal_error"}
    assert "internal-secret-marker" not in str(event.__dict__)


@pytest.mark.django_db
def test_operation_log_delete_endpoint_is_removed(api_client, user):
    user.is_superuser = True
    user.save(update_fields=["is_superuser"])
    api_client.force_authenticate(user)
    assert api_client.delete("/api/v1/logs/delete/1").status_code == 404

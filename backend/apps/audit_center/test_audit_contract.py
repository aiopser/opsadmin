import pytest
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.permissions import IsAuthenticated

from apps.audit_center.models import DomainAuditEvent
from apps.audit_center.services import create_domain_audit_event
from apps.audit_center.views import AuditEventViewSet


@pytest.mark.django_db
def test_audit_write_redacts_nested_secrets(user):
    event = create_domain_audit_event(user, "host.update", "host", 1,
        before={"password": "marker", "nested": {"Authorization": "Basic marker"}},
        after={"note": "token=marker"})
    event.refresh_from_db()
    assert "marker" not in str(event.before) + str(event.after)


@pytest.mark.django_db
def test_audit_list_and_detail_scope_to_actor(user, django_user_model):
    other = django_user_model.objects.create_user(username="audit-other")
    mine = create_domain_audit_event(user, "test", "host", 1)
    theirs = create_domain_audit_event(other, "test", "host", 2)
    factory = APIRequestFactory()
    request = factory.get("/api/v1/audit/events", {"pageNum": 1, "pageSize": 1})
    force_authenticate(request, user)
    view = AuditEventViewSet.as_view({"get": "list"}, permission_classes=[IsAuthenticated])
    response = view(request)
    assert response.data["data"]["total"] == 1
    assert response.data["data"]["list"][0]["id"] == mine.id
    detail = AuditEventViewSet.as_view({"get": "retrieve"}, permission_classes=[IsAuthenticated])
    assert detail(request, pk=theirs.pk).status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_audit_api_rejects_mutation(api_client, user, method):
    user.is_superuser = True
    user.save()
    api_client.force_authenticate(user)
    event = create_domain_audit_event(user, "test", "host", 1)
    path = "/api/v1/audit/events" if method == "post" else f"/api/v1/audit/events/{event.pk}"
    assert getattr(api_client, method)(path, {}, format="json").status_code == 405
    assert DomainAuditEvent.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_audit_serializer_exposes_one_field_contract(api_client, user):
    user.is_superuser = True
    user.save()
    api_client.force_authenticate(user)
    event = create_domain_audit_event(user, "test", "host", 1)
    response = api_client.get(f"/api/v1/audit/events/{event.pk}")
    assert response.data["data"]["resourceType"] == "host"
    assert "resource_type" not in response.data["data"]


@pytest.mark.django_db
def test_audit_export_requires_separate_permission(user):
    request = APIRequestFactory().get("/api/v1/audit/events/export")
    force_authenticate(request, user)
    view = AuditEventViewSet.as_view({"get": "export"}, permission_classes=[IsAuthenticated])
    assert view(request).status_code == 403


@pytest.mark.django_db
def test_export_keeps_scope_and_redacts_content(user, django_user_model):
    import json
    from apps.permission.models import Permission, Role

    role = Role.objects.create(name="audit-exporter")
    permission = Permission.objects.create(code="audit.event.export", name="Export", type="api", path="/api/v1/audit/events/export", method="GET")
    role.permission.add(permission)
    user.role.add(role)
    other = django_user_model.objects.create_user(username="export-other")
    mine = create_domain_audit_event(user, "test", "host", 1, after={"password": "marker"})
    create_domain_audit_event(other, "test", "host", 2)
    request = APIRequestFactory().get("/api/v1/audit/events/export")
    force_authenticate(request, user)
    view = AuditEventViewSet.as_view({"get": "export"}, permission_classes=[IsAuthenticated])
    response = view(request)
    content = b"".join(response.streaming_content).decode()
    assert [json.loads(line)["id"] for line in content.splitlines()] == [mine.pk]
    assert "marker" not in content


@pytest.mark.django_db
def test_audit_keyword_matches_displayed_operation_and_object_labels(api_client, user):
    user.is_superuser = True
    user.save()
    started = create_domain_audit_event(user, "workflow_run.create", "workflow_run", 1)
    updated = create_domain_audit_event(user, "host.update", "host", 2)
    deleted = create_domain_audit_event(user, "host.delete", "host", 3)
    api_client.force_authenticate(user)

    by_operation = api_client.get("/api/v1/audit/events", {"search": "启动"})
    assert [item["id"] for item in by_operation.data["data"]["list"]] == [started.pk]

    by_object = api_client.get("/api/v1/audit/events", {"search": "主机资产"})
    assert {item["id"] for item in by_object.data["data"]["list"]} == {updated.pk, deleted.pk}

    by_code = api_client.get("/api/v1/audit/events", {"search": "workflow_run.create"})
    assert [item["id"] for item in by_code.data["data"]["list"]] == [started.pk]


@pytest.mark.django_db
def test_audit_filter_and_seed_are_idempotent(api_client, user):
    from apps.permission.seed_data import seed_system_settings
    from apps.permission.models import Menu

    seed_system_settings(bind_superusers=False)
    count = Menu.objects.count()
    seed_system_settings(bind_superusers=False)
    assert Menu.objects.count() == count
    user.is_superuser = True
    user.save()
    api_client.force_authenticate(user)
    create_domain_audit_event(user, "host.update", "host", 1)
    wanted = create_domain_audit_event(user, "host.create", "host", 2)
    response = api_client.get("/api/v1/audit/events", {"action": "host.create", "pageSize": 1})
    assert response.data["data"]["total"] == 1
    assert response.data["data"]["list"][0]["id"] == wanted.pk

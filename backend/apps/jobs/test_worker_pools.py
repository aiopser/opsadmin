import pytest
from apps.jobs.models import WorkerPool
from apps.jobs.worker_pools import resolve_worker_pool, queue_for_pool
from rest_framework.exceptions import PermissionDenied, ValidationError


def test_worker_pool_is_owned_by_jobs():
    assert WorkerPool._meta.app_label == "jobs"
    assert WorkerPool._meta.db_table == "jobs_worker_pool"


@pytest.mark.django_db
def test_old_cmdb_worker_pool_route_is_removed(api_client, user):
    user.is_superuser = True
    user.save()
    api_client.force_authenticate(user)
    assert api_client.get("/api/v1/cmdb/worker-pools").status_code == 404


@pytest.mark.django_db
def test_worker_pool_jobs_api_creates_pool(api_client, user):
    user.is_superuser = True
    user.save()
    api_client.force_authenticate(user)
    response = api_client.post("/api/v1/jobs/worker-pools", {"name": "Test", "code": "test", "queueName": "devops.test", "concurrencyLimit": 2}, format="json")
    assert response.status_code == 200
    assert WorkerPool.objects.get(code="test").queue_name == "devops.test"


@pytest.mark.django_db
def test_worker_pool_permissions_and_capabilities(user):
    pool = WorkerPool.objects.create(code="pool", name="Pool", queue_name="test.ansible", execution_kinds=["module"])
    with pytest.raises(PermissionDenied):
        resolve_worker_pool(actor=user, pool_id=pool.pk, execution_kind="module")
    user.is_superuser = True
    user.save()
    assert resolve_worker_pool(actor=user, pool_id=pool.pk, execution_kind="module") == pool
    assert queue_for_pool(pool) == "test.ansible"
    with pytest.raises(ValidationError):
        resolve_worker_pool(actor=user, pool_id=pool.pk, execution_kind="playbook")
    pool.is_active = False
    pool.save()
    with pytest.raises(ValidationError):
        resolve_worker_pool(actor=user, pool_id=pool.pk, execution_kind="module")


@pytest.mark.django_db
def test_invalid_queue_is_rejected(user):
    user.is_superuser = True
    pool = WorkerPool.objects.create(code="invalid", name="Pool", queue_name="invalid queue")
    with pytest.raises(ValidationError):
        resolve_worker_pool(actor=user, pool_id=pool.pk, execution_kind="module")


@pytest.mark.django_db
def test_worker_pool_deletion_is_audited(api_client, user):
    from apps.audit_center.models import DomainAuditEvent
    user.is_superuser = True
    user.save()
    api_client.force_authenticate(user)
    pool = WorkerPool.objects.create(code="delete", name="Delete", queue_name="test")
    identifier = pool.pk
    assert api_client.delete(f"/api/v1/jobs/worker-pools/{identifier}").status_code == 200
    assert DomainAuditEvent.objects.filter(action="jobs.worker_pool.delete", resource_id=str(identifier)).exists()

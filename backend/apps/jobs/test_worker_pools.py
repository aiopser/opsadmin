import pytest
from apps.jobs.models import WorkerPool
from apps.jobs.worker_pools import region_for_targets, resolve_worker_pool, queue_for_pool
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


def test_region_for_targets_single_region_wins():
    targets = [{"host_id": 1, "region": "us-west-1"}, {"host_id": 2, "region": "us-west-1"}]
    assert region_for_targets(targets) == "us-west-1"


def test_region_for_targets_blank_on_mixed_or_empty_regions():
    assert region_for_targets([{"region": "us-west-1"}, {"region": "cn-east-1"}]) == ""
    assert region_for_targets([]) == ""
    assert region_for_targets(None) == ""


def test_region_for_targets_ignores_regionless_targets():
    # 存量无地域目标不阻塞已知地域的就近路由。
    assert region_for_targets([{"region": ""}, {"region": "cn-east-1"}]) == "cn-east-1"
    assert region_for_targets([{"region": " "}, {"region": "cn-east-1"}]) == "cn-east-1"


@pytest.mark.django_db
def test_resolve_worker_pool_routes_by_target_region(user):
    user.is_superuser = True
    user.save()
    WorkerPool.objects.create(code="default", name="Default", queue_name="q.default", is_default=True)
    region_pool = WorkerPool.objects.create(
        code="us-west", name="US West", queue_name="q.us-west", region="us-west-1"
    )
    resolved = resolve_worker_pool(
        actor=user, pool_id=None, execution_kind="module", target_region="us-west-1"
    )
    assert resolved == region_pool


@pytest.mark.django_db
def test_resolve_worker_pool_falls_back_to_default_without_region_pool(user):
    user.is_superuser = True
    user.save()
    default = WorkerPool.objects.create(code="default", name="Default", queue_name="q.default", is_default=True)
    WorkerPool.objects.create(
        code="us-west", name="US West", queue_name="q.us-west", region="us-west-1", is_active=False
    )
    resolved = resolve_worker_pool(
        actor=user, pool_id=None, execution_kind="module", target_region="us-west-1"
    )
    assert resolved == default


@pytest.mark.django_db
def test_resolve_worker_pool_region_candidate_must_support_execution_kind(user):
    user.is_superuser = True
    user.save()
    default = WorkerPool.objects.create(code="default", name="Default", queue_name="q.default", is_default=True)
    WorkerPool.objects.create(
        code="us-west", name="US West", queue_name="q.us-west", region="us-west-1",
        execution_kinds=["workflow"],
    )
    resolved = resolve_worker_pool(
        actor=user, pool_id=None, execution_kind="module", target_region="us-west-1"
    )
    assert resolved == default


@pytest.mark.django_db
def test_resolve_worker_pool_explicit_pool_overrides_region(user):
    user.is_superuser = True
    user.save()
    WorkerPool.objects.create(code="default", name="Default", queue_name="q.default", is_default=True)
    WorkerPool.objects.create(
        code="us-west", name="US West", queue_name="q.us-west", region="us-west-1"
    )
    explicit = WorkerPool.objects.create(
        code="cn-east", name="CN East", queue_name="q.cn-east", region="cn-east-1"
    )
    resolved = resolve_worker_pool(
        actor=user, pool_id=explicit.pk, execution_kind="module", target_region="us-west-1"
    )
    assert resolved == explicit

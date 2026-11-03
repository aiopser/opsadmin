"""运行可见范围测试：own / department / all 三档数据范围与回退行为。"""

import pytest
from django.contrib.auth import get_user_model

from apps.jobs.models import WorkerPool, WorkflowRun
from apps.jobs.run_access import (
    ALL,
    DEPARTMENT,
    NONE,
    OWNER,
    run_access_state,
    visible_runs,
)
from apps.permission.models import Role
from apps.user.models import Department


@pytest.fixture
def scope_data(db):
    sales = Department.objects.create(name="scope-sales")
    ops = Department.objects.create(name="scope-ops")
    pool = WorkerPool.objects.create(code="scope", name="Scope", queue_name="test")
    return sales, ops, pool


def make_user(username, department, **extra):
    return get_user_model().objects.create_user(
        username=username, password="test-pass-123", department=department, **extra
    )


def add_role(user, name, scope):
    user.role.add(
        Role.objects.create(name=name, code=name, job_data_scope=scope)
    )


def run_ids(user):
    return set(
        visible_runs(WorkflowRun.objects.all(), user).values_list("id", flat=True)
    )


@pytest.mark.django_db
def test_own_scope_sees_triggered_runs_only(scope_data):
    sales, _, pool = scope_data
    viewer = make_user("scope-owner", sales)
    colleague = make_user("scope-owner-colleague", sales)
    add_role(viewer, "own-role", Role.JobDataScope.OWN)
    own_run = WorkflowRun.objects.create(worker_pool=pool, triggered_by=viewer)
    WorkflowRun.objects.create(worker_pool=pool, triggered_by=colleague)

    assert run_access_state(viewer) == OWNER
    assert run_ids(viewer) == {own_run.id}


@pytest.mark.django_db
def test_department_scope_widens_to_direct_department(scope_data):
    sales, ops, pool = scope_data
    viewer = make_user("scope-dept", sales)
    colleague = make_user("scope-dept-colleague", sales)
    outsider = make_user("scope-dept-outsider", ops)
    add_role(viewer, "department-role", Role.JobDataScope.DEPARTMENT)
    own_run = WorkflowRun.objects.create(worker_pool=pool, triggered_by=viewer)
    colleague_run = WorkflowRun.objects.create(worker_pool=pool, triggered_by=colleague)
    WorkflowRun.objects.create(worker_pool=pool, triggered_by=outsider)

    assert run_access_state(viewer) == DEPARTMENT
    assert run_ids(viewer) == {own_run.id, colleague_run.id}


@pytest.mark.django_db
def test_all_scope_sees_every_run(scope_data):
    sales, ops, pool = scope_data
    viewer = make_user("scope-all", sales)
    outsider = make_user("scope-all-outsider", ops)
    add_role(viewer, "all-role", Role.JobDataScope.ALL)
    own_run = WorkflowRun.objects.create(worker_pool=pool, triggered_by=viewer)
    outsider_run = WorkflowRun.objects.create(worker_pool=pool, triggered_by=outsider)

    assert run_access_state(viewer) == ALL
    assert run_ids(viewer) == {own_run.id, outsider_run.id}


@pytest.mark.django_db
def test_department_scope_without_department_falls_back_to_own(scope_data):
    sales, _, pool = scope_data
    viewer = make_user("scope-no-dept", None)
    colleague = make_user("scope-no-dept-colleague", sales)
    add_role(viewer, "no-department-role", Role.JobDataScope.DEPARTMENT)
    own_run = WorkflowRun.objects.create(worker_pool=pool, triggered_by=viewer)
    WorkflowRun.objects.create(worker_pool=pool, triggered_by=colleague)

    assert run_access_state(viewer) == OWNER
    assert run_ids(viewer) == {own_run.id}


@pytest.mark.django_db
def test_inactive_employee_sees_nothing(scope_data):
    sales, _, pool = scope_data
    viewer = make_user("scope-inactive", sales, job_status=False)
    WorkflowRun.objects.create(worker_pool=pool, triggered_by=viewer)

    assert run_access_state(viewer) == NONE
    assert run_ids(viewer) == set()

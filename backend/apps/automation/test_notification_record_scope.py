"""Notification records must follow the same data scope as their runs."""

from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model

from apps.automation.models import NotificationRecord
from apps.automation.views import NotificationRecordViewSet
from apps.jobs.models import WorkerPool, WorkflowRun


@pytest.mark.django_db
def test_notification_record_queryset_excludes_other_users():
    user_model = get_user_model()
    owner = user_model.objects.create_user(
        username="notice-owner", phone="13800000201", password="test"
    )
    other = user_model.objects.create_user(
        username="notice-other", phone="13800000202", password="test"
    )
    owner.job_status = other.job_status = True
    owner.save(update_fields=["job_status"])
    other.save(update_fields=["job_status"])
    pool = WorkerPool.objects.create(
        code="notice-scope", name="notice-scope", queue_name="task"
    )
    own_run = WorkflowRun.objects.create(worker_pool=pool, triggered_by=owner)
    other_run = WorkflowRun.objects.create(worker_pool=pool, triggered_by=other)
    own = NotificationRecord.objects.create(workflow_run=own_run, body="mine")
    NotificationRecord.objects.create(workflow_run=other_run, body="private")
    NotificationRecord.objects.create(body="unbound")

    view = NotificationRecordViewSet()
    view.request = SimpleNamespace(user=owner)
    assert list(view.get_queryset().values_list("pk", flat=True)) == [own.pk]

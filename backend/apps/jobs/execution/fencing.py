"""Persist results only while the originating worker still owns this attempt."""

from django.db import transaction
from django.utils import timezone

from apps.jobs.models import NodeRun


def owned_node_queryset(node):
    return NodeRun.objects.filter(
        pk=node.pk,
        attempt_count=node.attempt_count,
        celery_task_id=node.celery_task_id,
        status=NodeRun.Status.RUNNING,
    )


@transaction.atomic
def commit_node_result(node, values):
    current = owned_node_queryset(node).select_for_update().first()
    if current is None:
        return False
    values = {**values, "updated_at": timezone.now()}
    owned_node_queryset(node).update(**values)
    for field, value in values.items():
        setattr(node, field, value)
    return True

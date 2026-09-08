import pytest

from apps.jobs.events import append_run_event
from apps.jobs.models import (
    HostRunResult,
    JobEventLog,
    NodeRun,
    NodeRunAttempt,
    WorkerPool,
    WorkflowRun,
)


@pytest.fixture
def execution():
    pool = WorkerPool.objects.create(code="events", name="Events", queue_name="test")
    run = WorkflowRun.objects.create(
        worker_pool=pool,
        target_snapshot=[
            {
                "host_id": 1,
                "hostname": "test",
                "address": "192.0.2.1",
                "port": 22,
                "connection_type": "ssh",
                "credential_ref_id": None,
                "variables": {},
            }
        ],
    )
    node = NodeRun.objects.create(workflow_run=run, attempt_count=1, status="running")
    attempt = NodeRunAttempt.objects.create(node_run=node, attempt=1, status="running")
    return run, node, attempt


def emit(execution, key, event="runner_on_ok"):
    run, node, attempt = execution
    return append_run_event(
        run_id=run.id,
        node_run_id=node.id,
        attempt_id=attempt.id,
        event_key=key,
        event={"event": event, "event_data": {"host": "test", "res": {"rc": 0}}},
    )


@pytest.mark.django_db
def test_duplicate_event_does_not_duplicate_projection(execution):
    first = emit(execution, "event-1")
    second = emit(execution, "event-1")
    assert first.pk == second.pk
    assert JobEventLog.objects.count() == 1
    assert HostRunResult.objects.count() == 1
    assert first.sequence == 1


@pytest.mark.django_db
def test_event_sequence_is_per_run_and_increases(execution):
    first = emit(execution, "one")
    second = emit(execution, "two")
    assert (first.sequence, second.sequence) == (1, 2)
    execution[0].refresh_from_db()
    assert execution[0].event_sequence == 2


@pytest.mark.django_db
def test_same_key_in_new_attempt_is_independent(execution):
    run, node, attempt = execution
    first = emit(execution, "same")
    node.attempt_count = 2
    node.save()
    second_attempt = NodeRunAttempt.objects.create(node_run=node, attempt=2)
    second = emit((run, node, second_attempt), "same")
    assert first.pk != second.pk
    assert second.sequence == 2


@pytest.mark.django_db
def test_cross_run_node_and_attempt_are_rejected(execution):
    run, node, attempt = execution
    other = WorkflowRun.objects.create(worker_pool=run.worker_pool)
    with pytest.raises(ValueError):
        append_run_event(
            run_id=other.id,
            node_run_id=node.id,
            attempt_id=attempt.id,
            event_key="cross",
            event={"event": "runner_on_ok"},
        )
    assert JobEventLog.objects.count() == 0


@pytest.mark.django_db
def test_late_nonterminal_callback_does_not_regress_host(execution):
    emit(execution, "done")
    emit(execution, "late-start", "runner_on_start")
    assert HostRunResult.objects.get().status == "ok"


@pytest.mark.django_db
def test_late_old_attempt_does_not_override_current_projection(execution):
    run, node, old = execution
    node.attempt_count = 2
    node.save()
    current = NodeRunAttempt.objects.create(node_run=node, attempt=2)
    emit((run, node, current), "current", "runner_on_failed")
    emit(execution, "late-old", "runner_on_ok")
    assert HostRunResult.objects.get().status == "failed"


@pytest.mark.django_db
def test_out_of_order_terminal_callback_does_not_replace_newer_result(execution):
    run, node, attempt = execution
    for counter, event_type in [(20, "runner_on_failed"), (10, "runner_on_ok")]:
        append_run_event(
            run_id=run.id,
            node_run_id=node.id,
            attempt_id=attempt.id,
            event_key=str(counter),
            event={
                "event": event_type,
                "counter": counter,
                "event_data": {
                    "host": "test",
                    "res": {"rc": 1 if counter == 20 else 0},
                },
            },
        )
    assert HostRunResult.objects.get().status == "failed"
    assert JobEventLog.objects.count() == 2


def test_deadlock_retry_is_bounded():
    from unittest.mock import patch
    from django.db import OperationalError

    with patch(
        "apps.jobs.events._append_once", side_effect=OperationalError(1213, "deadlock")
    ) as append:
        with pytest.raises(OperationalError):
            append_run_event(run_id=1, event_key="test", event={})
        assert append.call_count == 3


@pytest.mark.django_db(transaction=True)
def test_two_mysql_transactions_allocate_unique_sequences(execution):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import connection, close_old_connections

    if connection.vendor != "mysql":
        pytest.skip(
            "Requires the explicit isolated MySQL test settings; SQLite does not validate row locks"
        )
    barrier = Barrier(2)

    def publish(key):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return emit(execution, key).sequence
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(publish, ["concurrent-one", "concurrent-two"])) == [
            1,
            2,
        ]


@pytest.mark.django_db
def test_database_rejects_duplicate_sequence_and_event_key(execution):
    from django.db import IntegrityError, transaction

    first = emit(execution, "one")
    for sequence, key in [
        (first.sequence, "other"),
        (first.sequence + 1, first.event_key),
    ]:
        with pytest.raises(IntegrityError), transaction.atomic():
            JobEventLog.objects.bulk_create(
                [
                    JobEventLog(
                        workflow_run_id=first.workflow_run_id,
                        sequence=sequence,
                        event_key=key,
                        event_type="invalid-duplicate",
                    )
                ]
            )
    assert JobEventLog.objects.count() == 1

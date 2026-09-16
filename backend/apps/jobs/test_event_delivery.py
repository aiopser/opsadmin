import pytest

from django.db import connection

from apps.jobs.events import append_run_event
from apps.jobs.models import (
    HostRunResult,
    JobEventLog,
    NodeRun,
    NodeRunAttempt,
    WorkerPool,
    WorkflowRun,
)

# SQLite 无并发写能力（table is locked），并发分配仅在 MySQL 验收环境执行
mysql_only = pytest.mark.skipif(
    connection.vendor != "mysql", reason="concurrent writes require MySQL"
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
def test_sequence_collision_retries_and_keeps_event_sequence_monotonic(execution):
    """sequence 撞唯一约束时顺延重试，event_sequence 以 Greatest 单调推进。"""
    run = execution[0]
    # 模拟并发窗口：sequence=1 已被占用，但 run.event_sequence 仍为 0
    JobEventLog.objects.create(
        workflow_run=run,
        sequence=1,
        event_key="0:None:occupied",
        event_type="test",
        message="",
        payload={},
    )
    log = append_run_event(
        run_id=run.id, event_key="later", event={"event_type": "test"}
    )
    assert log.sequence == 2
    run.refresh_from_db()
    assert run.event_sequence == 2


@mysql_only
@pytest.mark.django_db(transaction=True)
def test_concurrent_appends_allocate_unique_sequences(execution):
    """并发追加同一 run：sequence 不重复、event_sequence 单调、事件不丢失。"""
    from concurrent.futures import ThreadPoolExecutor

    from django.db import close_old_connections

    run = execution[0]

    def append(index):
        close_old_connections()
        try:
            return append_run_event(
                run_id=run.id,
                event_key=f"concurrent-{index}",
                event={"event_type": "test", "message": str(index)},
            )
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=8) as pool:
        logs = list(pool.map(append, range(30)))

    sequences = [log.sequence for log in logs]
    assert len(set(sequences)) == 30
    assert JobEventLog.objects.filter(workflow_run=run).count() == 30
    run.refresh_from_db()
    assert run.event_sequence >= max(sequences)


@mysql_only
@pytest.mark.django_db(transaction=True)
def test_concurrent_same_key_returns_same_event(execution):
    """并发投递同一 event_key：只落一条，双方返回同一条事件。"""
    from concurrent.futures import ThreadPoolExecutor

    from django.db import close_old_connections

    run = execution[0]

    def append(_):
        close_old_connections()
        try:
            return append_run_event(
                run_id=run.id,
                event_key="same-key",
                event={"event_type": "test", "message": "dedup"},
            )
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=4) as pool:
        logs = list(pool.map(append, range(4)))

    assert len({log.pk for log in logs}) == 1
    assert JobEventLog.objects.filter(workflow_run=run).count() == 1


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

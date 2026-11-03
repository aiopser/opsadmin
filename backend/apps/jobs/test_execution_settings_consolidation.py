from types import SimpleNamespace
import pytest
from apps.jobs.execution.settings_snapshot import freeze_execution_settings
from apps.jobs.execution.plan_builder import (
    _ansible_execution_options,
    _apply_host_execution_options,
)

DEFAULTS = dict(
    host_strategy="parallel",
    forks=10,
    serial_batch=2,
    max_fail_percentage=0,
    timeout=300,
)


@pytest.mark.parametrize(
    "step,expected,source",
    [(None, 45, "resource"), (120, 120, "step"), (400, 300, "global")],
)
def test_step_timeout_overrides_resource_before_run_budget(step, expected, source):
    frozen = freeze_execution_settings(
        DEFAULTS,
        {},
        {
            "nodes": [
                dict(
                    id="x",
                    type="script",
                    timeoutSeconds=step,
                    commandVersion={"timeout_seconds": 45},
                )
            ]
        },
    )
    assert frozen["nodes"]["x"]["values"]["timeoutSeconds"] == expected
    assert frozen["nodes"]["x"]["sources"]["timeoutSeconds"] == source


@pytest.mark.parametrize(
    "kind,resource,expected",
    [
        ("api", {"definition": {"timeout_seconds": 20}}, 20),
        ("jenkins", {"definition": {}}, 300),
        ("notify", None, 300),
    ],
)
def test_generic_nodes_freeze_usable_timeout(kind, resource, expected):
    frozen = freeze_execution_settings(
        DEFAULTS,
        {},
        {
            "nodes": [
                dict(id="x", type=kind, timeoutSeconds=None, resourceSnapshot=resource)
            ]
        },
    )
    assert frozen["nodes"]["x"]["values"]["timeoutSeconds"] == expected


@pytest.mark.parametrize("policy", [None, "native", "platform"])
def test_playbook_host_policy_preserves_native_unless_opted_in(policy):
    config = {} if policy is None else {"hostPolicy": policy}
    node = SimpleNamespace(node_key="x", node_type="playbook", config=config)
    frozen = freeze_execution_settings(
        DEFAULTS, {}, {"nodes": [dict(id="x", type="playbook", config=config)]}
    )
    options = _ansible_execution_options(
        SimpleNamespace(execution_settings=frozen, timeout_seconds=300), node
    )
    original = {"serial": 7, "max_fail_percentage": 35, "any_errors_fatal": False}
    result = _apply_host_execution_options([dict(original)], options)[0]
    assert result == (original if policy != "platform" else {"any_errors_fatal": True})


@pytest.mark.parametrize("kind", ["script", "module"])
def test_platform_policies_still_apply_to_generated_plays(kind):
    frozen = freeze_execution_settings(
        DEFAULTS,
        {},
        {"nodes": [dict(id="x", type=kind, config={"hostStrategy": "serial"})]},
    )
    options = _ansible_execution_options(
        SimpleNamespace(execution_settings=frozen), SimpleNamespace(node_key="x")
    )
    assert _apply_host_execution_options([{}], options) == [
        {"serial": 1, "any_errors_fatal": True}
    ]
    assert options["forks"] == 1


def test_native_playbook_keeps_runner_forks_even_with_serial_platform_default():
    frozen = freeze_execution_settings(
        {**DEFAULTS, "host_strategy": "serial"},
        {},
        {"nodes": [dict(id="x", type="playbook", config={"forks": 2})]},
    )
    values = frozen["nodes"]["x"]["values"]
    assert values["hostPolicy"] == "native"
    assert values["forks"] == 10


def test_dispatch_uses_frozen_settings_and_remaining_budget():
    from datetime import timedelta
    from django.utils import timezone
    from unittest.mock import patch
    from apps.jobs.application.dispatch import _node_queue_and_timeout

    frozen = freeze_execution_settings(
        DEFAULTS, {}, {"nodes": [dict(id="x", type="api", timeoutSeconds=120)]}
    )
    now = timezone.now()
    run = SimpleNamespace(
        execution_settings=frozen,
        timeout_seconds=300,
        workflow_deadline_at=now + timedelta(seconds=25),
        worker_pool=None,
        run_domain="default",
    )
    node = SimpleNamespace(
        workflow_run=run,
        node_key="x",
        node_type="api",
        workflow_node=SimpleNamespace(timeout_seconds=1),
    )
    with patch("apps.jobs.execution.settings_snapshot.timezone.now", return_value=now):
        assert _node_queue_and_timeout(node)[1] == 25


@pytest.mark.parametrize("kind", ["script", "playbook", "module"])
def test_inherited_check_mode_requires_supported_resource(kind):
    with pytest.raises(ValueError, match="Check Mode"):
        freeze_execution_settings(
            DEFAULTS,
            {"check_mode": True},
            {
                "nodes": [
                    dict(
                        id="x",
                        type=kind,
                        commandVersion={"check_mode_supported": False},
                    )
                ]
            },
        )
    frozen = freeze_execution_settings(
        DEFAULTS,
        {"check_mode": True},
        {
            "nodes": [
                dict(id="x", type=kind, commandVersion={"check_mode_supported": True})
            ]
        },
    )
    assert frozen["nodes"]["x"]["values"]["checkMode"] is True


@pytest.mark.django_db
def test_nullable_timeout_survives_graph_roundtrip_and_execution_snapshot():
    from apps.automation.models import WorkflowTemplate, WorkflowVersion
    from apps.automation.workflow_graph import replace_graph, serialize_graph
    from apps.jobs.execution.snapshots import execution_node

    template = WorkflowTemplate.objects.create(name="Nullable", code="nullable-timeout")
    version = WorkflowVersion.objects.create(workflow=template, version=1)
    graph = {
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "x", "type": "jenkins", "timeoutSeconds": None},
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"id": "a", "source": "start", "target": "x"},
            {"id": "b", "source": "x", "target": "end"},
        ],
    }
    assert replace_graph(version, graph) == []
    saved = serialize_graph(version)
    assert saved["nodes"][1]["timeoutSeconds"] is None
    assert (
        execution_node(
            SimpleNamespace(
                workflow_run=SimpleNamespace(graph_snapshot=saved), node_key="x"
            )
        ).timeout_seconds
        is None
    )


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["api", "notify", "script"])
def test_expired_queued_delivery_times_out_without_external_execution(kind):
    from datetime import timedelta
    from unittest.mock import patch
    from django.utils import timezone
    from apps.jobs.models import NodeRun, NodeRunAttempt, WorkerPool, WorkflowRun
    from apps.jobs.tasks import execute_node

    pool = WorkerPool.objects.create(
        code="expired-budget", name="Expired", queue_name="test"
    )
    run = WorkflowRun.objects.create(
        worker_pool=pool,
        status="running",
        workflow_deadline_at=timezone.now() - timedelta(seconds=1),
    )
    node = NodeRun.objects.create(
        workflow_run=run, node_key="x", node_type=kind, status="queued", attempt_count=1
    )
    NodeRunAttempt.objects.create(node_run=node, attempt=1)
    with patch("apps.jobs.tasks.authorize_execution"), patch(
        "apps.jobs.tasks.runtime_context", return_value={}
    ), patch("apps.jobs.tasks.execute_generic_node", return_value={}) as generic, patch(
        "apps.jobs.tasks.execute_ansible_node"
    ) as ansible, patch(
        "apps.jobs.tasks.enqueue_workflow_run"
    ):
        execute_node(node.pk, 1)
    node.refresh_from_db()
    assert node.status == "timeout"
    generic.assert_not_called()
    ansible.assert_not_called()


from apps.jobs.test_execution_entrypoints import actor, host, pool


@pytest.mark.django_db
@pytest.mark.parametrize("check_mode", [False, True])
def test_direct_resource_playbook_freezes_native_policy_before_creation(
    actor, host, pool, check_mode
):
    from apps.automation.models import CommandAtom, CommandVersion
    from apps.jobs.application.runs import create_quick_command_run
    from apps.jobs.execution.snapshots import ensure_node_runs, execution_node
    from apps.jobs.execution.plan_builder import _node_command_spec, _node_playbook

    command = CommandAtom.objects.create(
        name="Native playbook",
        code="native-quick",
        resource_kind="playbook",
        status="published",
    )
    content = "- hosts: all\n  serial: 7\n  max_fail_percentage: 35\n  any_errors_fatal: false\n  tasks: []\n"
    source = CommandVersion.objects.create(
        command=command,
        version=1,
        command_type="playbook",
        content=content,
        status="published",
        check_mode_supported=True,
        timeout_seconds=120,
    )
    run = create_quick_command_run(
        command_type="linux_shell",
        command_content="ansible-playbook playbook.yml",
        resource_version=source,
        host_ids=[host.pk],
        worker_pool=pool,
        triggered_by=actor,
        extra_input_vars={
            "execution_source": "playbook",
            "playbook_content": content,
            "check_mode": check_mode,
        },
    )
    definition = execution_node(ensure_node_runs(run)["quick_command"])
    options = _ansible_execution_options(run, definition)
    playbook = _node_playbook(run, definition, _node_command_spec(definition), {})
    actual = _apply_host_execution_options(playbook, options)[0]
    assert options["host_policy"] == "native"
    assert options["check_mode"] == check_mode
    assert actual["serial"] == 7
    assert actual["max_fail_percentage"] == 35
    assert actual["any_errors_fatal"] is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "source,extra",
    [
        ("playbook", {"playbook_content": "- hosts: all\n  tasks: []"}),
        ("module", {"module": "ansible.builtin.ping", "module_args": "{}"}),
    ],
)
def test_online_ansible_check_mode_keeps_runner_contract(
    actor, host, pool, source, extra
):
    from apps.jobs.application.runs import create_quick_command_run

    run = create_quick_command_run(
        command_type="linux_shell",
        command_content="online execution",
        host_ids=[host.pk],
        worker_pool=pool,
        triggered_by=actor,
        extra_input_vars={"execution_source": source, "check_mode": True, **extra},
    )
    assert (
        run.execution_settings["nodes"]["quick_command"]["values"]["checkMode"] is True
    )

    assert (
        run.execution_settings["nodes"]["quick_command"]["sources"]["timeoutSeconds"]
        == "global"
    )


from apps.jobs.test_execution_entrypoints import api_run, notify_run


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["api", "notify"])
def test_generic_transport_uses_remaining_run_budget(kind, api_run, notify_run):
    from datetime import timedelta
    from unittest.mock import patch
    from django.utils import timezone
    from apps.jobs.node_executors import execute_api, execute_notification

    run, node = (
        (api_run[1], api_run[2]) if kind == "api" else (notify_run[2], notify_run[3])
    )
    now = timezone.now()
    run.workflow_deadline_at = now + timedelta(seconds=2)
    run.save(update_fields=["workflow_deadline_at"])
    node.workflow_run = run
    seen = []

    def request(method, url, headers, body, timeout, verify_ssl=True):
        seen.append(timeout)
        return 200, {}, "{}"

    with patch("apps.jobs.node_executors._request", side_effect=request), patch(
        "apps.jobs.execution.settings_snapshot.timezone.now", return_value=now
    ):
        (execute_api if kind == "api" else execute_notification)(
            node, {"inputs": {"name": "test"}}
        )
    assert seen == [2]

import pytest

from apps.jobs.views import _preview_host_policy


@pytest.mark.parametrize(
    "node,expected",
    [
        ({"type": "api"}, "none"),
        ({"type": "playbook", "config": {"hostStrategy": "serial"}}, "native"),
        ({"type": "playbook", "config": {"hostPolicy": "platform"}}, "run"),
        ({"type": "script", "config": {"forks": 20}}, "step"),
        ({"type": "module", "config": {}}, "run"),
        (
            {
                "type": "playbook",
                "config": {"hostPolicy": "platform", "maxFailPercentage": 0},
            },
            "step",
        ),
    ],
)
def test_preview_distinguishes_native_inherited_and_explicit_policy(node, expected):
    assert _preview_host_policy(node) == expected


def test_quick_playbook_preview_reports_native_policy_for_command_wrapper(monkeypatch):
    from types import SimpleNamespace
    from apps.jobs import views

    monkeypatch.setattr(
        views,
        "_execution_preview",
        lambda *args, **kwargs: {
            "steps": [
                {"type": "command", "targetScope": "all", "hostPolicySource": "run"}
            ]
        },
    )
    monkeypatch.setattr(views, "request_config", lambda *args: {})
    serializer = SimpleNamespace(
        initial_data={},
        validated_data={
            "workflow_version": None,
            "target_preview": [],
            "worker_pool": None,
            "playbookContent": "- hosts: all",
        },
    )
    preview = views._quick_execution_preview(serializer, "Playbook")
    assert preview["steps"][0]["hostPolicySource"] == "native"

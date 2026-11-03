from types import SimpleNamespace
from unittest.mock import patch
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from apps.automation.models import NotificationChannel, NotificationTemplate
from apps.cmdb.crypto import encrypt_secret
from .node_executors import send_notification
from .execution.snapshots import execution_resource


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["dingtalk", "feishu"])
def test_runtime_snapshot_loads_current_signing_secret(kind):
    channel = NotificationChannel.objects.create(
        name="signed",
        channel_type=kind,
        secret_encrypted=encrypt_secret("https://example.test/robot"),
        signing_secret_encrypted=encrypt_secret("rotated-signing-key"),
    )
    template = NotificationTemplate.objects.create(
        name="signed template",
        code="signed-template",
        channel=channel,
        body_template="message",
    )
    definition = {
        "id": template.pk,
        "name": template.name,
        "code": template.code,
        "body_template": "message",
        "channel": {
            "id": channel.pk,
            "name": channel.name,
            "channel_type": kind,
            "config": {},
        },
    }
    node = SimpleNamespace(
        node_key="notify",
        workflow_run=SimpleNamespace(
            graph_snapshot={
                "nodes": [
                    {
                        "id": "notify",
                        "type": "notify",
                        "timeoutSeconds": 10,
                        "resourceSnapshot": {"definition": definition},
                    }
                ]
            }
        ),
    )
    resource = execution_resource(node)
    assert resource.channel.signing_secret_encrypted == channel.signing_secret_encrypted
    assert "rotated-signing-key" not in str(node.workflow_run.graph_snapshot)
    with patch(
        "apps.jobs.node_executors._request",
        return_value=(200, {}, '{"errcode":0,"code":0}'),
    ) as request:
        send_notification(resource, {})
    args = request.call_args.args
    if kind == "dingtalk":
        assert parse_qs(urlsplit(args[1]).query)["sign"]
    else:
        assert json.loads(args[3])["sign"]

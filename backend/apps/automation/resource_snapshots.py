"""Freeze resource configuration; encrypted credentials remain live references."""

from copy import deepcopy
import re

from common.redaction import SENSITIVE_KEY_PATTERN, redact_text

from .models import ApiEndpoint, JenkinsJob, NotificationTemplate


def _fields(instance, names):
    return {name: deepcopy(getattr(instance, name)) for name in names}


def _assert_no_literal_secrets(value):
    if isinstance(value, dict):
        pair_name = value.get("key") or value.get("name")
        if isinstance(pair_name, str) and re.search(
            SENSITIVE_KEY_PATTERN, pair_name, re.IGNORECASE
        ):
            secret = value.get("value")
            if secret and not (
                isinstance(secret, str)
                and secret.strip().startswith("{{")
                and secret.strip().endswith("}}")
            ):
                raise ValueError(
                    "Resource credentials must use secret references or runtime secret inputs"
                )
        for key, item in value.items():
            if re.search(SENSITIVE_KEY_PATTERN, str(key), re.IGNORECASE) and item:
                if not (
                    isinstance(item, str)
                    and item.strip().startswith("{{")
                    and item.strip().endswith("}}")
                ):
                    raise ValueError(
                        "Resource credentials must use secret references or runtime secret inputs"
                    )
            _assert_no_literal_secrets(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_literal_secrets(item)
    elif isinstance(value, str) and "{{" not in value and redact_text(value) != value:
        raise ValueError("Literal credentials cannot enter a resource snapshot")


def resource_snapshot(node):
    if not node.resource_id:
        return None
    if node.node_type == "api":
        resource = ApiEndpoint.objects.get(pk=node.resource_id, is_active=True)
        data = _fields(
            resource,
            (
                "id",
                "name",
                "method",
                "url",
                "query_params",
                "headers",
                "cookies",
                "body_type",
                "body",
                "auth_type",
                "username",
                "api_key_name",
                "api_key_location",
                "success_rules",
                "output_extractors",
                "timeout_seconds",
                "verify_ssl",
            ),
        )
        for name in ("query_params", "headers", "cookies", "body", "url"):
            _assert_no_literal_secrets(data[name])
    elif node.node_type == "jenkins":
        resource = JenkinsJob.objects.select_related("server").get(
            pk=node.resource_id, is_active=True, server__is_active=True
        )
        data = _fields(resource, ("id", "name", "url", "parameters"))
        data["server"] = _fields(
            resource.server, ("id", "name", "base_url", "username", "verify_ssl")
        )
    elif node.node_type == "notify":
        resource = NotificationTemplate.objects.select_related("channel").get(
            pk=node.resource_id, is_active=True, channel__is_active=True
        )
        data = _fields(
            resource,
            (
                "id",
                "name",
                "code",
                "subject_template",
                "body_template",
                "receiver_template",
            ),
        )
        data["channel"] = _fields(
            resource.channel, ("id", "name", "channel_type", "config")
        )
        _assert_no_literal_secrets(data["channel"]["config"])
    else:
        return None
    return {"revision": resource.updated_at.isoformat(), "definition": data}

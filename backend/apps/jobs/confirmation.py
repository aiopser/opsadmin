"""Opaque confirmation of the execution definition shown in a preview."""

import hashlib
import hmac
import json

from django.conf import settings

from apps.jobs.settings_service import get_engine_settings
from apps.jobs.models import WorkerPool


DEFINITION_FIELDS = (
    "name",
    "workflow_version_id",
    "worker_pool_id",
    "host_ids",
    "group_ids",
    "tag_ids",
    "input_vars",
    "host_strategy",
    "forks",
    "serial_batch",
    "max_fail_percentage",
    "timeout_seconds",
)


def definition_config(definition):
    """Only editable execution fields; counters and scheduling timestamps are excluded."""
    fields = (
        DEFINITION_FIELDS
        + (("failure_alert",) if hasattr(definition, "failure_alert") else ())
        + (("gateway_id",) if hasattr(definition, "gateway_id") else ())
        + (
            ("queue_timeout_seconds",)
            if hasattr(definition, "queue_timeout_seconds")
            else ()
        )
    )
    config = {field: getattr(definition, field) for field in fields}
    if hasattr(definition, "secret_input_vars_encrypted"):
        from apps.jobs.input_secrets import resolve_workflow_inputs

        config["input_vars"] = resolve_workflow_inputs(definition)
    return config


def request_config(data, validated_data=None):
    """Bind the submitted payload without including preview-only confirmation fields."""
    config = {
        key: value
        for key, value in data.items()
        if key
        not in {
            "expectedTargetIds",
            "expectedTargetFingerprint",
            "expectedConfirmationFingerprint",
            "executionRequestId",
        }
    }
    for field in ("source_command_version", "module_version", "playbook_version"):
        version = (validated_data or {}).get(field)
        if version is not None:
            config[field] = {
                "id": version.pk,
                "status": version.status,
                "content": version.content,
                "module_name": version.module_name,
                "parameter_docs": version.parameter_docs,
                "default_vars": version.default_vars,
                "argument_schema": version.argument_schema,
                "output_extractors": version.output_extractors,
                "timeout_seconds": version.timeout_seconds,
                "become_enabled": version.become_enabled,
                "check_mode_supported": version.check_mode_supported,
                "command_status": version.command.status,
                "risk_level": version.command.risk_level,
            }
    return config


def confirmation_fingerprint(workflow_version, worker_pool, config):
    """HMAC hides inputs and secrets while detecting changes to the execution definition."""
    payload = {
        "workflow": {
            "id": workflow_version.pk,
            "status": workflow_version.status,
            "published_hash": workflow_version.published_hash,
            "graph": workflow_version.graph_snapshot,
            "input_schema": workflow_version.input_schema,
            "failure_alert": workflow_version.workflow.failure_alert,
        },
        "worker_pool": (
            {
                "id": worker_pool.pk,
                "queue_name": worker_pool.queue_name,
                "region": worker_pool.region,
                "is_active": worker_pool.is_active,
                "concurrency_limit": worker_pool.concurrency_limit,
                "execution_kinds": worker_pool.execution_kinds,
            }
            if worker_pool is not None
            else None
        ),
        "automatic_pool_candidates": (
            list(
                WorkerPool.objects.filter(is_active=True)
                .order_by("pk")
                .values(
                    "id",
                    "queue_name",
                    "region",
                    "is_default",
                    "is_active",
                    "concurrency_limit",
                    "execution_kinds",
                )
            )
            if worker_pool is None
            else None
        ),
        "engine": get_engine_settings(),
        "definition": config,
    }
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
    )
    return hmac.new(
        settings.SECRET_KEY.encode(), canonical.encode(), hashlib.sha256
    ).hexdigest()

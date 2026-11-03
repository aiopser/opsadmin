from types import SimpleNamespace
import importlib

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.automation.models import CommandAtom, CommandVersion
from apps.automation.serializers import (
    AnsibleNodeResourceCreateSerializer,
    CommandVersionSerializer,
)
from apps.automation.workflow_graph import _command_version_info
from apps.jobs.execution.plan_builder import _node_playbook


@pytest.mark.django_db
def test_module_api_stores_explicit_fields_without_overloading_content():
    command = CommandAtom.objects.create(
        name="Explicit module", code="explicit-module", resource_kind="module"
    )
    notes = [{"name": "name", "description": "服务名称"}]
    serializer = CommandVersionSerializer(
        data={
            "command": command.pk,
            "version": 1,
            "command_type": "ansible_module",
            "module_name": "ansible.builtin.service",
            "parameter_docs": notes,
        }
    )
    assert serializer.is_valid(), serializer.errors
    version = serializer.save()
    assert version.content == ""
    assert version.argument_schema == {}
    assert version.module_name == "ansible.builtin.service"
    assert version.parameter_docs == notes
    frozen = _command_version_info(version)
    assert frozen["module_name"] == version.module_name
    assert frozen["parameter_docs"] == notes


@pytest.mark.django_db
def test_old_module_request_is_normalized_into_explicit_fields():
    command = CommandAtom.objects.create(
        name="Legacy module", code="legacy-module", resource_kind="module"
    )
    notes = [{"name": "path", "description": "目标路径"}]
    serializer = CommandVersionSerializer(
        data={
            "command": command.pk,
            "version": 1,
            "command_type": "ansible_module",
            "content": "ansible.builtin.file",
            "argument_schema": {"x-module-parameter-docs": notes},
        }
    )
    assert serializer.is_valid(), serializer.errors
    version = serializer.save()
    assert version.module_name == "ansible.builtin.file"
    assert version.parameter_docs == notes
    assert version.content == ""
    assert version.argument_schema == {}


@pytest.mark.parametrize("modern", [True, False])
def test_new_and_old_frozen_module_snapshots_execute_the_same(modern):
    spec = SimpleNamespace(
        command_type="ansible_module",
        content="" if modern else "ansible.builtin.service",
        default_vars={},
        become_enabled=False,
    )
    if modern:
        spec.module_name = "ansible.builtin.service"
        spec.parameter_docs = [{"name": "name", "description": "reference only"}]
    node = SimpleNamespace(
        node_type="module",
        command_version=spec,
        config={"args": {"name": "nginx", "state": "started"}},
    )
    playbook = _node_playbook(SimpleNamespace(input_vars={}), node, spec, {})
    assert playbook[0]["tasks"][0]["ansible.builtin.service"] == {
        "name": "nginx",
        "state": "started",
    }


@pytest.mark.django_db
def test_inline_module_resource_rejects_conflicting_legacy_content():
    serializer = AnsibleNodeResourceCreateSerializer(
        data={
            "resourceKind": "module",
            "commandType": "ansible_module",
            "name": "Conflict",
            "code": "conflict-module",
            "moduleName": "ansible.builtin.file",
            "content": "ansible.builtin.service",
        }
    )
    assert not serializer.is_valid()
    assert "content" in serializer.errors


@pytest.mark.django_db
def test_data_migration_copies_legacy_fields_without_rewriting_published_data():
    migration = importlib.import_module("apps.automation.migrations.0012_module_fields")
    state = MigrationExecutor(connection).loader.project_state(
        ("automation", "0012_module_fields")
    )
    model = state.apps.get_model("automation", "CommandVersion")
    command = CommandAtom.objects.create(
        name="Migrated module", code="migrated-module", resource_kind="module"
    )
    schema = {"properties": {"name": {"type": "string", "description": "服务名称"}}}
    row = model.objects.create(
        command_id=command.pk,
        version=1,
        status="published",
        command_type="ansible_module",
        content="ansible.builtin.service",
        argument_schema=schema,
    )
    migration.copy_module_fields(state.apps, SimpleNamespace(connection=connection))
    row.refresh_from_db()
    assert row.module_name == "ansible.builtin.service"
    assert row.parameter_docs == [{"name": "name", "description": "服务名称"}]
    assert row.content == "ansible.builtin.service"
    assert row.argument_schema == schema


@pytest.mark.django_db
def test_reverse_migration_restores_new_module_definition_to_legacy_fields():
    migration = importlib.import_module("apps.automation.migrations.0012_module_fields")
    state = MigrationExecutor(connection).loader.project_state(
        ("automation", "0012_module_fields")
    )
    model = state.apps.get_model("automation", "CommandVersion")
    command = CommandAtom.objects.create(
        name="Rollback module", code="rollback-module", resource_kind="module"
    )
    notes = [{"name": "path", "description": "目标路径"}]
    row = model.objects.create(
        command_id=command.pk,
        version=1,
        command_type="ansible_module",
        module_name="ansible.builtin.file",
        parameter_docs=notes,
    )
    migration.restore_legacy_fields(state.apps, SimpleNamespace(connection=connection))
    row.refresh_from_db()
    assert row.content == "ansible.builtin.file"
    assert row.argument_schema == {"x-module-parameter-docs": notes}


@pytest.mark.django_db
def test_module_parameter_docs_reject_non_string_values():
    command = CommandAtom.objects.create(
        name="Strict module", code="strict-module", resource_kind="module"
    )
    serializer = CommandVersionSerializer(
        data={
            "command": command.pk,
            "version": 1,
            "command_type": "ansible_module",
            "module_name": "ansible.builtin.file",
            "parameter_docs": [{"name": 123, "description": "目标路径"}],
        }
    )
    assert not serializer.is_valid()
    assert "parameter_docs" in serializer.errors

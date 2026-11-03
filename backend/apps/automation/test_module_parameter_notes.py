import pytest

from apps.automation.models import CommandAtom
from apps.automation.serializers import CommandVersionSerializer


@pytest.mark.django_db
def test_module_notes_are_reference_metadata_not_execution_values():
    command = CommandAtom.objects.create(
        name="Module notes", code="module-notes", resource_kind="module"
    )
    notes = [{"name": "name", "description": "服务名称，如 nginx"}]
    serializer = CommandVersionSerializer(
        data={
            "command": command.pk,
            "version": 1,
            "command_type": "ansible_module",
            "content": "ansible.builtin.service",
            "argument_schema": {"x-module-parameter-docs": notes},
            "default_vars": {"module_args": {"name": "hidden-service"}},
            "become_enabled": True,
            "output_extractors": [],
            "timeout_seconds": 90,
        }
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["argument_schema"] == {}
    assert serializer.validated_data["parameter_docs"] == notes
    assert serializer.validated_data["default_vars"] == {}
    assert serializer.validated_data["become_enabled"] is False
    assert serializer.validated_data["timeout_seconds"] == 60


@pytest.mark.django_db
@pytest.mark.parametrize(
    "notes",
    [
        [{"name": "name", "description": "a"}, {"name": " name ", "description": "b"}],
        [{"name": "name", "description": ""}],
        [{"name": "", "description": "说明"}],
        {"name": "not a list"},
    ],
)
def test_module_notes_reject_duplicate_or_incomplete_entries(notes):
    command = CommandAtom.objects.create(
        name="Invalid notes", code="invalid-notes", resource_kind="module"
    )
    serializer = CommandVersionSerializer(
        data={
            "command": command.pk,
            "version": 1,
            "command_type": "ansible_module",
            "content": "ansible.builtin.service",
            "argument_schema": {"x-module-parameter-docs": notes},
        }
    )
    assert not serializer.is_valid()
    assert "argument_schema" in serializer.errors

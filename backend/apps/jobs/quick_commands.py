from django.db import transaction

from apps.automation.models import (
    CommandAtom,
    CommandVersion,
    WorkflowNode,
    WorkflowTemplate,
    WorkflowVersion,
)


QUICK_WORKFLOWS = {
    CommandVersion.CommandType.LINUX_SHELL: "__quick_linux_shell",
    CommandVersion.CommandType.WINDOWS_POWERSHELL: "__quick_windows_powershell",
}
QUICK_WORKFLOW_CODES = frozenset(QUICK_WORKFLOWS.values())


def is_quick_command_workflow_version(workflow_version) -> bool:
    return workflow_version.workflow.code in QUICK_WORKFLOW_CODES


def quick_command_risk_level(source_command_version):
    if source_command_version is None:
        return CommandAtom.RiskLevel.HIGH
    return source_command_version.command.risk_level


@transaction.atomic
def ensure_quick_command_workflows() -> dict[str, WorkflowVersion]:
    versions = {}
    for command_type, workflow_code in QUICK_WORKFLOWS.items():
        display_name = (
            "Quick Linux Shell"
            if command_type == CommandVersion.CommandType.LINUX_SHELL
            else "Quick Windows PowerShell"
        )
        command, _ = CommandAtom.objects.update_or_create(
            code=f"{workflow_code}_command",
            defaults={
                "name": display_name,
                "category": "system",
                "description": "Protected command used by quick-command runs.",
                "status": CommandAtom.Status.PUBLISHED,
                "risk_level": CommandAtom.RiskLevel.LOW,
            },
        )
        command_version, _ = CommandVersion.objects.update_or_create(
            command=command,
            version=1,
            defaults={
                "status": CommandVersion.Status.PUBLISHED,
                "command_type": command_type,
                "content": "{{ command_content }}",
            },
        )
        workflow, _ = WorkflowTemplate.objects.update_or_create(
            code=workflow_code,
            defaults={
                "name": display_name,
                "description": "Protected workflow used by quick-command runs.",
                "status": WorkflowTemplate.Status.PUBLISHED,
                "owner_team": "system",
            },
        )
        workflow_version, _ = WorkflowVersion.objects.update_or_create(
            workflow=workflow,
            version=1,
            defaults={
                "status": WorkflowVersion.Status.PUBLISHED,
                "input_schema": {
                    "type": "object",
                    "required": ["command_content"],
                    "properties": {"command_content": {"type": "string"}},
                },
            },
        )
        WorkflowNode.objects.update_or_create(
            workflow_version=workflow_version,
            node_key="quick_command",
            defaults={
                "name": display_name,
                "command_version": command_version,
                "order_index": 1,
            },
        )
        versions[command_type] = workflow_version
    return versions

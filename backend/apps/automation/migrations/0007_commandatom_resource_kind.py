from django.db import migrations, models


def classify_existing_resources(apps, schema_editor):
    command_atom = apps.get_model("automation", "CommandAtom")
    command_version = apps.get_model("automation", "CommandVersion")
    mappings = {
        "python": "script",
        "playbook": "playbook",
        "ansible_module": "module",
    }
    for command_type, resource_kind in mappings.items():
        command_ids = command_version.objects.filter(
            command_type=command_type
        ).values_list("command_id", flat=True)
        command_atom.objects.filter(id__in=command_ids).update(
            resource_kind=resource_kind
        )


class Migration(migrations.Migration):
    dependencies = [("automation", "0006_remove_legacy_task_models")]

    operations = [
        migrations.AddField(
            model_name="commandatom",
            name="resource_kind",
            field=models.CharField(
                choices=[
                    ("command", "Command"),
                    ("script", "Script"),
                    ("playbook", "Playbook"),
                    ("module", "Ansible Module"),
                ],
                db_index=True,
                default="command",
                max_length=16,
            ),
        ),
        migrations.RunPython(
            classify_existing_resources,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

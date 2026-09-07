from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0011_remove_legacy_ansible_task"),
        ("automation", "0002_change_node_command_version_to_cascade"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workflowrun",
            name="workflow_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="runs",
                to="automation.workflowversion",
            ),
        ),
        migrations.AlterField(
            model_name="scheduledjob",
            name="workflow_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="scheduled_jobs",
                to="automation.workflowversion",
            ),
        ),
        migrations.AlterField(
            model_name="noderun",
            name="workflow_node",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="node_runs",
                to="automation.workflownode",
            ),
        ),
        migrations.AlterField(
            model_name="noderun",
            name="command_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="node_runs",
                to="automation.commandversion",
            ),
        ),
    ]

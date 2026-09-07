from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0006_execution_governance_db_defaults"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workflowrun",
            name="trigger_type",
            field=models.CharField(
                choices=[
                    ("manual", "Manual"),
                    ("api", "API"),
                    ("scheduled", "Scheduled"),
                    ("ansible_task", "Ansible task"),
                ],
                default="manual",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="workflowrun",
            name="workflow_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="runs",
                to="automation.workflowversion",
            ),
        ),
        migrations.AddField(
            model_name="workflowrun",
            name="ansible_request",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

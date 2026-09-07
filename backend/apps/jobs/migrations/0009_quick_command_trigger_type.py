from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0008_scheduled_job"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workflowrun",
            name="trigger_type",
            field=models.CharField(
                choices=[
                    ("manual", "Manual"),
                    ("quick_command", "Quick command"),
                    ("api", "API"),
                    ("scheduled", "Scheduled"),
                    ("ansible_task", "Ansible task"),
                ],
                default="manual",
                max_length=16,
            ),
        ),
    ]

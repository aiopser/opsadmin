from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0010_default_worker_pool_queue"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="workflowrun",
            name="ansible_request",
        ),
        migrations.AlterField(
            model_name="workflowrun",
            name="trigger_type",
            field=models.CharField(
                choices=[
                    ("manual", "Manual"),
                    ("quick_command", "Quick command"),
                    ("api", "API"),
                    ("scheduled", "Scheduled"),
                ],
                default="manual",
                max_length=16,
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0004_hostname_result_idempotency"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workflowrun",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("queued", "Queued"),
                    ("running", "Running"),
                    ("success", "Success"),
                    ("failed", "Failed"),
                    ("timeout", "Timeout"),
                    ("cancel_requested", "Cancel requested"),
                    ("canceled", "Canceled"),
                ],
                default="pending",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="workflowrun",
            name="cancel_requested_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workflowrun",
            name="celery_task_id",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="workflowrun",
            name="heartbeat_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workflowrun",
            name="runner_workspace",
            field=models.CharField(blank=True, default="", max_length=512),
        ),
        migrations.AddField(
            model_name="workflowrun",
            name="timeout_seconds",
            field=models.PositiveIntegerField(default=3600),
        ),
        migrations.AddField(
            model_name="workflowrun",
            name="worker_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]

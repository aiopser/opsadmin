from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jobs", "0019_workflow_run_domain")]

    operations = [
        migrations.AddField(
            model_name="scheduledjob",
            name="host_strategy",
            field=models.CharField(
                choices=[
                    ("parallel", "Parallel"),
                    ("serial", "Serial"),
                    ("rolling", "Rolling"),
                ],
                default="parallel",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="scheduledjob",
            name="forks",
            field=models.PositiveIntegerField(default=10),
        ),
        migrations.AddField(
            model_name="scheduledjob",
            name="serial_batch",
            field=models.PositiveIntegerField(default=5),
        ),
        migrations.AddField(
            model_name="scheduledjob",
            name="max_fail_percentage",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="scheduledjob",
            name="timeout_seconds",
            field=models.PositiveIntegerField(default=300),
        ),
        migrations.AddField(
            model_name="scheduledjob",
            name="queue_timeout_seconds",
            field=models.PositiveIntegerField(default=120),
        ),
        migrations.AddField(
            model_name="scheduledjob",
            name="bypass_host_gateway",
            field=models.BooleanField(default=False),
        ),
    ]

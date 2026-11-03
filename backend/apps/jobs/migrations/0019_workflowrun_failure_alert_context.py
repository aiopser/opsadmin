from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0018_scheduledjob_expires_at_scheduledjob_remark_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="workflowrun",
            name="failure_alert_context",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

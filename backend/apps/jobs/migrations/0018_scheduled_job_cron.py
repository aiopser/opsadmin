from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jobs", "0017_workflow_secret_inputs")]

    operations = [
        migrations.RemoveField(model_name="scheduledjob", name="interval_minutes"),
        migrations.AddField(
            model_name="scheduledjob",
            name="cron_expression",
            field=models.CharField(default="0 * * * *", max_length=128),
        ),
        migrations.AddField(
            model_name="scheduledjob",
            name="timezone",
            field=models.CharField(default="Asia/Shanghai", max_length=64),
        ),
        migrations.AddField(
            model_name="scheduledjob",
            name="input_vars",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

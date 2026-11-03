from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("automation", "0006_notificationchannel_feishu")]

    operations = [
        migrations.AddField(
            model_name="notificationtemplate",
            name="alert_on_run_failure",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="notificationrecord",
            name="alert_key",
            field=models.CharField(blank=True, max_length=128, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="notificationrecord",
            name="attempt_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="notificationrecord",
            name="claimed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notificationrecord",
            name="next_retry_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="notificationrecord",
            name="status",
            field=models.CharField(
                max_length=16,
                default="pending",
                choices=[
                    ("pending", "Pending"),
                    ("success", "Success"),
                    ("failed", "Failed"),
                    ("sending", "Sending"),
                ],
            ),
        ),
    ]

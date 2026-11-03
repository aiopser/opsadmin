from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jobs", "0016_explicit_gateway_only")]

    operations = [
        migrations.AddField(
            model_name="workflowrun", name="failure_alert",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="workflowtaskticket", name="failure_alert",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
    ]

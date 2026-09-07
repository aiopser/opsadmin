from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cmdb", "0003_asset_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="hostgroup",
            name="group_type",
            field=models.CharField(
                choices=[("static", "Static"), ("dynamic", "Dynamic")],
                default="static",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="hostgroup",
            name="match_rule",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="hostgroup",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
    ]

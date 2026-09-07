from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0013_commandintercept_gateway_playbook_securityrule"),
        ("cmdb", "0007_remove_execution_zone"),
    ]

    operations = [
        migrations.AddField(
            model_name="assethost",
            name="default_gateway",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="hosts",
                to="jobs.gateway",
            ),
        ),
    ]

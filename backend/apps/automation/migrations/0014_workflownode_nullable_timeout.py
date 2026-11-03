from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("automation", "0013_remove_workflowversion_global_vars")]
    operations = [
        migrations.AlterField(
            model_name="workflownode",
            name="timeout_seconds",
            field=models.IntegerField(default=None, null=True, blank=True),
        )
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cmdb", "0006_merge_service_tree_into_host_groups")]

    operations = [
        migrations.AlterField(
            model_name="assetsyncrecord",
            name="status",
            field=models.CharField(
                max_length=16,
                default="queued",
                choices=[
                    ("queued", "Queued"),
                    ("running", "Running"),
                    ("succeeded", "Succeeded"),
                    ("partial", "Partial"),
                    ("failed", "Failed"),
                ],
            ),
        ),
    ]

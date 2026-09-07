from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("cmdb", "0006_credential_enhancement")]

    operations = [
        migrations.RemoveField(
            model_name="assethost",
            name="execution_zone",
        ),
        migrations.RemoveField(
            model_name="workerpool",
            name="execution_zone",
        ),
        migrations.DeleteModel(name="ExecutionZone"),
    ]

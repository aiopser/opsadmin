from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ansible_platform", "0001_initial"),
    ]

    operations = [migrations.DeleteModel(name="TaskExecution")]

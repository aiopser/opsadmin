from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0002_domainauditevent"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hostrunresult",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("running", "Running"),
                    ("ok", "Ok"),
                    ("changed", "Changed"),
                    ("failed", "Failed"),
                    ("unreachable", "Unreachable"),
                    ("skipped", "Skipped"),
                    ("canceled", "Canceled"),
                ],
                default="pending",
                max_length=16,
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0016_graph_runtime"),
    ]

    operations = [
        migrations.AddField(
            model_name="workflowrun",
            name="secret_input_vars_encrypted",
            field=models.TextField(blank=True, default=""),
        ),
    ]

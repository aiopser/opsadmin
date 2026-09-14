from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0003_remove_workflowrun_runner_workspace_runlogchunk'),
    ]

    operations = [
        migrations.AddField(
            model_name='workerpool',
            name='region',
            field=models.CharField(blank=True, db_index=True, default='', max_length=64),
        ),
    ]

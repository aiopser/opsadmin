from django.db import migrations


def apply_mysql_defaults(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    schema_editor.execute(
        """
        ALTER TABLE jobs_workflow_run
            MODIFY celery_task_id varchar(255) NOT NULL DEFAULT '',
            MODIFY worker_name varchar(255) NOT NULL DEFAULT '',
            MODIFY timeout_seconds int UNSIGNED NOT NULL DEFAULT 3600,
            MODIFY runner_workspace varchar(512) NOT NULL DEFAULT ''
        """
    )


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0005_execution_governance"),
    ]

    operations = [
        migrations.RunPython(apply_mysql_defaults, migrations.RunPython.noop),
    ]

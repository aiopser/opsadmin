from django.db import migrations


LEGACY_TABLES = (
    "automation_task_node_run",
    "automation_task_run",
    "automation_task_subtask",
    "automation_task_template",
)


def drop_legacy_task_tables(apps, schema_editor):
    existing_tables = set(schema_editor.connection.introspection.table_names())
    for table_name in LEGACY_TABLES:
        if table_name not in existing_tables:
            continue
        quoted_name = schema_editor.connection.ops.quote_name(table_name)
        schema_editor.execute(f"DROP TABLE {quoted_name}")


class Migration(migrations.Migration):
    dependencies = [("automation", "0010_workflow_version_editor_mode")]

    operations = [
        migrations.RunPython(drop_legacy_task_tables, migrations.RunPython.noop),
    ]

from django.db import migrations, models


def legacy_notes(schema):
    if not isinstance(schema, dict):
        return []
    if "x-module-parameter-docs" in schema:
        notes = schema["x-module-parameter-docs"]
        return notes if isinstance(notes, list) else []
    properties = schema.get("properties", schema)
    if not isinstance(properties, dict):
        return []
    return [
        {"name": name, "description": str(value.get("description") or "")}
        for name, value in properties.items()
        if name not in {"properties", "required"} and isinstance(value, dict)
    ]


def copy_module_fields(apps, schema_editor):
    versions = apps.get_model("automation", "CommandVersion").objects.using(
        schema_editor.connection.alias
    )
    for row in versions.filter(command_type="ansible_module").iterator(chunk_size=500):
        changes = {}
        if not row.module_name:
            changes["module_name"] = row.content.strip()
        if not row.parameter_docs:
            changes["parameter_docs"] = legacy_notes(row.argument_schema)
        if changes:
            versions.filter(pk=row.pk).update(**changes)


def restore_legacy_fields(apps, schema_editor):
    versions = apps.get_model("automation", "CommandVersion").objects.using(
        schema_editor.connection.alias
    )
    for row in versions.filter(command_type="ansible_module").iterator(chunk_size=500):
        changes = {}
        if not row.content:
            changes["content"] = row.module_name
        if not row.argument_schema and row.parameter_docs:
            changes["argument_schema"] = {"x-module-parameter-docs": row.parameter_docs}
        if changes:
            versions.filter(pk=row.pk).update(**changes)


class Migration(migrations.Migration):
    dependencies = [("automation", "0011_notificationrecord_notif_status_sent_idx")]
    operations = [
        migrations.AlterField(
            model_name="commandversion",
            name="content",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="commandversion",
            name="module_name",
            field=models.CharField(max_length=255, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="commandversion",
            name="parameter_docs",
            field=models.JSONField(default=list, blank=True),
        ),
        migrations.RunPython(copy_module_fields, restore_legacy_fields),
    ]

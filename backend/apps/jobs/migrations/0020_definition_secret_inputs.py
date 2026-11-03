import json

from django.db import migrations, models


def protect_existing_definitions(apps, schema_editor):
    from apps.cmdb.crypto import encrypt_secret

    for name in ("WorkflowTaskTicket", "ScheduledJob"):
        Model = apps.get_model("jobs", name)
        for record in Model.objects.select_related("workflow_version").iterator(
            chunk_size=100
        ):
            version = record.workflow_version
            schema = version.input_schema if version is not None else []
            fields = schema.get("fields", []) if isinstance(schema, dict) else schema
            secret_names = {
                item.get("name")
                for item in fields or []
                if isinstance(item, dict) and item.get("type") == "secret"
            }
            values = dict(record.input_vars or {})
            if version is None:
                # With the defining schema gone, no field can safely be
                # classified as public. Preserve every value encrypted.
                secret_names = set(values)
            secrets = {
                key: values[key]
                for key in secret_names
                if key in values and values[key] not in (None, "")
            }
            if not secrets:
                continue
            cipher = encrypt_secret(json.dumps(secrets, ensure_ascii=False))
            for key in secrets:
                values[key] = "[REDACTED]"
            Model.objects.filter(pk=record.pk).update(
                input_vars=values, secret_input_vars_encrypted=cipher
            )


class Migration(migrations.Migration):
    dependencies = [("jobs", "0019_workflowrun_failure_alert_context")]
    operations = [
        migrations.AddField(
            "workflowtaskticket",
            "secret_input_vars_encrypted",
            models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            "scheduledjob",
            "secret_input_vars_encrypted",
            models.TextField(blank=True, default=""),
        ),
        migrations.RunPython(protect_existing_definitions),
    ]

from django.db import migrations, models


def host_key_for(host_id, hostname):
    if host_id is not None:
        return f"id:{host_id}"
    return f"name:{hostname}"


def case_insensitive_host_key(host_key):
    return host_key.lower()


def backfill_and_deduplicate_host_keys(apps, schema_editor):
    HostRunResult = apps.get_model("jobs", "HostRunResult")
    seen = set()
    duplicate_ids = []

    results = HostRunResult.objects.order_by(
        "node_run_id",
        "-updated_at",
        "-id",
    )
    for result in results.iterator():
        host_key = host_key_for(result.host_id, result.hostname)
        uniqueness_key = (result.node_run_id, case_insensitive_host_key(host_key))
        if uniqueness_key in seen:
            duplicate_ids.append(result.id)
            continue
        seen.add(uniqueness_key)
        HostRunResult.objects.filter(id=result.id).update(host_key=host_key)

    if duplicate_ids:
        HostRunResult.objects.filter(id__in=duplicate_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0003_realtime_run_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="hostrunresult",
            name="host_key",
            field=models.CharField(max_length=140, null=True),
        ),
        migrations.RunPython(
            backfill_and_deduplicate_host_keys,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="hostrunresult",
            name="host_key",
            field=models.CharField(max_length=140),
        ),
        migrations.AddConstraint(
            model_name="hostrunresult",
            constraint=models.UniqueConstraint(
                fields=("node_run", "host_key"),
                name="jobs_unique_node_host_key",
            ),
        ),
    ]

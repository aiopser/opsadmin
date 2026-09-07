from django.db import migrations


def normalize_default_worker_pool_queue(apps, schema_editor):
    WorkerPool = apps.get_model("cmdb", "WorkerPool")
    WorkerPool.objects.filter(
        code="default",
        queue_name="ansible.default",
    ).update(queue_name="ansible")


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0009_quick_command_trigger_type"),
    ]

    operations = [
        migrations.RunPython(
            normalize_default_worker_pool_queue,
            migrations.RunPython.noop,
        ),
    ]

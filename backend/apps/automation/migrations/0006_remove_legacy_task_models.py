from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("automation", "0005_migrate_legacy_tasks_to_workflows"),
    ]

    operations = [
        # Remove the legacy models from Django's state, but retain their physical
        # tables for one release as a rollback/audit safety net. A later, explicit
        # cleanup migration may drop them after production acceptance.
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="TaskNodeRun"),
                migrations.DeleteModel(name="TaskRun"),
                migrations.DeleteModel(name="TaskSubtask"),
                migrations.DeleteModel(name="TaskTemplate"),
            ],
        ),
    ]

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("audit_center", "0001_initial"),
        ("jobs", "0023_unify_execution_resources"),
    ]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[migrations.DeleteModel(name="DomainAuditEvent")],
        ),
    ]

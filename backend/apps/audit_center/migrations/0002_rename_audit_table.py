from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("audit_center", "0001_initial"),
        ("jobs", "0024_move_audit_event_to_audit_center"),
    ]
    operations = [
        migrations.AlterModelTable(
            name="domainauditevent",
            table="audit_center_event",
        ),
    ]

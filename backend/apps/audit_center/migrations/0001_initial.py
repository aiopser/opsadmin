from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="DomainAuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("domain", models.CharField(choices=[("ops", "Ops system"), ("task", "Task system"), ("automation", "Automation resources"), ("cmdb", "Asset management"), ("security", "Security"), ("system", "System")], db_index=True, default="system", max_length=32)),
                ("action", models.CharField(db_index=True, max_length=64)),
                ("resource_type", models.CharField(db_index=True, max_length=64)),
                ("resource_id", models.CharField(blank=True, default="", max_length=64)),
                ("before", models.JSONField(blank=True, default=dict)),
                ("after", models.JSONField(blank=True, default=dict)),
                ("request_id", models.CharField(blank=True, default="", max_length=128)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, default="", max_length=255)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="domain_audit_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "audit_center_event", "ordering": ["-id"]},
        ),
    ]

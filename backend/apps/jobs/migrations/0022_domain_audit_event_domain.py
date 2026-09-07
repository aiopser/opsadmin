from django.db import migrations, models


def classify_existing_events(apps, schema_editor):
    AuditEvent = apps.get_model("jobs", "DomainAuditEvent")
    WorkflowRun = apps.get_model("jobs", "WorkflowRun")
    run_domains = dict(WorkflowRun.objects.values_list("id", "run_domain"))
    for event in AuditEvent.objects.all().iterator():
        action = event.action or ""
        if action.startswith("cmdb."):
            domain = "cmdb"
        elif action.startswith("automation."):
            domain = "automation"
        elif action.startswith(("quick_command_run.", "playbook_run.", "module_run.")):
            domain = "ops"
        elif event.resource_type == "workflow_run":
            try:
                domain = run_domains.get(int(event.resource_id), "system")
            except (TypeError, ValueError):
                domain = "system"
        elif action.startswith(("security.", "command_intercept.")):
            domain = "security"
        else:
            domain = "system"
        AuditEvent.objects.filter(pk=event.pk).update(domain=domain)


class Migration(migrations.Migration):
    dependencies = [("jobs", "0021_auto_20260812_1749")]

    operations = [
        migrations.AddField(
            model_name="domainauditevent",
            name="domain",
            field=models.CharField(
                choices=[
                    ("ops", "Ops system"),
                    ("task", "Task system"),
                    ("automation", "Automation resources"),
                    ("cmdb", "Asset management"),
                    ("security", "Security"),
                    ("system", "System"),
                ],
                db_index=True,
                default="system",
                max_length=32,
            ),
        ),
        migrations.RunPython(classify_existing_events, migrations.RunPython.noop),
    ]

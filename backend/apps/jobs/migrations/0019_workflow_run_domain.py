from django.db import migrations, models


OPS_SOURCES = {"quick_command", "playbook", "module"}


def classify_existing_runs(apps, schema_editor):
    WorkflowRun = apps.get_model("jobs", "WorkflowRun")
    for run in WorkflowRun.objects.all().iterator(chunk_size=500):
        input_vars = run.input_vars if isinstance(run.input_vars, dict) else {}
        source = str(input_vars.get("execution_source") or "").strip()
        is_ops = run.trigger_type == "quick_command" or source in OPS_SOURCES
        execution_kind = source if source in OPS_SOURCES else "workflow"
        update_fields = {
            "run_domain": "ops" if is_ops else "task",
            "execution_kind": execution_kind,
        }
        if run.trigger_type == "quick_command":
            update_fields["trigger_type"] = "manual"
        WorkflowRun.objects.filter(pk=run.pk).update(**update_fields)


class Migration(migrations.Migration):
    dependencies = [("jobs", "0018_scheduled_job_cron")]

    operations = [
        migrations.AddField(
            model_name="workflowrun",
            name="run_domain",
            field=models.CharField(
                choices=[("task", "Task system"), ("ops", "Ops system")],
                db_index=True,
                default="task",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="workflowrun",
            name="execution_kind",
            field=models.CharField(
                choices=[
                    ("workflow", "Workflow"),
                    ("quick_command", "Quick command"),
                    ("playbook", "Playbook"),
                    ("module", "Module"),
                ],
                db_index=True,
                default="workflow",
                max_length=32,
            ),
        ),
        migrations.RunPython(classify_existing_runs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="workflowrun",
            name="trigger_type",
            field=models.CharField(
                choices=[
                    ("manual", "Manual"),
                    ("api", "API"),
                    ("scheduled", "Scheduled"),
                ],
                default="manual",
                max_length=16,
            ),
        ),
        migrations.AddIndex(
            model_name="workflowrun",
            index=models.Index(
                fields=["run_domain", "status"],
                name="jobs_run_domain_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="workflowrun",
            index=models.Index(
                fields=["run_domain", "created_at"],
                name="jobs_run_domain_created_idx",
            ),
        ),
    ]

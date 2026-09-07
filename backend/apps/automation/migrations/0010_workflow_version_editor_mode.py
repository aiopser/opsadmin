from django.db import migrations, models


def classify_existing_versions(apps, schema_editor):
    WorkflowVersion = apps.get_model("automation", "WorkflowVersion")
    WorkflowVersion.objects.exclude(bpmn_xml="").update(editor_mode="bpmn")


class Migration(migrations.Migration):
    dependencies = [("automation", "0009_jenkins_jobs_builds")]

    operations = [
        migrations.AddField(
            model_name="workflowversion",
            name="editor_mode",
            field=models.CharField(
                choices=[("steps", "Steps"), ("bpmn", "BPMN")],
                default="steps",
                max_length=16,
            ),
        ),
        migrations.RunPython(classify_existing_versions, migrations.RunPython.noop),
    ]

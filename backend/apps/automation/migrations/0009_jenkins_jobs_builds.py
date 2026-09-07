from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("automation", "0008_api_outputs_notification_templates"),
        ("jobs", "0017_workflow_secret_inputs"),
    ]

    operations = [
        migrations.CreateModel(
            name="JenkinsJob",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="创建时间"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="更新时间"),
                ),
                ("name", models.CharField(max_length=512)),
                ("url", models.URLField(blank=True, default="", max_length=2048)),
                ("color", models.CharField(blank=True, default="", max_length=32)),
                ("parameters", models.JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                (
                    "server",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="jobs",
                        to="automation.jenkinsserver",
                    ),
                ),
            ],
            options={
                "db_table": "automation_jenkins_job",
                "ordering": ["server_id", "name"],
                "unique_together": {("server", "name")},
            },
        ),
        migrations.CreateModel(
            name="JenkinsBuild",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="创建时间"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="更新时间"),
                ),
                ("build_number", models.PositiveIntegerField(blank=True, null=True)),
                ("queue_url", models.URLField(blank=True, default="", max_length=2048)),
                ("build_url", models.URLField(blank=True, default="", max_length=2048)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("aborted", "Aborted"),
                        ],
                        default="queued",
                        max_length=16,
                    ),
                ),
                ("result", models.CharField(blank=True, default="", max_length=32)),
                ("parameters", models.JSONField(blank=True, default=dict)),
                ("console_output", models.TextField(blank=True, default="")),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="builds",
                        to="automation.jenkinsjob",
                    ),
                ),
                (
                    "workflow_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="jenkins_builds",
                        to="jobs.workflowrun",
                    ),
                ),
                (
                    "node_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="jenkins_builds",
                        to="jobs.noderun",
                    ),
                ),
            ],
            options={"db_table": "automation_jenkins_build", "ordering": ["-id"]},
        ),
    ]

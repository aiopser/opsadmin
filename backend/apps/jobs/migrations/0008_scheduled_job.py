from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("automation", "0001_initial"),
        ("cmdb", "0001_initial"),
        ("jobs", "0007_ansible_task_workflow_run"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScheduledJob",
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
                ("name", models.CharField(max_length=128)),
                ("host_ids", models.JSONField(blank=True, default=list)),
                ("interval_minutes", models.PositiveIntegerField(default=60)),
                ("enabled", models.BooleanField(default=True)),
                (
                    "next_run_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_scheduled_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "last_workflow_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="scheduled_job_results",
                        to="jobs.workflowrun",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_scheduled_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "worker_pool",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="scheduled_jobs",
                        to="cmdb.workerpool",
                    ),
                ),
                (
                    "workflow_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="scheduled_jobs",
                        to="automation.workflowversion",
                    ),
                ),
            ],
            options={
                "db_table": "jobs_scheduled_job",
                "ordering": ["enabled", "next_run_at", "-id"],
            },
        ),
    ]

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("jobs", "0008_scheduledjob_last_skip_reason_and_more")]

    operations = [
        migrations.CreateModel(
            name="RunLogArchiveRequest",
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
                ("sequence", models.PositiveBigIntegerField()),
                ("content_encrypted", models.TextField()),
                ("reserved_bytes", models.PositiveIntegerField(default=0)),
                ("content_truncated", models.BooleanField(default=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("stored", "Stored"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("retry_count", models.PositiveIntegerField(default=0)),
                (
                    "next_attempt_at",
                    models.DateTimeField(
                        db_index=True, default=django.utils.timezone.now
                    ),
                ),
                (
                    "last_error_type",
                    models.CharField(blank=True, default="", max_length=128),
                ),
                (
                    "workflow_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="log_archive_requests",
                        to="jobs.workflowrun",
                    ),
                ),
            ],
            options={
                "db_table": "jobs_run_log_archive_request",
            },
        ),
        migrations.AddConstraint(
            model_name="runlogarchiverequest",
            constraint=models.UniqueConstraint(
                fields=("workflow_run", "sequence"),
                name="jobs_archive_request_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="runlogarchiverequest",
            index=models.Index(
                fields=["status", "next_attempt_at"], name="jobs_archive_due_idx"
            ),
        ),
    ]

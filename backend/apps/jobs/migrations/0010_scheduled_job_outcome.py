import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("jobs", "0009_run_log_archive_request")]

    operations = [
        migrations.CreateModel(
            name="ScheduledJobOutcome",
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
                ("scheduled_for", models.DateTimeField()),
                (
                    "outcome",
                    models.CharField(
                        choices=[
                            ("dispatched", "Dispatched"),
                            ("overlap_skipped", "Overlap skipped"),
                            ("overlap_queued", "Overlap queued"),
                            ("misfire_skipped", "Misfire skipped"),
                            ("invalid", "Invalid"),
                        ],
                        max_length=32,
                    ),
                ),
                ("reason", models.CharField(blank=True, default="", max_length=255)),
                (
                    "scheduled_job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outcomes",
                        to="jobs.scheduledjob",
                    ),
                ),
                (
                    "workflow_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="schedule_outcomes",
                        to="jobs.workflowrun",
                    ),
                ),
            ],
            options={
                "db_table": "jobs_scheduled_job_outcome",
                "ordering": ["-scheduled_for", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="scheduledjoboutcome",
            constraint=models.UniqueConstraint(
                fields=("scheduled_job", "scheduled_for"),
                name="jobs_schedule_outcome_unique",
            ),
        ),
    ]

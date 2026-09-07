from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("jobs", "0015_module_catalog"),
    ]

    operations = [
        migrations.AddField(
            model_name="workflowrun",
            name="context_vars",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="workflowrun",
            name="graph_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="workflowrun",
            name="queue_timeout_seconds",
            field=models.PositiveIntegerField(default=120),
        ),
        migrations.AddField(
            model_name="workflowrun",
            name="queue_deadline_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workflowrun",
            name="workflow_deadline_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="workflowrun",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("queued", "Queued"),
                    ("running", "Running"),
                    ("waiting", "Waiting"),
                    ("success", "Success"),
                    ("failed", "Failed"),
                    ("timeout", "Timeout"),
                    ("cancel_requested", "Cancel requested"),
                    ("canceled", "Canceled"),
                ],
                default="pending",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="noderun",
            name="node_key",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="noderun",
            name="node_name",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="noderun",
            name="node_type",
            field=models.CharField(blank=True, default="command", max_length=32),
        ),
        migrations.AddField(
            model_name="noderun",
            name="config_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="noderun",
            name="attempt_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="noderun",
            name="celery_task_id",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="noderun",
            name="queued_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="noderun",
            name="heartbeat_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="noderun",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("queued", "Queued"),
                    ("running", "Running"),
                    ("waiting_approval", "Waiting approval"),
                    ("success", "Success"),
                    ("failed", "Failed"),
                    ("skipped", "Skipped"),
                    ("ignored", "Ignored"),
                    ("timeout", "Timeout"),
                    ("canceled", "Canceled"),
                ],
                default="pending",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="NodeRunAttempt",
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
                ("attempt", models.PositiveIntegerField(default=1)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("timeout", "Timeout"),
                            ("canceled", "Canceled"),
                        ],
                        default="queued",
                        max_length=16,
                    ),
                ),
                (
                    "celery_task_id",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("queue_name", models.CharField(blank=True, default="", max_length=64)),
                (
                    "worker_name",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("duration_ms", models.IntegerField(blank=True, null=True)),
                ("exit_code", models.IntegerField(blank=True, null=True)),
                ("output_vars", models.JSONField(blank=True, default=dict)),
                ("failure_reason", models.TextField(blank=True, default="")),
                (
                    "node_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attempts",
                        to="jobs.noderun",
                    ),
                ),
            ],
            options={
                "db_table": "jobs_node_run_attempt",
                "ordering": ["node_run_id", "attempt"],
                "unique_together": {("node_run", "attempt")},
            },
        ),
        migrations.CreateModel(
            name="ApprovalRecord",
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
                (
                    "decision",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("expired", "Expired"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("comment", models.TextField(blank=True, default="")),
                ("acted_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                (
                    "approver",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="workflow_approvals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "node_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approvals",
                        to="jobs.noderun",
                    ),
                ),
            ],
            options={"db_table": "jobs_approval_record", "ordering": ["-id"]},
        ),
        migrations.AddConstraint(
            model_name="approvalrecord",
            constraint=models.UniqueConstraint(
                fields=("node_run", "approver"), name="jobs_unique_node_approver"
            ),
        ),
    ]

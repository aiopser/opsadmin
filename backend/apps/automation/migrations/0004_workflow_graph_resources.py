from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("automation", "0003_tasknoderun_taskrun_tasksubtask_tasktemplate"),
    ]

    operations = [
        migrations.AddField(
            model_name="workflowversion",
            name="bpmn_xml",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="workflowversion",
            name="graph_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="workflowversion",
            name="validation_report",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="workflowversion",
            name="published_hash",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="workflownode",
            name="command_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="workflow_nodes",
                to="automation.commandversion",
            ),
        ),
        migrations.AddField(
            model_name="workflownode",
            name="node_type",
            field=models.CharField(
                choices=[
                    ("start", "Start"),
                    ("end", "End"),
                    ("command", "Command"),
                    ("script", "Script"),
                    ("playbook", "Playbook"),
                    ("module", "Ansible Module"),
                    ("api", "API"),
                    ("jenkins", "Jenkins"),
                    ("approval", "Approval"),
                    ("notify", "Notification"),
                    ("exclusive_gateway", "Exclusive Gateway"),
                    ("parallel_gateway", "Parallel Gateway"),
                    ("parallel_join", "Parallel Join"),
                ],
                default="command",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="workflownode",
            name="resource_type",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="workflownode",
            name="resource_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workflownode",
            name="config",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="workflownode",
            name="input_schema",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="workflownode",
            name="output_schema",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="workflownode",
            name="retry_policy",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="workflownode",
            name="failure_policy",
            field=models.CharField(
                choices=[
                    ("stop", "Stop workflow"),
                    ("ignore", "Ignore and continue"),
                    ("retry", "Retry"),
                ],
                default="stop",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="WorkflowEdge",
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
                ("edge_key", models.CharField(max_length=64)),
                ("condition_expression", models.TextField(blank=True, default="")),
                ("is_default", models.BooleanField(default=False)),
                ("order_index", models.PositiveIntegerField(default=0)),
                (
                    "source_node",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outgoing_edges",
                        to="automation.workflownode",
                    ),
                ),
                (
                    "target_node",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incoming_edges",
                        to="automation.workflownode",
                    ),
                ),
                (
                    "workflow_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="edges",
                        to="automation.workflowversion",
                    ),
                ),
            ],
            options={
                "db_table": "automation_workflow_edge",
                "ordering": ["workflow_version_id", "order_index", "id"],
                "unique_together": {("workflow_version", "edge_key")},
            },
        ),
        migrations.CreateModel(
            name="ApiEndpoint",
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
                ("description", models.TextField(blank=True, default="")),
                ("method", models.CharField(default="GET", max_length=16)),
                ("url", models.URLField(max_length=2048)),
                ("query_params", models.JSONField(blank=True, default=list)),
                ("headers", models.JSONField(blank=True, default=list)),
                ("cookies", models.JSONField(blank=True, default=list)),
                (
                    "body_type",
                    models.CharField(
                        choices=[
                            ("none", "None"),
                            ("json", "JSON"),
                            ("form", "Form"),
                            ("raw", "Raw"),
                        ],
                        default="none",
                        max_length=16,
                    ),
                ),
                ("body", models.TextField(blank=True, default="")),
                (
                    "auth_type",
                    models.CharField(
                        choices=[
                            ("none", "None"),
                            ("basic", "Basic"),
                            ("bearer", "Bearer"),
                            ("api_key", "API key"),
                        ],
                        default="none",
                        max_length=16,
                    ),
                ),
                ("username", models.CharField(blank=True, default="", max_length=255)),
                ("secret_encrypted", models.TextField(blank=True, default="")),
                (
                    "api_key_name",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "api_key_location",
                    models.CharField(blank=True, default="header", max_length=16),
                ),
                ("success_rules", models.JSONField(blank=True, default=dict)),
                ("timeout_seconds", models.PositiveIntegerField(default=30)),
                ("verify_ssl", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_api_endpoints",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_api_endpoints",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "automation_api_endpoint", "ordering": ["name", "id"]},
        ),
        migrations.CreateModel(
            name="JenkinsServer",
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
                ("base_url", models.URLField(max_length=2048)),
                ("username", models.CharField(blank=True, default="", max_length=255)),
                ("token_encrypted", models.TextField(blank=True, default="")),
                ("verify_ssl", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_jenkins_servers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_jenkins_servers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "automation_jenkins_server",
                "ordering": ["name", "id"],
            },
        ),
        migrations.CreateModel(
            name="NotificationChannel",
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
                (
                    "channel_type",
                    models.CharField(
                        choices=[
                            ("webhook", "Webhook"),
                            ("wecom", "WeCom"),
                            ("dingtalk", "DingTalk"),
                            ("email", "Email"),
                        ],
                        max_length=16,
                    ),
                ),
                ("config", models.JSONField(blank=True, default=dict)),
                ("secret_encrypted", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_notification_channels",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_notification_channels",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "automation_notification_channel",
                "ordering": ["name", "id"],
            },
        ),
        migrations.CreateModel(
            name="ApprovalPolicy",
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
                ("description", models.TextField(blank=True, default="")),
                (
                    "approval_mode",
                    models.CharField(
                        choices=[("any", "Any approver"), ("all", "All approvers")],
                        default="any",
                        max_length=16,
                    ),
                ),
                ("approver_user_ids", models.JSONField(blank=True, default=list)),
                ("approver_role_ids", models.JSONField(blank=True, default=list)),
                ("timeout_seconds", models.PositiveIntegerField(default=86400)),
                (
                    "timeout_action",
                    models.CharField(
                        choices=[("reject", "Reject"), ("approve", "Approve")],
                        default="reject",
                        max_length=16,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_approval_policies",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_approval_policies",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "automation_approval_policy",
                "ordering": ["name", "id"],
            },
        ),
    ]

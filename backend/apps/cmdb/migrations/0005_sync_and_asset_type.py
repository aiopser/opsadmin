from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("cmdb", "0004_dynamic_host_group")]

    operations = [
        migrations.AddField(
            model_name="assethost",
            name="asset_type",
            field=models.CharField(
                choices=[
                    ("server", "Server"),
                    ("virtual_machine", "Virtual Machine"),
                    ("cloud_instance", "Cloud Instance"),
                ],
                default="server",
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="AssetSyncRecord",
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
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                        ],
                        default="queued",
                        max_length=16,
                    ),
                ),
                ("task_id", models.CharField(blank=True, default="", max_length=128)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("total_count", models.PositiveIntegerField(default=0)),
                ("created_count", models.PositiveIntegerField(default=0)),
                ("updated_count", models.PositiveIntegerField(default=0)),
                ("skipped_count", models.PositiveIntegerField(default=0)),
                ("error_message", models.TextField(blank=True, default="")),
                ("payload", models.JSONField(default=list, blank=True)),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sync_records",
                        to="cmdb.assetsource",
                    ),
                ),
            ],
            options={
                "db_table": "cmdb_asset_sync_record",
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]

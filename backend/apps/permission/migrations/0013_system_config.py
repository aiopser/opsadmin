from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("permission", "0012_operation_log"),
    ]

    operations = [
        migrations.CreateModel(
            name="SystemConfig",
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
                    "config_name",
                    models.CharField(max_length=64, verbose_name="Config name"),
                ),
                (
                    "config_key",
                    models.CharField(
                        db_index=True,
                        max_length=128,
                        unique=True,
                        verbose_name="Config key",
                    ),
                ),
                (
                    "config_value",
                    models.TextField(
                        blank=True, default="", verbose_name="Config value"
                    ),
                ),
                (
                    "config_group",
                    models.CharField(
                        choices=[
                            ("basic", "Basic"),
                            ("security", "Security"),
                            ("log", "Log"),
                            ("file", "File"),
                        ],
                        default="basic",
                        max_length=32,
                        verbose_name="Config group",
                    ),
                ),
                (
                    "remark",
                    models.TextField(blank=True, default="", verbose_name="Remark"),
                ),
                (
                    "is_system",
                    models.BooleanField(default=False, verbose_name="Built-in config"),
                ),
            ],
            options={
                "verbose_name": "System config",
                "verbose_name_plural": "System config",
                "db_table": "system_config",
            },
        ),
    ]

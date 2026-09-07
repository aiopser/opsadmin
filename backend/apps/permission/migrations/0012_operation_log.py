from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("permission", "0011_dict_models"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OperationLog",
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
                    "module",
                    models.CharField(
                        blank=True, default="", max_length=64, verbose_name="Module"
                    ),
                ),
                (
                    "action_type",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=64,
                        verbose_name="Action type",
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        blank=True, default="", max_length=255, verbose_name="Title"
                    ),
                ),
                (
                    "content",
                    models.TextField(blank=True, default="", verbose_name="Content"),
                ),
                (
                    "operator_name",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=150,
                        verbose_name="Operator name",
                    ),
                ),
                (
                    "request_uri",
                    models.CharField(
                        db_index=True, max_length=255, verbose_name="Request URI"
                    ),
                ),
                (
                    "request_method",
                    models.CharField(max_length=16, verbose_name="Request method"),
                ),
                (
                    "ip",
                    models.CharField(
                        blank=True, default="", max_length=64, verbose_name="IP"
                    ),
                ),
                (
                    "region",
                    models.CharField(
                        blank=True, default="", max_length=128, verbose_name="Region"
                    ),
                ),
                (
                    "device",
                    models.CharField(
                        blank=True, default="", max_length=128, verbose_name="Device"
                    ),
                ),
                (
                    "browser",
                    models.CharField(
                        blank=True, default="", max_length=128, verbose_name="Browser"
                    ),
                ),
                (
                    "os",
                    models.CharField(
                        blank=True, default="", max_length=128, verbose_name="OS"
                    ),
                ),
                (
                    "status",
                    models.IntegerField(
                        db_index=True, default=1, verbose_name="Status"
                    ),
                ),
                (
                    "execution_time",
                    models.IntegerField(default=0, verbose_name="Execution time"),
                ),
                (
                    "error_msg",
                    models.TextField(
                        blank=True, default="", verbose_name="Error message"
                    ),
                ),
                (
                    "operator",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Operator",
                    ),
                ),
            ],
            options={
                "verbose_name": "Operation log",
                "verbose_name_plural": "Operation log",
                "db_table": "system_operation_log",
            },
        ),
    ]

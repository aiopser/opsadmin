from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("permission", "0010_auto_20260616_1352"),
    ]

    operations = [
        migrations.CreateModel(
            name="DictType",
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
                    "name",
                    models.CharField(max_length=64, verbose_name="Dictionary name"),
                ),
                (
                    "dict_code",
                    models.CharField(
                        db_index=True,
                        max_length=64,
                        unique=True,
                        verbose_name="Dictionary code",
                    ),
                ),
                ("status", models.IntegerField(default=1, verbose_name="Status")),
                (
                    "remark",
                    models.TextField(blank=True, default="", verbose_name="Remark"),
                ),
            ],
            options={
                "verbose_name": "Dictionary type",
                "verbose_name_plural": "Dictionary type",
                "db_table": "system_dict_type",
            },
        ),
        migrations.CreateModel(
            name="DictItem",
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
                ("label", models.CharField(max_length=64, verbose_name="Label")),
                ("value", models.CharField(max_length=128, verbose_name="Value")),
                ("status", models.IntegerField(default=1, verbose_name="Status")),
                ("sort", models.IntegerField(default=1, verbose_name="Sort")),
                (
                    "tag_type",
                    models.CharField(
                        choices=[
                            ("N", "None"),
                            ("P", "Primary"),
                            ("S", "Success"),
                            ("W", "Warning"),
                            ("I", "Info"),
                            ("D", "Danger"),
                        ],
                        default="N",
                        max_length=1,
                        verbose_name="Tag type",
                    ),
                ),
                (
                    "dict_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="permission.dicttype",
                        verbose_name="Dictionary type",
                    ),
                ),
            ],
            options={
                "verbose_name": "Dictionary item",
                "verbose_name_plural": "Dictionary item",
                "db_table": "system_dict_item",
                "unique_together": {("dict_type", "value")},
            },
        ),
    ]

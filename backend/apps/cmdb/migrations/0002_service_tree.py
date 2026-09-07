# Generated manually for the additive CMDB service-tree foundation.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("cmdb", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Business",
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
                ("code", models.CharField(db_index=True, max_length=64, unique=True)),
                ("name", models.CharField(max_length=128)),
                ("description", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "db_table": "cmdb_business",
                "ordering": ["code"],
            },
        ),
        migrations.CreateModel(
            name="ServiceTreeNode",
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
                    "code",
                    models.CharField(max_length=64),
                ),
                ("name", models.CharField(max_length=128)),
                (
                    "node_type",
                    models.CharField(
                        choices=[
                            ("environment", "Environment"),
                            ("region", "Region"),
                            ("module", "Module"),
                        ],
                        max_length=32,
                    ),
                ),
                ("description", models.TextField(blank=True, default="")),
                ("sort_order", models.IntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="service_tree_nodes",
                        to="cmdb.business",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="cmdb.servicetreenode",
                    ),
                ),
            ],
            options={
                "db_table": "cmdb_service_tree_node",
                "ordering": ["sort_order", "name", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="servicetreenode",
            constraint=models.UniqueConstraint(
                fields=("business", "code"),
                name="cmdb_service_tree_business_code_uniq",
            ),
        ),
        migrations.AddField(
            model_name="assethost",
            name="service_node",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="hosts",
                to="cmdb.servicetreenode",
            ),
        ),
    ]

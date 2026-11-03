import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cmdb", "0010_private_cloud_providers"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CloudImportPreview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("source_updated_at", models.DateTimeField()),
                ("assets", models.JSONField(default=list)),
                ("digest", models.CharField(max_length=64)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("status", models.CharField(default="pending", max_length=16)),
                ("error_message", models.CharField(blank=True, default="", max_length=255)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ("source", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cloud_previews", to="cmdb.assetsource")),
            ],
            options={"db_table": "cmdb_cloud_import_preview"},
        ),
    ]

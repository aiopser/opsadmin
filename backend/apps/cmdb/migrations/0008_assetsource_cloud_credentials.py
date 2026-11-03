from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cmdb", "0007_assetsyncrecord_partial")]

    operations = [
        migrations.AddField(
            model_name="assetsource",
            name="cloud_provider",
            field=models.CharField(
                blank=True,
                default="",
                max_length=16,
                choices=[("aliyun", "Alibaba Cloud"), ("tencent", "Tencent Cloud")],
            ),
        ),
        migrations.AddField(
            model_name="assetsource",
            name="regions",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="assetsource",
            name="credentials_encrypted",
            field=models.TextField(blank=True, default=""),
        ),
    ]

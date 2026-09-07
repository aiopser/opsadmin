from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cmdb", "0005_sync_and_asset_type")]

    operations = [
        migrations.AddField(
            model_name="credentialref",
            name="connection_type",
            field=models.CharField(
                choices=[("ssh", "SSH"), ("winrm", "WinRM"), ("local", "Local")],
                default="ssh",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="credentialref",
            name="username",
            field=models.CharField(blank=True, default="root", max_length=64),
        ),
        migrations.AddField(
            model_name="credentialref",
            name="default_port",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="credentialref",
            name="secret_ref",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="credentialref",
            name="encrypted_secret",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="assethost",
            name="last_discovered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

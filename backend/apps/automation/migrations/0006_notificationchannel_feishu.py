from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("automation", "0005_gitrepository")]

    operations = [
        migrations.AlterField(
            model_name="notificationchannel",
            name="channel_type",
            field=models.CharField(
                max_length=16,
                choices=[
                    ("webhook", "Webhook"),
                    ("wecom", "WeCom"),
                    ("dingtalk", "DingTalk"),
                    ("feishu", "Feishu"),
                    ("email", "Email"),
                ],
            ),
        ),
    ]

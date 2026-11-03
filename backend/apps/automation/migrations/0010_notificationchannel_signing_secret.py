from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("automation", "0009_notificationrecord_context_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationchannel",
            name="signing_secret_encrypted",
            field=models.TextField(blank=True, default=""),
        ),
    ]

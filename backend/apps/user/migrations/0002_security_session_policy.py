from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("user", "0001_initial")]
    operations = [
        migrations.AddField(
            "userprofile",
            "auth_version",
            models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            "userprofile", "must_change_password", models.BooleanField(default=False)
        ),
        migrations.AddField(
            "userprofile",
            "login_failure_count",
            models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            "userprofile",
            "login_locked_until",
            models.DateTimeField(null=True, blank=True, editable=False),
        ),
    ]

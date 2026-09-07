from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("user", "0003_auto_20260616_1352"),
    ]

    operations = [
        migrations.AddField(
            model_name="department",
            name="code",
            field=models.CharField(
                blank=True, default="", max_length=64, verbose_name="Department code"
            ),
        ),
        migrations.AddField(
            model_name="department",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="children",
                to="user.department",
                verbose_name="Parent department",
            ),
        ),
        migrations.AddField(
            model_name="department",
            name="sort",
            field=models.IntegerField(default=1, verbose_name="Sort"),
        ),
        migrations.AddField(
            model_name="department",
            name="status",
            field=models.IntegerField(default=1, verbose_name="Status"),
        ),
    ]

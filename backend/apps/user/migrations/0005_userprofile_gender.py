from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0004_department_tree_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="gender",
            field=models.IntegerField(default=1, verbose_name="Gender"),
        ),
    ]

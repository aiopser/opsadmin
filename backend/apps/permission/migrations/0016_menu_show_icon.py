from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("permission", "0015_menu_menu_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="menu",
            name="show_icon",
            field=models.BooleanField(default=False, verbose_name="Show icon"),
        ),
    ]

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("automation", "0004_commandversion_remark"),
    ]

    operations = [
        migrations.CreateModel(
            name="GitRepository",
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
                ("name", models.CharField(max_length=128)),
                ("repo_url", models.URLField(max_length=2048)),
                ("username", models.CharField(blank=True, default="", max_length=128)),
                (
                    "branch",
                    models.CharField(blank=True, default="main", max_length=128),
                ),
                ("token_encrypted", models.TextField(blank=True, default="")),
                ("verify_ssl", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "db_table": "automation_git_repository",
                "ordering": ["name", "id"],
            },
        ),
        migrations.AddField(
            model_name="gitrepository",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_git_repositories",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="gitrepository",
            name="updated_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="updated_git_repositories",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]

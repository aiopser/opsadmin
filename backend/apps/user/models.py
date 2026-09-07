from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.permission.models import Role
from common.models import StandardModelMixin

__all__ = ["Department", "UserProfile"]


class Department(StandardModelMixin, models.Model):
    name = models.CharField(max_length=32, verbose_name="Department name")
    code = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name="Department code",
    )
    parent = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        related_name="children",
        on_delete=models.CASCADE,
        verbose_name="Parent department",
    )
    sort = models.IntegerField(default=1, verbose_name="Sort")
    status = models.IntegerField(default=1, verbose_name="Status")

    def __str__(self):
        return self.name

    class Meta:
        db_table = "user_department"
        verbose_name = "Department"
        verbose_name_plural = "Departments"


class UserProfile(AbstractUser):
    name = models.CharField(max_length=20, default="", verbose_name="Display name")
    icon = models.ImageField(
        upload_to="icon/user/%Y/%m/%d/",
        default="icon/user/2022/04/17/devops.png",
        blank=True,
        null=True,
    )
    email = models.EmailField(verbose_name="Email", max_length=255)
    position = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Position",
    )
    gender = models.IntegerField(default=1, verbose_name="Gender")
    department = models.ForeignKey(
        verbose_name="Department",
        to=Department,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="user",
    )
    staff_id = models.IntegerField(null=True, blank=True, verbose_name="Staff ID")
    job_status = models.BooleanField(default=True, verbose_name="Active employee")
    phone = models.CharField(verbose_name="Phone", max_length=32)
    remarks = models.TextField(
        verbose_name="Remarks", blank=True, null=True, default=None
    )
    role = models.ManyToManyField(
        to=Role,
        related_name="user",
        verbose_name="Role",
        blank=True,
    )

    class Meta:
        db_table = "user_userprofile"
        verbose_name = "User profile"
        verbose_name_plural = verbose_name
        ordering = ["id"]

    def __str__(self):
        return self.username

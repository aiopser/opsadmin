from django.contrib.auth.models import AbstractUser
from django.contrib.auth.hashers import (
    check_password as check_encoded_password,
    make_password,
)
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
    auth_version = models.PositiveIntegerField(default=0, editable=False)
    must_change_password = models.BooleanField(default=False)
    login_failure_count = models.PositiveIntegerField(default=0, editable=False)
    login_locked_until = models.DateTimeField(null=True, blank=True, editable=False)
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

    def set_password(self, raw_password):
        super().set_password(raw_password)
        if self.pk:
            self.auth_version = models.F("auth_version") + 1
            self.must_change_password = False
            self._credentials_changed = True

    def check_password(self, raw_password):
        original = self.password
        upgraded = None

        def upgrade(raw):
            nonlocal upgraded
            encoded = make_password(raw)
            if self.pk is None:
                self.password = encoded
                upgraded = True
                return
            upgraded = bool(
                type(self)
                .objects.filter(pk=self.pk, password=original)
                .update(password=encoded)
            )
            if upgraded:
                self.password = encoded
            # Hash maintenance is not a human password change: retain the
            # initial-password gate and authentication generation.

        valid = check_encoded_password(raw_password, original, setter=upgrade)
        return valid and upgraded is not False

    def save(self, *args, **kwargs):
        changed = getattr(self, "_credentials_changed", False)
        if self.pk and not self._state.adding and kwargs.get("update_fields") is None:
            protected = {
                "password",
                "auth_version",
                "must_change_password",
                "login_failure_count",
                "login_locked_until",
            }
            deferred = self.get_deferred_fields()
            kwargs["update_fields"] = {
                field.name
                for field in self._meta.concrete_fields
                if not field.primary_key
                and field.name not in protected
                and field.attname not in deferred
            }
        if changed and kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                "password",
                "auth_version",
                "must_change_password",
            }
        result = super().save(*args, **kwargs)
        if changed:
            self.refresh_from_db(fields=["auth_version"])
            self._credentials_changed = False
        return result

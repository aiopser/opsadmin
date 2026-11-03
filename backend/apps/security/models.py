from django.conf import settings
from django.db import models
from common.models import StandardModelMixin


class SecuritySubscription(StandardModelMixin):
    name = models.CharField(max_length=128)
    enabled = models.BooleanField(default=False)
    interval_minutes = models.PositiveIntegerField(default=60)
    keywords = models.JSONField(default=list, blank=True)
    severities = models.JSONField(default=list, blank=True)
    notification = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    initialized_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)


class SecurityAdvisory(StandardModelMixin):
    stable_id = models.CharField(max_length=80, unique=True)
    title = models.CharField(max_length=512)
    url = models.URLField()
    category = models.CharField(max_length=256, blank=True)
    published = models.CharField(max_length=40)
    severity = models.CharField(max_length=32)
    fingerprint = models.CharField(max_length=64)
    source_status = models.CharField(max_length=256, blank=True)


class SecurityCollection(StandardModelMixin):
    subscription = models.ForeignKey(SecuritySubscription, on_delete=models.CASCADE)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    trigger = models.CharField(max_length=16, default="manual")
    status = models.CharField(max_length=16, default="queued")
    count = models.PositiveIntegerField(default=0)
    notifications = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=256, blank=True)
    finished_at = models.DateTimeField(null=True)


class SecurityFetch(StandardModelMixin):
    """一次官方源共享抓取：周期采集合并执行，各订阅基于落库结果自行匹配。"""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    trigger = models.CharField(max_length=16, default="scheduled")
    status = models.CharField(max_length=16, default="queued")
    count = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=256, blank=True)
    finished_at = models.DateTimeField(null=True)


class SecurityObservation(models.Model):
    subscription = models.ForeignKey(SecuritySubscription, on_delete=models.CASCADE)
    advisory = models.ForeignKey(SecurityAdvisory, on_delete=models.CASCADE)
    fingerprint = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["subscription", "advisory"], name="security_observation_unique"
            )
        ]

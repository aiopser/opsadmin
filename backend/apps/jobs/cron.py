from datetime import timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone as django_timezone


class CronExpressionError(ValueError):
    pass


def _expand_field(value, minimum, maximum, *, sunday=False):
    values = set()
    for token in value.split(","):
        token = token.strip()
        if not token:
            raise CronExpressionError("Cron 字段不能为空")
        base, separator, step_text = token.partition("/")
        try:
            step = int(step_text) if separator else 1
        except ValueError as exc:
            raise CronExpressionError("Cron 步长必须是整数") from exc
        if step < 1:
            raise CronExpressionError("Cron 步长必须大于 0")
        try:
            if base == "*":
                start, end = minimum, maximum
            elif "-" in base:
                start_text, end_text = base.split("-", 1)
                start, end = int(start_text), int(end_text)
            else:
                start = int(base)
                end = maximum if separator else start
        except ValueError as exc:
            raise CronExpressionError("Cron 字段必须是数字、范围或通配符") from exc
        upper = 7 if sunday else maximum
        if (
            start < minimum
            or start > upper
            or end < minimum
            or end > upper
            or start > end
        ):
            raise CronExpressionError(f"Cron 字段超出范围 {minimum}-{maximum}")
        values.update(value % 7 if sunday else value for value in range(start, end + 1, step))
    return values


def parse_cron(expression):
    fields = str(expression or "").split()
    if len(fields) != 5:
        raise CronExpressionError("Cron 表达式必须包含 5 个字段：分 时 日 月 周")
    minute, hour, day, month, weekday = fields
    return {
        "minute": _expand_field(minute, 0, 59),
        "hour": _expand_field(hour, 0, 23),
        "day": _expand_field(day, 1, 31),
        "month": _expand_field(month, 1, 12),
        "weekday": _expand_field(weekday, 0, 6, sunday=True),
        "day_any": day == "*",
        "weekday_any": weekday == "*",
    }


def validate_timezone(timezone_name):
    try:
        return ZoneInfo(str(timezone_name))
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise CronExpressionError("无效的时区名称") from exc


def next_cron_time(expression, timezone_name, after=None):
    cron = parse_cron(expression)
    zone = validate_timezone(timezone_name)
    current = after or django_timezone.now()
    if django_timezone.is_naive(current):
        current = current.replace(tzinfo=ZoneInfo(settings.TIME_ZONE))
    current = current.astimezone(zone)
    candidate = current.replace(second=0, microsecond=0) + timedelta(minutes=1)
    # Five years of minute slots provides a deterministic upper bound for invalid/impossible dates.
    for _ in range(60 * 24 * 366 * 5):
        if _minute_matches(candidate, cron):
            result = candidate.astimezone(timezone.utc)
            if not settings.USE_TZ:
                return result.astimezone(ZoneInfo(settings.TIME_ZONE)).replace(
                    tzinfo=None
                )
            return result
        candidate += timedelta(minutes=1)
    raise CronExpressionError("未来五年内没有符合该 Cron 表达式的执行时间")


def prev_cron_time(expression, timezone_name, before=None):
    """Most recent cron slot at or before ``before``'s minute.

    Used to identify the occurrence a beat trigger belongs to: when the
    scheduler fires shortly after a slot, the slot itself is the intended
    occurrence; after a backlog it is the last matching slot before now.
    """
    cron = parse_cron(expression)
    zone = validate_timezone(timezone_name)
    current = before or django_timezone.now()
    if django_timezone.is_naive(current):
        current = current.replace(tzinfo=ZoneInfo(settings.TIME_ZONE))
    current = current.astimezone(zone)
    candidate = current.replace(second=0, microsecond=0)
    for _ in range(60 * 24 * 366 * 5):
        if _minute_matches(candidate, cron):
            result = candidate.astimezone(timezone.utc)
            if not settings.USE_TZ:
                return result.astimezone(ZoneInfo(settings.TIME_ZONE)).replace(
                    tzinfo=None
                )
            return result
        candidate -= timedelta(minutes=1)
    raise CronExpressionError("过去五年内没有符合该 Cron 表达式的执行时间")


def _minute_matches(candidate, cron):
    cron_weekday = (candidate.weekday() + 1) % 7
    day_matches = candidate.day in cron["day"]
    weekday_matches = cron_weekday in cron["weekday"]
    # Match Celery's crontab: all five fields must match simultaneously.
    calendar_matches = day_matches and weekday_matches
    return (
        candidate.month in cron["month"]
        and candidate.hour in cron["hour"]
        and candidate.minute in cron["minute"]
        and calendar_matches
    )


def utc_instant(value):
    """Interpret database-naive timestamps in the configured Django timezone."""
    if django_timezone.is_naive(value):
        value = value.replace(tzinfo=ZoneInfo(settings.TIME_ZONE))
    return value.astimezone(timezone.utc)


def database_instant(value):
    aware = utc_instant(value)
    return aware if settings.USE_TZ else aware.astimezone(ZoneInfo(settings.TIME_ZONE)).replace(tzinfo=None)


def celery_instant(value):
    """Interpret a naive timestamp in django-celery-beat's UTC convention.

    Beat stores cursors (``last_run_at``) and clocked/expires moments as naive
    UTC when ``DJANGO_CELERY_BEAT_TZ_AWARE`` is off, which is the opposite of
    the application's naive local convention.  Use this instead of
    ``utc_instant`` for any value read back from ``django_celery_beat``.
    """
    if django_timezone.is_naive(value):
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def celery_datetime(value):
    """Convert an application-local datetime into beat's naive-UTC column value."""
    if value is None:
        return None
    aware = utc_instant(value)
    return aware if settings.USE_TZ else aware.replace(tzinfo=None)

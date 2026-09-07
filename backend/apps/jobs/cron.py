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
        step = int(step_text) if separator else 1
        if step < 1:
            raise CronExpressionError("Cron 步长必须大于 0")
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            start_text, end_text = base.split("-", 1)
            start, end = int(start_text), int(end_text)
        else:
            start = end = int(base)
        if sunday:
            start = 0 if start == 7 else start
            end = 0 if end == 7 else end
        if (
            start < minimum
            or start > maximum
            or end < minimum
            or end > maximum
            or start > end
        ):
            raise CronExpressionError(f"Cron 字段超出范围 {minimum}-{maximum}")
        values.update(range(start, end + 1, step))
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
    except ZoneInfoNotFoundError as exc:
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
        cron_weekday = (candidate.weekday() + 1) % 7
        day_matches = candidate.day in cron["day"]
        weekday_matches = cron_weekday in cron["weekday"]
        if cron["day_any"] or cron["weekday_any"]:
            calendar_matches = day_matches and weekday_matches
        else:
            calendar_matches = day_matches or weekday_matches
        if (
            candidate.month in cron["month"]
            and candidate.hour in cron["hour"]
            and candidate.minute in cron["minute"]
            and calendar_matches
        ):
            result = candidate.astimezone(timezone.utc)
            if not settings.USE_TZ:
                return result.astimezone(ZoneInfo(settings.TIME_ZONE)).replace(
                    tzinfo=None
                )
            return result
        candidate += timedelta(minutes=1)
    raise CronExpressionError("未来五年内没有符合该 Cron 表达式的执行时间")

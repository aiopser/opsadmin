"""prev_cron_time / next_cron_time contract tests."""

from datetime import timedelta

from django.utils import timezone

from apps.jobs.cron import next_cron_time, parse_cron, prev_cron_time


def test_prev_includes_the_current_minute_slot():
    anchor = timezone.now().replace(minute=17, second=30, microsecond=0)

    slot = prev_cron_time("* * * * *", "UTC", anchor)

    assert slot.minute == 17


def test_prev_matches_last_slot_when_beat_fires_late():
    anchor = timezone.now().replace(hour=10, minute=7, second=0, microsecond=0)

    slot = prev_cron_time("0 * * * *", "UTC", anchor)

    assert (slot.hour, slot.minute) == (10, 0)


def test_prev_and_next_roundtrip_on_slot_boundaries():
    expression = "*/15 9-18 * * 1-5"
    anchor = timezone.now() - timedelta(days=3)
    for _ in range(50):
        nxt = next_cron_time(expression, "UTC", anchor)
        assert prev_cron_time(expression, "UTC", nxt) == nxt
        after_next = next_cron_time(expression, "UTC", nxt)
        # prev includes the slot minute itself, so step back one second.
        assert prev_cron_time(expression, "UTC", after_next - timedelta(seconds=1)) == nxt
        anchor = nxt


def test_prev_respects_day_of_month_and_weekday_and_semantics():
    anchor = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)

    slot = prev_cron_time("0 0 1 * 1", "UTC", anchor)

    # Keep the calendar identical to Celery's crontab scheduler.
    assert slot.day == 1 and slot.weekday() == 0


def test_prev_rejects_invalid_expression():
    import pytest

    from apps.jobs.cron import CronExpressionError

    with pytest.raises(CronExpressionError):
        prev_cron_time("not a cron", "UTC")


def test_parse_cron_expands_steps_and_ranges():
    cron = parse_cron("*/10 0-2 1,15 3 1-5")
    assert cron["minute"] == set(range(0, 60, 10))
    assert cron["hour"] == {0, 1, 2}
    assert cron["day"] == {1, 15}
    assert cron["month"] == {3}
    assert cron["weekday"] == {1, 2, 3, 4, 5}

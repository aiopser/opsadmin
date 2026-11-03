from celery import shared_task

from .notification_history import purge_notification_history


@shared_task(name="automation.purge_notification_history")
def purge_notification_history_task() -> dict:
    return purge_notification_history()

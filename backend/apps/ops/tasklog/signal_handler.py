import logging

from celery.signals import after_setup_logger

from .logger import AnsibleTaskOutputFilter, CeleryThreadTaskFileHandler


@after_setup_logger.connect
def add_ansible_task_log_handler(
    sender=None, logger=None, loglevel=None, format=None, **kwargs
):
    if not logger:
        return
    handler = CeleryThreadTaskFileHandler()
    handler.setLevel(loglevel or logging.INFO)
    handler.addFilter(AnsibleTaskOutputFilter())
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

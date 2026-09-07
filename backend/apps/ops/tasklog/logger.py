from logging import Filter, StreamHandler
from threading import get_ident

from celery import current_task
from celery.signals import task_postrun, task_prerun

from .constants import CELERY_LOG_MAGIC_MARK
from .utils import get_task_log_path


class AnsibleTaskOutputFilter(Filter):
    """Keep Ansible console output out of Celery's operational log noise."""

    def filter(self, record):
        return record.name == "celery.redirected"


class CeleryThreadTaskFileHandler(StreamHandler):
    """JumpServer's thread-aware file logger for live task output."""

    terminator = "\r\n"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thread_id_fd_mapper = {}
        self.task_id_thread_id_mapper = {}
        task_prerun.connect(self.on_task_start)
        task_postrun.connect(self.on_task_end)

    @staticmethod
    def get_current_thread_id():
        return str(get_ident())

    def on_task_start(self, sender, task_id, **kwargs):
        thread_id = self.get_current_thread_id()
        self.task_id_thread_id_mapper[task_id] = thread_id
        self.thread_id_fd_mapper[thread_id] = open(get_task_log_path(task_id), "ab")

    def on_task_end(self, sender, task_id, **kwargs):
        thread_id = self.task_id_thread_id_mapper.pop(task_id, "")
        file_obj = self.thread_id_fd_mapper.pop(thread_id, None)
        if file_obj and not file_obj.closed:
            file_obj.write(CELERY_LOG_MAGIC_MARK)
            file_obj.close()

    def emit(self, record):
        file_obj = self.thread_id_fd_mapper.get(self.get_current_thread_id())
        if not file_obj:
            return
        file_obj.write(self.format(record).encode())
        file_obj.write(self.terminator.encode())
        file_obj.flush()

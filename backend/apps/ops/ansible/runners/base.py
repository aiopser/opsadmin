import os
import sys
import locale

from django.conf import settings

from apps.ops.ansible.cleaner import WorkPostRunCleaner


class BaseRunner(WorkPostRunCleaner):
    def __init__(self, **kwargs):
        self.runner_params = kwargs
        self.clean_workspace = kwargs.pop("clean_workspace", True)
        self.setup_env()

    @staticmethod
    def setup_env():
        ansible_config_path = os.path.join(settings.BASE_DIR, "config", "ansible.cfg")
        ansible_modules_path = os.path.join(
            settings.BASE_DIR, "apps", "ops", "ansible", "modules"
        )
        os.environ.setdefault("PYTHONPATH", str(settings.BASE_DIR))
        os.environ.setdefault("ANSIBLE_FORCE_COLOR", "True")
        # 临时排查日志：确认 ansible.cfg 是否被 worker 加载，定位连接优化配置不生效问题。
        if os.path.exists(ansible_config_path):
            os.environ.setdefault("ANSIBLE_CONFIG", ansible_config_path)
            print(
                f"[ansible-debug] ansible.cfg 已加载: path={ansible_config_path}, "
                f"ANSIBLE_CONFIG={os.environ.get('ANSIBLE_CONFIG')}",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(
                "[ansible-debug] ansible.cfg 不存在，Ansible 将使用默认配置: "
                f"{ansible_config_path}",
                file=sys.stderr,
                flush=True,
            )
        if os.path.isdir(ansible_modules_path):
            os.environ.setdefault("ANSIBLE_LIBRARY", ansible_modules_path)
        # CentOS 7 images do not always have C.UTF-8 or en_US.UTF-8
        # generated.  Do not inherit an invalid locale into bwrap/Ansible:
        # Ansible aborts before connecting to any target in that case.
        for candidate in ("C.UTF-8", "en_US.UTF-8", "C"):
            try:
                locale.setlocale(locale.LC_ALL, candidate)
            except locale.Error:
                continue
            os.environ["LC_ALL"] = candidate
            os.environ["LANG"] = candidate
            os.environ["LANGUAGE"] = candidate
            break

    @property
    def clean_dir(self):
        if not self.clean_workspace:
            return None
        return self.private_data_dir

    @property
    def private_data_dir(self):
        return self.runner_params.get("private_data_dir", None)

    def get_event_handler(self):
        _event_handler = self.runner_params.pop("event_handler", None)
        return _event_handler

    def get_status_handler(self):
        _status_handler = self.runner_params.pop("status_handler", None)

        if not _status_handler:
            return

        def _handler(data, **kwargs):
            if self.private_data_dir:
                data["private_data_dir"] = self.private_data_dir
            _status_handler(data, **kwargs)

        return _handler

    def get_cancel_callback(self):
        return self.runner_params.pop("cancel_callback", None)

    def run(self):
        raise NotImplementedError()

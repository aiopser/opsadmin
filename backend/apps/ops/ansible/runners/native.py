from apps.ops.ansible.cleaner import cleanup_post_run
from apps.ops.ansible.runners.base import BaseRunner

__all__ = ["AnsibleNativeRunner"]


class AnsibleNativeRunner(BaseRunner):
    @cleanup_post_run
    def run(self):
        # Keep ansible-runner optional for Django management commands that do
        # not execute Ansible jobs.
        import ansible_runner

        ansible_runner.run(
            event_handler=self.get_event_handler(),
            status_handler=self.get_status_handler(),
            cancel_callback=self.get_cancel_callback(),
            **self.runner_params,
        )

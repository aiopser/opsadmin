from socket import gethostbyname, gethostname

from django.utils.functional import LazyObject

from apps.ops.ansible import AnsibleNativeRunner
from apps.ops.ansible.docker import use_ansible_docker_isolation
from apps.ops.ansible.runners.base import BaseRunner

__all__ = ["interface"]


class _LazyRunnerInterface(LazyObject):
    def _setup(self):
        self._wrapped = self.make_interface()

    @staticmethod
    def make_interface():
        runner_type = AnsibleNativeRunner
        return RunnerInterface(runner_type=runner_type, gateway_proxy_host="127.0.0.1")


interface = _LazyRunnerInterface()


class RunnerInterface:
    def __init__(self, runner_type, gateway_proxy_host="127.0.0.1"):
        if not issubclass(runner_type, BaseRunner):
            raise TypeError(f"{runner_type} can not cast to {BaseRunner}")
        self._runner_type = runner_type
        self._gateway_proxy_host = gateway_proxy_host

    def get_gateway_proxy_host(self):
        if use_ansible_docker_isolation() and self._gateway_proxy_host == "127.0.0.1":
            return gethostbyname(gethostname())
        return self._gateway_proxy_host

    def get_runner_type(self):
        return self._runner_type

    def run(self, **kwargs):
        runner_type = self.get_runner_type()
        runner = runner_type(**kwargs)
        return runner.run()

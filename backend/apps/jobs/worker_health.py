"""Read-only Celery inspection command for deployment version comparison."""

from celery.worker.control import inspect_command
from common.runtime_health import release_id


@inspect_command(name="deployment_version")
def deployment_version(state):
    return {"version": release_id()}

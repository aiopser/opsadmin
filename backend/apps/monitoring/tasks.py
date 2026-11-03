from celery import shared_task
from .registration import run_sync, recover_stale_syncs


@shared_task(name="monitoring.sync_consul_target", soft_time_limit=60, time_limit=75)
def sync_consul_target(record_id):
    run_sync(record_id)


@shared_task(name="monitoring.recover_stale_syncs")
def recover_syncs():
    return recover_stale_syncs()


@shared_task(name="monitoring.dispatch_due_targets", soft_time_limit=55, time_limit=65)
def dispatch_automatic_targets():
    from .automatic import dispatch_due_targets

    return dispatch_due_targets()


@shared_task(name="monitoring.execute_enrollment", soft_time_limit=180, time_limit=210)
def execute_enrollment(run_id):
    from .enrollment import execute_policy_run

    execute_policy_run(run_id)


@shared_task(name="monitoring.dispatch_enrollment", soft_time_limit=55, time_limit=65)
def dispatch_enrollment():
    from .enrollment import dispatch_policies

    return dispatch_policies()

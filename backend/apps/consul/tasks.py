from celery import shared_task


@shared_task(name="consul.read_remote_file")
def read_remote_file(read_id):
    from .remote_files import execute_read

    execute_read(read_id)


@shared_task(name="consul.recover_remote_reads")
def recover_remote_reads():
    from .remote_files import recover_reads

    recover_reads()

from django.conf import settings


def get_ansible_log_verbosity(verbosity=0):
    if settings.DEBUG_ANSIBLE:
        return 10
    if verbosity is None and settings.DEBUG:
        return 1
    return verbosity

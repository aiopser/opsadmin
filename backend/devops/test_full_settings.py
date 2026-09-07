"""All business apps, using only isolated test resources."""

from .test_settings import *  # noqa: F403

ROOT_URLCONF = "devops.test_full_urls"

INSTALLED_APPS = [
    *INSTALLED_APPS,  # noqa: F405
    "apps.cmdb.apps.CMDBConfig",
    "apps.automation.apps.AutomationConfig",
    "apps.jobs.apps.JobsConfig",
    "apps.ops.apps.OpsConfig",
]

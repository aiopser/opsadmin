"""Test settings must boot without reading a deployment INI, even if it exists."""

from pathlib import Path
import subprocess
import sys
import unittest


class TestSettingsIsolationTests(unittest.TestCase):
    def test_import_never_reads_deployment_ini(self):
        script = """
import configparser
import importlib
from pathlib import Path

original = configparser.ConfigParser.read
def guarded(self, filenames, *args, **kwargs):
    paths = [filenames] if isinstance(filenames, (str, Path)) else filenames
    for path in paths:
        if Path(path).name in {"devops.ini", "devops.ini.temp"}:
            raise AssertionError("Test settings tried to read deployment INI")
    return original(self, filenames, *args, **kwargs)
configparser.ConfigParser.read = guarded
settings = importlib.import_module("devops.test_full_settings")
assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"
assert settings.CELERY_BROKER_URL == "memory://"
assert settings.EMAIL_BACKEND == "django.core.mail.backends.locmem.EmailBackend"
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

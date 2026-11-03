"""Exercise the format gate using disposable source trees and real Black."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CHECKER = Path(__file__).with_name("check_python_format.py")


class PythonFormatGateTests(unittest.TestCase):
    def check_source(self, source, accepted_source=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "apps" / "demo.py"
            target.parent.mkdir()
            target.write_bytes(source.encode("utf-8"))
            files = (
                {"apps/demo.py": hashlib.sha256(accepted_source.encode()).hexdigest()}
                if accepted_source is not None
                else {}
            )
            (root / "python-format-baseline.json").write_text(
                json.dumps({"version": 1, "files": files}), encoding="utf-8"
            )
            return subprocess.run(
                [sys.executable, str(CHECKER), "--root", str(root)],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_unchanged_legacy_format_is_accepted_by_content_hash(self):
        result = self.check_source("value=1\n", accepted_source="value=1\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_changing_a_legacy_file_requires_formatting(self):
        result = self.check_source("value=2\n", accepted_source="value=1\n")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_new_unformatted_file_is_rejected(self):
        result = self.check_source("value=1\n")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_formatted_change_is_accepted_without_rebaselining(self):
        result = self.check_source("value = 2\n", accepted_source="value=1\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_crlf_checkout_has_the_same_legacy_content_identity(self):
        result = self.check_source("value=1\r\n", accepted_source="value=1\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_utf8_bom_is_normalized_like_black_file_loading(self):
        result = self.check_source("\ufeffvalue=1\n", accepted_source="value=1\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_invalid_python_is_rejected_even_when_hash_matches(self):
        result = self.check_source("def broken(:\n", accepted_source="def broken(:\n")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

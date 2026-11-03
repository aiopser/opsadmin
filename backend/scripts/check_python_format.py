"""Gate new Python format violations while allowing unchanged reviewed legacy files."""

import argparse
import hashlib
import json
from pathlib import Path

import black


SOURCE_DIRS = ("apps", "common", "devops", "scripts")


def source_files(root: Path) -> list[Path]:
    return sorted(
        path
        for directory in SOURCE_DIRS
        for path in (root / directory).rglob("*.py")
        if not {"migrations", "tests", "__pycache__"}.intersection(
            path.relative_to(root).parts
        )
        and path.name != "tests.py"
        and not path.name.startswith("test_")
        and not path.name.endswith("_tests.py")
    )


def inspect_source(path: Path) -> tuple[str, str | None]:
    # Normalize checkout line endings before hashing, including Windows CRLF.
    source = path.read_text(encoding="utf-8-sig")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    try:
        formatted = black.format_file_contents(
            source, fast=False, mode=black.FileMode()
        )
    except black.NothingChanged:
        return digest, None
    except (black.InvalidInput, SyntaxError, AssertionError):
        return digest, "invalid Python"
    return digest, "not Black formatted" if formatted != source else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    baseline_path = root / "python-format-baseline.json"
    checks = [
        (path.relative_to(root).as_posix(), *inspect_source(path))
        for path in source_files(root)
    ]
    if not checks:
        parser.error("No production Python source files were found")
    invalid = [name for name, _, issue in checks if issue == "invalid Python"]
    if args.write_baseline:
        if invalid:
            print("Invalid Python cannot be baselined: " + ", ".join(invalid))
            return 1
        baseline = {
            "version": 1,
            "black_version": black.__version__,
            "files": {name: digest for name, digest, issue in checks if issue},
        }
        baseline_path.write_text(
            json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Recorded {len(baseline['files'])} legacy format exceptions")
        return 0
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("Missing or invalid python-format-baseline.json")
        return 1
    if baseline.get("version") != 1 or not isinstance(baseline.get("files"), dict):
        print("Unsupported Python format baseline schema")
        return 1
    if baseline.get("black_version", black.__version__) != black.__version__:
        print("Black version changed; review the formatter and baseline together")
        return 1
    failures = [
        (name, issue)
        for name, digest, issue in checks
        if issue
        and (issue == "invalid Python" or baseline["files"].get(name) != digest)
    ]
    for name, issue in failures:
        print(f"{name}: {issue}; format this file before continuing")
    legacy_count = sum(bool(issue) for _, _, issue in checks) - len(failures)
    print(
        f"Python format gate: {len(checks)} production files, "
        f"{legacy_count} unchanged legacy exceptions, {len(failures)} failures"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

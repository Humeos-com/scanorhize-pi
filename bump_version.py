#!/usr/bin/env python3

import re
import subprocess
import sys
from pathlib import Path


def _run(args):
    return subprocess.run(
        args,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def staged_python_changes_exist() -> bool:
    """Return True if there are staged .py changes excluding version.py and this script."""
    result = _run([
        "git",
        "diff",
        "--cached",
        "--name-only",
        "--diff-filter=AM",
        "--",
        "*.py",
    ])
    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    exclude = {"version.py", Path(__file__).name}
    return any(Path(f).name not in exclude for f in files)


def version_staged() -> bool:
    """Return True if version.py is staged (has changes in index)."""
    result = _run(["git", "diff", "--cached", "--name-only", "--", "version.py"])
    return any(line.strip() == "version.py" for line in result.stdout.splitlines())


def unstaged_python_changes_exist() -> bool:
    """Return True if there are unstaged .py changes (working tree) excluding version.py and this script."""
    result = _run([
        "git",
        "diff",
        "--name-only",
        "--diff-filter=AM",
        "--",
        "*.py",
    ])
    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    exclude = {"version.py", Path(__file__).name}
    return any(Path(f).name not in exclude for f in files)


def bump_patch_version(file_path: str = "version.py") -> None:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r'__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"', content)
    if not match:
        raise ValueError("Version not found in version.py!")

    major, minor, patch = map(int, match.groups())
    patch += 1
    new_version = f"{major}.{minor}.{patch}"

    new_content = re.sub(
        r'__version__\s*=\s*".*"', f'__version__ = "{new_version}"', content
    )
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    # Stage the change so the commit can include it
    _run(["git", "add", file_path])

    print(f"Bumped version to: {new_version}")


if __name__ == "__main__":
    # Avoid bumping repeatedly within a single commit attempt
    if version_staged():
        print("version.py already staged; skipping bump.")
        sys.exit(0)

    # Avoid stash conflicts: only bump when no unstaged python changes
    if unstaged_python_changes_exist():
        print("Unstaged Python changes detected; skipping version bump.")
        sys.exit(0)

    # Only bump if there are staged Python changes (excluding version.py and this script)
    if staged_python_changes_exist():
        bump_patch_version()
        # Exit 1 so pre-commit re-runs hooks once with updated index, without bumping again
        sys.exit(1)

    print("No staged Python changes to bump.")
    sys.exit(0)

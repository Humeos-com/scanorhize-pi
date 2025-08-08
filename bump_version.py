#!/usr/bin/env python3

import re

def bump_patch_version(file_path="version.py"):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r'__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"', content)
    if not match:
        raise ValueError("Version not found in version.py!")

    major, minor, patch = map(int, match.groups())
    patch += 1
    new_version = f'{major}.{minor}.{patch}'

    new_content = re.sub(r'__version__\s*=\s*".*"', f'__version__ = "{new_version}"', content)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"Bumped version to: {new_version}")

if __name__ == "__main__":
    bump_patch_version()


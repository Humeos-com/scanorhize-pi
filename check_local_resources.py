#!/usr/bin/env python3
"""
Script to check if all local resources are available for offline operation
"""

import os

# Define the local resources that should exist
LOCAL_RESOURCES = [
    "static/css/bootstrap.min.css",
    "static/js/bootstrap.bundle.min.js",
]


def check_resource(resource_path):
    """Check if a resource exists and has content"""
    if not os.path.exists(resource_path):
        return False, "File does not exist"

    file_size = os.path.getsize(resource_path)
    if file_size == 0:
        return False, "File is empty"

    return True, f"OK ({file_size} bytes)"


def main():
    """Check all local resources"""
    print("Checking local resources for offline operation...")

    all_good = True
    total_count = len(LOCAL_RESOURCES)
    good_count = 0

    for resource in LOCAL_RESOURCES:
        status, message = check_resource(resource)
        if status:
            print(f"✓ {resource}: {message}")
            good_count += 1
        else:
            print(f"✗ {resource}: {message}")
            all_good = False

    print(f"\nCheck complete: {good_count}/{total_count} resources available")

    if all_good:
        print("✓ All local resources are available!")
        print("Your application can work offline.")
    else:
        print("⚠ Some resources are missing or empty.")
        print("Run 'python download_assets.py' to download missing resources.")


if __name__ == "__main__":
    main()

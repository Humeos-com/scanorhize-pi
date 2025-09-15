#!/usr/bin/env python3
"""
Script to download external CDN resources locally for offline operation
"""

import os
import requests

# Define the external resources to download (Bootstrap 5)
EXTERNAL_RESOURCES = [
    {
        "url": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
        "local_path": "static/css/bootstrap.min.css",
    },
    {
        "url": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
        "local_path": "static/js/bootstrap.bundle.min.js",
    },
]


def download_resource(resource):
    """Download a single resource"""
    url = resource["url"]
    local_path = resource["local_path"]

    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    try:
        print(f"Downloading {url}...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        with open(local_path, "wb") as f:
            f.write(response.content)

        print(f"✓ Downloaded to {local_path}")
        return True

    except Exception as e:
        print(f"✗ Failed to download {url}: {e}")
        return False


def main():
    """Download all external resources"""
    print("Downloading external resources for offline operation...")

    success_count = 0
    total_count = len(EXTERNAL_RESOURCES)

    for resource in EXTERNAL_RESOURCES:
        if download_resource(resource):
            success_count += 1

    print(f"\nDownload complete: {success_count}/{total_count} resources downloaded")

    if success_count == total_count:
        print("✓ All resources downloaded successfully!")
        print("\nNext steps:")
        print("1. Run: python update_templates.py")
        print("2. Restart your Flask application")
    else:
        print("⚠ Some resources failed to download. Check your internet connection.")


if __name__ == "__main__":
    main()

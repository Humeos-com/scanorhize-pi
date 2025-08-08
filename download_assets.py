#!/usr/bin/env python3
"""
Script to download external CDN resources locally for offline operation
"""

import os
import requests
import urllib.parse
from pathlib import Path

# Define the external resources to download
EXTERNAL_RESOURCES = [
    {
        "url": "https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css",
        "local_path": "static/css/bootstrap.min.css",
        "integrity": "sha384-ggOyR0iXCbMQv3Xipma34MD+dH/1fQ784/j6cY/iJTQUOhcWr7x9JvoRxT2MZw1T"
    },
    {
        "url": "https://code.jquery.com/jquery-3.3.1.slim.min.js",
        "local_path": "static/js/jquery-3.3.1.slim.min.js",
        "integrity": "sha384-q8i/X+965DzO0rT7abK41JStQIAqVgRVzpbzo5smXKp4YfRvH+8abtTE1Pi6jizo"
    },
    {
        "url": "https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.14.7/umd/popper.min.js",
        "local_path": "static/js/popper.min.js",
        "integrity": "sha384-UO2eT0CpHqdSJQ6hJty5KVphtPhzWj9WO1clHTMGa3JDZwrnQq4sF86dIHNDz0W1"
    },
    {
        "url": "https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/js/bootstrap.min.js",
        "local_path": "static/js/bootstrap.min.js",
        "integrity": "sha384-JjSmVgyd0p3pXB1rRibZUAYoIIy6OrQ6VrjIEaFf/nJGzIxFDsf4x0xIM+B07jRM"
    }
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
        
        with open(local_path, 'wb') as f:
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

#!/usr/bin/env python3
"""
Utility functions shared across modules
"""

# import json
# import os
from logging import getLogger


def write_json_to_file(file_path: str, json_data: str) -> int:
    """Utility function to write JSON data to a file.

    Args:
        file_path: Path to the file to write
        json_data: JSON string to write

    Returns:
        0 on success, 1 on error
    """
    try:
        with open(file_path, "w", encoding="utf-8") as outfile:
            outfile.write(json_data)
        return 0
    except OSError as e:
        getLogger().error("write_json_to_file: OSError: %s", e)
        return 1

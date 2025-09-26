#!/usr/bin/env python3
"""
Utility functions shared across modules
"""

# import json
# import os
import html
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


def sanitize_output(output: str) -> str:
    """Sanitize output string to prevent XSS attacks.

    This function escapes HTML special characters to prevent injection
    of malicious scripts through the output parameter.

    Args:
        output: The output string to sanitize

    Returns:
        Sanitized string safe for HTML rendering
    """
    if output is None:
        return ""

    # Escape HTML special characters
    sanitized = html.escape(str(output), quote=True)

    # Additional security: limit length to prevent DoS
    max_length = 10000  # Reasonable limit for output messages
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "... [truncated]"
        getLogger().warning(
            "Output message truncated due to length: %d chars", len(output)
        )

    return sanitized

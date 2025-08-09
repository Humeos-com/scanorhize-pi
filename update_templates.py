#!/usr/bin/env python3
"""
Script to update HTML templates to use local resources instead of CDN
"""


import re
from pathlib import Path

# Define the replacements for external resources (Bootstrap 5)
RESOURCE_REPLACEMENTS = [
    {
        "pattern": r'<link rel="stylesheet" href="https?://[^\"]*bootstrap@5[^\"]*/dist/css/bootstrap\.min\.css"[^>]*>',
        "replacement": "<link rel=\"stylesheet\" href=\"{{ url_for('static', filename='css/bootstrap.min.css') }}\">",
    },
    {
        "pattern": r'<script src="https?://[^\"]*bootstrap@5[^\"]*/dist/js/bootstrap\.bundle\.min\.js"[^>]*></script>',
        "replacement": "<script src=\"{{ url_for('static', filename='js/bootstrap.bundle.min.js') }}\"></script>",
    },
    # Remove old Bootstrap 4/jQuery/Popper CDN references if present by replacing with nothing
    {
        "pattern": r'<script src="https://code\.jquery\.com/jquery-[^\"]+\.min\.js"[^>]*></script>',
        "replacement": "",
    },
    {
        "pattern": r'<script src="https://cdnjs\.cloudflare\.com/ajax/libs/popper\.js/[^\"]+/umd/popper\.min\.js"[^>]*></script>',
        "replacement": "",
    },
    {
        "pattern": r'<script src="https?://[^\"]*bootstrapcdn[^\"]*/bootstrap/[^\"]+/js/bootstrap\.min\.js"[^>]*></script>',
        "replacement": "",
    },
]


def update_template_file(file_path):
    """Update a single template file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Apply all replacements
        for replacement in RESOURCE_REPLACEMENTS:
            content = re.sub(
                replacement["pattern"], replacement["replacement"], content
            )

        # Only write if content changed
        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✓ Updated {file_path}")
            return True
        else:
            print(f"- No changes needed for {file_path}")
            return False

    except Exception as e:
        print(f"✗ Error updating {file_path}: {e}")
        return False


def main():
    """Update all HTML templates"""
    print("Updating HTML templates to use local resources...")

    # Find all HTML files in templates directory
    templates_dir = Path("templates")
    html_files = list(templates_dir.glob("*.html"))

    if not html_files:
        print("No HTML files found in templates directory")
        return

    updated_count = 0
    total_count = len(html_files)

    for html_file in html_files:
        if update_template_file(html_file):
            updated_count += 1

    print(f"\nUpdate complete: {updated_count}/{total_count} files updated")

    if updated_count > 0:
        print("✓ Templates updated successfully!")
        print("\nYour application will now work offline with local resources.")
    else:
        print("No templates needed updating.")


if __name__ == "__main__":
    main()

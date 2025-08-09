# Offline Resources Management

This document explains how to manage external resources locally for offline operation.

## Overview

The Scanorhize application uses Bootstrap 5 for styling and components. To ensure the application works when internet connection is broken, these resources have been downloaded and served locally. Bootstrap 5's bundle already includes Popper 2, and jQuery is not required.

## Files Created

- `download_assets.py` - Downloads external resources locally
- `update_templates.py` - Updates HTML templates to use local resources
- `check_local_resources.py` - Verifies local resources are available

## Local Resources

The following resources are now served locally:

- `static/css/bootstrap.min.css` - Bootstrap CSS framework (v5.x)
- `static/js/bootstrap.bundle.min.js` - Bootstrap JS bundle with Popper (v5.x)

## Usage

### Initial Setup

1. **Download external resources:**
   ```bash
   python download_assets.py
   ```

2. **Update templates to use local resources:**
   ```bash
   python update_templates.py
   ```

3. **Verify everything is working:**
   ```bash
   python check_local_resources.py
   ```

### Maintenance

- **Check resource status:**
  ```bash
  python check_local_resources.py
  ```

- **Re-download resources (if needed):**
  ```bash
  python download_assets.py
  ```

## Benefits

- **Offline operation:** Application works without internet connection
- **Faster loading:** Local resources load faster than CDN
- **Reliability:** No dependency on external CDN availability
- **Consistency:** Same version of resources always available

## Template Changes

The `templates/base.html` file has been updated to use local resources:

**Before (example using CDN):**
```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
```

**After (local):**
```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/bootstrap.min.css') }}">
<script src="{{ url_for('static', filename='js/bootstrap.bundle.min.js') }}"></script>
```

Note: jQuery and the separate Popper include are not needed with Bootstrap 5’s bundle.

## Troubleshooting

If you encounter issues:

1. **Check if resources exist:**
   ```bash
   python check_local_resources.py
   ```

2. **Re-download if missing:**
   ```bash
   python download_assets.py
   ```

3. **Restart Flask application** after making changes

## Notes

- Integrity attributes from CDN are not used for local files
- All resources are minified versions for optimal performance
- The application will work seamlessly in both online and offline modes

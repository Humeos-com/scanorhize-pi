# Offline Resources Management

This document explains how to manage external resources locally for offline operation.

## Overview

The Scanorhize application uses external CDN resources (Bootstrap, jQuery, Popper.js) that require internet connectivity. To ensure the application works when internet connection is broken, these resources have been downloaded locally.

## Files Created

- `download_assets.py` - Downloads external resources locally
- `update_templates.py` - Updates HTML templates to use local resources
- `check_local_resources.py` - Verifies local resources are available

## Local Resources

The following resources are now served locally:

- `static/css/bootstrap.min.css` - Bootstrap CSS framework
- `static/js/jquery-3.3.1.slim.min.js` - jQuery library
- `static/js/popper.min.js` - Popper.js for Bootstrap tooltips
- `static/js/bootstrap.min.js` - Bootstrap JavaScript

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

**Before:**
```html
<link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
<script src="https://code.jquery.com/jquery-3.3.1.slim.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.14.7/umd/popper.min.js"></script>
<script src="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/js/bootstrap.min.js"></script>
```

**After:**
```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/bootstrap.min.css') }}">
<script src="{{ url_for('static', filename='js/jquery-3.3.1.slim.min.js') }}"></script>
<script src="{{ url_for('static', filename='js/popper.min.js') }}"></script>
<script src="{{ url_for('static', filename='js/bootstrap.min.js') }}"></script>
```

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

- The integrity checks from CDN have been removed since we're serving local files
- All resources are minified versions for optimal performance
- The application will work seamlessly in both online and offline modes

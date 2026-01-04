# Device Image Upload Script

This script automatically processes device images from the `IncomingImages` directory and uploads them to the Register API.

## Features

- Scans `IncomingImages` directory for image files
- Extracts device ID from the start of the filename
- Verifies device exists via API before uploading
- Uploads images using the Register API
- Moves processed images to `ProcessedImages` directory
- Handles errors gracefully and provides detailed logging

## Requirements

- Python 3.6 or higher
- `requests` library: `pip install requests`

## Setup

1. Install the required library:
   ```bash
   pip install requests
   ```

2. Set environment variables:
   ```bash
   export REGISTER_API_URL="http://localhost:8000/api/v1"
   export REGISTER_API_KEY="your-api-key-here"
   ```

   Optional (defaults shown):
   ```bash
   export INCOMING_DIR="./ProcessedImages"
   export PROCESSED_DIR="./UploadedImages"
   ```

3. Create the directories:
   ```bash
   mkdir -p ProcessedImages UploadedImages
   ```

## Usage

### Basic Usage

```bash
python scripts/upload_device_images.py
```

Or make it executable and run directly:

```bash
chmod +x scripts/upload_device_images.py
./scripts/upload_device_images.py
```

### Filename Format

The script extracts the device ID from the start of the filename. Supported formats:

- `12345.jpg` → Device ID: 12345
- `12345-image.jpg` → Device ID: 12345
- `12345_2024-01-15.jpg` → Device ID: 12345
- `12345-2024-01-15_14-30-45.jpg` → Device ID: 12345

The script looks for numeric digits at the beginning of the filename (before the extension).

### Supported Image Formats

- `.jpg`, `.jpeg`
- `.png`
- `.gif`
- `.bmp`
- `.webp`
- `.tiff`, `.tif`

## Workflow

1. Place image files in the `IncomingImages` directory
2. Run the script
3. The script will:
   - Extract device ID from filename
   - Check if device exists via API
   - Upload image if device exists
   - Move file to `ProcessedImages` directory
4. Files that fail validation or upload are moved to `ProcessedImages` to avoid reprocessing

## Example

```bash
# Set your API credentials
export REGISTER_API_KEY="abc123xyz"

# Place images in IncomingImages
cp my_device_12345.jpg IncomingImages/

# Run the script
python scripts/upload_device_images.py

# Output:
# Device Image Upload Script
# ============================================================
# API URL: http://localhost:8000/api/v1
# Incoming directory: ./IncomingImages
# Processed directory: ./ProcessedImages
#
# Found 1 image file(s) to process
#
# Processing: my_device_12345.jpg
#   Extracted device ID: 12345
#   Successfully uploaded: /media/device_images/12345/my_device_12345.jpg
#   Moved to processed directory
#
# ============================================================
# Summary:
#   Processed successfully: 1
#   Skipped: 0
#   Errors: 0
# ============================================================
```

## Error Handling

- **No device ID found**: File is moved to `ProcessedImages` and skipped
- **Device doesn't exist**: File is moved to `ProcessedImages` and skipped
- **API authentication error**: File remains in `IncomingImages` for retry
- **Upload error**: File remains in `IncomingImages` for retry

## Automation

You can set up a cron job or scheduled task to run this script periodically:

```bash
# Run every 5 minutes
*/5 * * * * cd /path/to/register && /usr/bin/python3 scripts/upload_device_images.py >> /var/log/device_upload.log 2>&1
```

Or use a systemd timer, or any other task scheduler.

## Troubleshooting

### "REGISTER_API_KEY environment variable is required"
Set the API key: `export REGISTER_API_KEY="your-key"`

### "requests library is required"
Install it: `pip install requests`

### "API key does not have access to device"
The API key must belong to the client associated with the device's design. Contact your administrator.

### Files not being processed
- Check that files are in the `IncomingImages` directory
- Verify filenames start with a numeric device ID
- Check file extensions are supported image formats
- Ensure the script has read/write permissions


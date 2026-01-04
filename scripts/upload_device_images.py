#!/usr/bin/env python3
"""
Standalone script to process device images from ProcessedImages directory.

This script:
1. Scans the "ProcessedImages" directory for image files
2. Extracts device ID from the start of the filename
3. Checks if the device exists via the Register API
4. Uploads the image if the device exists
5. Moves the processed image to "UploadedImages" directory

Usage:
    python upload_device_images.py

Environment variables:
    REGISTER_API_URL: Base URL for the Register API (default: http://localhost:8000/api/v1)
    REGISTER_API_KEY: API key for authentication (required)
    PROCESSED_DIR: Directory to watch for images (default: ./ProcessedImages)
    UPLOADED_DIR: Directory to move uploaded images (default: ./UploadedImages)
"""

import os
import sys
import shutil
import re
from pathlib import Path
from typing import Optional, Tuple

try:
    import requests
except ImportError:
    print("Error: requests library is required. Install it with: pip install requests")
    sys.exit(1)


# Configuration
DEFAULT_API_URL = "http://localhost:8000/api/v1"
DEFAULT_PROCESSED_DIR = "./ProcessedImages"
DEFAULT_UPLOADED_DIR = "./UploadedImages"

# Image file extensions to process
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}


def get_config():
    """Get configuration from environment variables."""
    api_url = os.environ.get('REGISTER_API_URL', DEFAULT_API_URL).rstrip('/')
    api_key = os.environ.get('REGISTER_API_KEY')
    processed_dir = os.environ.get('PROCESSED_DIR', DEFAULT_PROCESSED_DIR)
    uploaded_dir = os.environ.get('UPLOADED_DIR', DEFAULT_UPLOADED_DIR)
    
    if not api_key:
        print("Error: REGISTER_API_KEY environment variable is required")
        print("Set it with: export REGISTER_API_KEY='your-api-key'")
        sys.exit(1)
    
    return {
        'api_url': api_url,
        'api_key': api_key,
        'processed_dir': Path(processed_dir),
        'uploaded_dir': Path(uploaded_dir),
    }


def extract_device_id(filename: str) -> Optional[int]:
    """
    Extract device ID from the start of the filename.
    
    The device ID should be at the start of the filename, before any
    separators like '-', '_', or '.'. Examples:
    - "12345.jpg" -> 12345
    - "12345-image.jpg" -> 12345
    - "12345_2024-01-15.jpg" -> 12345
    - "12345-2024-01-15_14-30-45.jpg" -> 12345
    
    Returns the device ID as an integer, or None if not found.
    """
    # Remove extension
    name_without_ext = Path(filename).stem
    
    # Try to extract numeric ID from the start
    # Match digits at the beginning, optionally followed by separator
    match = re.match(r'^(\d+)', name_without_ext)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    
    return None


def check_device_exists(api_url: str, api_key: str, device_id: int) -> bool:
    """
    Check if a device exists in the Register API.
    
    Returns True if the device exists, False otherwise.
    """
    url = f"{api_url}/device/{device_id}/"
    headers = {"X-API-Key": api_key}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        elif response.status_code == 403:
            print(f"  Warning: API key does not have access to device {device_id}")
            return False
        else:
            print(f"  Warning: Unexpected response {response.status_code} when checking device {device_id}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"  Error checking device {device_id}: {e}")
        return False


def upload_device_image(api_url: str, api_key: str, device_id: int, image_path: Path) -> bool:
    """
    Upload an image to the Register API for a specific device.
    
    Returns True if upload was successful, False otherwise.
    """
    url = f"{api_url}/device/{device_id}/add-device-image/"
    headers = {"X-API-Key": api_key}
    
    try:
        with open(image_path, 'rb') as f:
            files = {'file': (image_path.name, f, 'image/jpeg')}
            response = requests.post(url, headers=headers, files=files, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"  Successfully uploaded: {result.get('image_url', 'N/A')}")
            return True
        elif response.status_code == 403:
            print(f"  Error: API key does not have access to device {device_id}")
            return False
        elif response.status_code == 404:
            print(f"  Error: Device {device_id} not found")
            return False
        else:
            error_msg = response.json().get('message', 'Unknown error') if response.content else 'Unknown error'
            print(f"  Error uploading image: {error_msg} (status {response.status_code})")
            return False
    except requests.exceptions.RequestException as e:
        print(f"  Error uploading image: {e}")
        return False
    except Exception as e:
        print(f"  Unexpected error: {e}")
        return False


def ensure_directory_exists(directory: Path):
    """Create directory if it doesn't exist."""
    directory.mkdir(parents=True, exist_ok=True)


def process_images(config: dict):
    """Main processing function."""
    processed_dir = config['processed_dir']
    uploaded_dir = config['uploaded_dir']
    api_url = config['api_url']
    api_key = config['api_key']
    
    # Ensure directories exist
    ensure_directory_exists(processed_dir)
    ensure_directory_exists(uploaded_dir)
    
    # Check if processed directory exists
    if not processed_dir.exists():
        print(f"Error: Processed directory does not exist: {processed_dir}")
        sys.exit(1)
    
    # Find all image files
    image_files = []
    for ext in IMAGE_EXTENSIONS:
        image_files.extend(processed_dir.glob(f"*{ext}"))
        image_files.extend(processed_dir.glob(f"*{ext.upper()}"))
    
    if not image_files:
        print(f"No image files found in {processed_dir}")
        return
    
    print(f"Found {len(image_files)} image file(s) to process")
    print()
    
    processed_count = 0
    skipped_count = 0
    error_count = 0
    
    for image_path in sorted(image_files):
        filename = image_path.name
        print(f"Processing: {filename}")
        
        # Extract device ID
        device_id = extract_device_id(filename)
        if device_id is None:
            print(f"  Skipping: Could not extract device ID from filename")
            skipped_count += 1
            # Move to uploaded anyway to avoid reprocessing
            try:
                dest_path = uploaded_dir / filename
                shutil.move(str(image_path), str(dest_path))
                print(f"  Moved to uploaded directory (no device ID found)")
            except Exception as e:
                print(f"  Error moving file: {e}")
            print()
            continue
        
        print(f"  Extracted device ID: {device_id}")
        
        # Check if device exists
        if not check_device_exists(api_url, api_key, device_id):
            print(f"  Skipping: Device {device_id} does not exist or is not accessible")
            skipped_count += 1
            # Move to uploaded anyway to avoid reprocessing
            try:
                dest_path = uploaded_dir / filename
                shutil.move(str(image_path), str(dest_path))
                print(f"  Moved to uploaded directory (device not found)")
            except Exception as e:
                print(f"  Error moving file: {e}")
            print()
            continue
        
        # Upload image
        if upload_device_image(api_url, api_key, device_id, image_path):
            # Move to uploaded directory
            try:
                dest_path = uploaded_dir / filename
                shutil.move(str(image_path), str(dest_path))
                print(f"  Moved to uploaded directory")
                processed_count += 1
            except Exception as e:
                print(f"  Error moving file: {e}")
                error_count += 1
        else:
            error_count += 1
            # Don't move file on error so it can be retried
            print(f"  File left in processed directory for retry")
        
        print()
    
    # Summary
    print("=" * 60)
    print(f"Summary:")
    print(f"  Processed successfully: {processed_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Errors: {error_count}")
    print("=" * 60)


def main():
    """Main entry point."""
    print("Device Image Upload Script")
    print("=" * 60)
    
    config = get_config()
    
    print(f"API URL: {config['api_url']}")
    print(f"Processed directory: {config['processed_dir']}")
    print(f"Uploaded directory: {config['uploaded_dir']}")
    print()
    
    process_images(config)


if __name__ == "__main__":
    main()


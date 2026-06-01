# find_barcodes.py

Processes incoming PCB images by detecting the board in the frame, reading its QR code or barcode, and renaming/moving the cropped result using the decoded serial number.

## What it does

1. Scans `IncomingImages/` for `.jpg` files.
2. Parses the timestamp embedded in each filename (expected format: `YYYY-MM-DD hh.mm.ss`). Files without a recognisable timestamp are skipped.
3. Loads the image and applies Otsu's binarisation to segment the PCB from the background.
4. Finds the largest contour in the thresholded image (assumed to be the PCB), computes its bounding box, and crops to it with configurable padding.
5. Scans the cropped image for barcodes (via **pyzbar**) and QR codes (via **OpenCV's QRCodeDetector**).
6. If the decoded value starts with the configured prefix (`d.superlab.au/` by default), the remainder is used as the serial number. Otherwise the full decoded value is used.
7. Saves the cropped image to `ProcessedImages/<serial>-<timestamp>.jpg`.
8. Moves the original image to `ImageBackups/<original_timestamp>.jpg`.

## Directory layout

```
scripts/
├── find_barcodes.py
├── IncomingImages/      # Drop new .jpg images here (input)
├── ProcessedImages/     # Cropped images, named by serial number (output)
└── ImageBackups/        # Original images after successful processing
```

All three directories must exist before running the script.

## Configuration

At the top of the script:

| Variable | Default | Description |
|---|---|---|
| `padding` | `100` | Pixel padding added around the PCB bounding box before cropping |
| `prefix` | `"d.superlab.au/"` | QR/barcode prefix stripped to derive the serial number |

## Dependencies

- **OpenCV** (`cv2`) — image loading, thresholding, contour detection, QR decoding
- **pyzbar** — barcode/QR decoding (secondary decoder)
- **numpy** — required by OpenCV

Install with:

```bash
pip install opencv-python pyzbar numpy
```

`pyzbar` also requires the `zbar` system library:

```bash
# Debian/Ubuntu
sudo apt install libzbar0

# macOS
brew install zbar
```

## Filename convention

Incoming images must include a timestamp in the filename matching:

```
YYYY-MM-DD hh.mm.ss
```

Example: `IncomingImages/2025-06-11 16.38.12.jpg`

The output filename uses the serial number and a normalised form of that timestamp:

```
ProcessedImages/<serial>-2025-06-11_16-38-12.jpg
```

## Notes

- If both pyzbar and OpenCV detect a code, the OpenCV result takes precedence (it is processed last and overwrites `serial_number`).
- If no serial number can be extracted from any code in the image, the image is left in `IncomingImages/` and not moved.
- The script uses Otsu's automatic global threshold by default. Alternative thresholding approaches (manual, adaptive) are included in the source as commented-out options, useful if lighting conditions vary significantly.

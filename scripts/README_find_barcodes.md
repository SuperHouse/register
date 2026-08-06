# find_barcodes.py

This script processes new photos of PCBs (printed circuit boards). It finds the board in each photo, reads its QR code or barcode, and saves a cropped copy of the image under the decoded serial number.

## What it does

1. Scans `IncomingImages/` for `.jpg` files.
2. Reads the timestamp in each file name. The expected format is `YYYY-MM-DD hh.mm.ss`. Skips a file if it has no timestamp.
3. Loads the image and applies Otsu's threshold to separate the board from the background.
4. Finds the largest shape in the thresholded image and treats it as the board. Crops the image to this shape's bounding box, plus a configurable margin.
5. Scans the cropped image for barcodes and QR codes, using the `zxing-cpp` library.
6. Checks each detected code against the rules in "Valid serial numbers" below, and keeps the last code that passes.
7. If a valid serial number remains, saves the cropped image to `ProcessedImages/<serial>-<timestamp>.jpg`, and moves the original image to `ImageBackups/<original_timestamp>.jpg`.
8. If no valid serial number remains, leaves the original image in `IncomingImages/` for manual review. The script also leaves the image in place if it finds no board shape at all.

## Valid serial numbers

A detected code sets the serial number only if it passes these checks.

- A QR code must start with one of the configured prefixes (see "Configuration"). The script uses the rest of the QR code as the serial number.
- A Code 128 barcode uses its full value as the serial number.
- The script ignores any other code format, for example a Data Matrix code. Some boards carry a Data Matrix code on an individual component, and this code is not the board serial number.
- The value must contain digits only.
- The value must fall inside the configured `min_serial`–`max_serial` range.

These checks stop the script from using an unrelated code by mistake, for example a microcontroller's own ID code, or a partly obscured label that decodes to a different, but still plausible, value.

## Directory layout

```
scripts/
├── find_barcodes.py
├── IncomingImages/      # Drop new .jpg images here (input)
├── ProcessedImages/     # Cropped images, named by serial number (output)
└── ImageBackups/        # Original images after successful processing
```

Create all three directories before you run the script.

## Configuration

Set these variables at the top of the script.

| Variable | Default | Description |
|---|---|---|
| `padding` | `100` | Pixels of margin added around the board's bounding box before the crop |
| `prefixes` | `["d.superlab.au/", "d.superhouse.tv/"]` | QR code prefixes. The script strips a matching prefix and uses the rest as the serial number |
| `min_serial` | `1000` | Lowest serial number the script accepts |
| `max_serial` | `99999` | Highest serial number the script accepts |

## Dependencies

- **OpenCV** (`cv2`) — image loading, thresholding, contour detection
- **zxing-cpp** — barcode and QR code decoding
- **numpy** — required by OpenCV

Install with:

```bash
pip install opencv-python zxing-cpp numpy
```

`zxing-cpp` needs no system library. It works the same way on macOS and Linux.

## Filename convention

An incoming image file name must contain a timestamp in this format:

```
YYYY-MM-DD hh.mm.ss
```

Example: `IncomingImages/2025-06-11 16.38.12.jpg`

The output file name uses the serial number and a normalized form of that timestamp:

```
ProcessedImages/<serial>-2025-06-11_16-38-12.jpg
```

## Notes

- The script resets the serial number, and both date variables, at the start of each loop iteration. This stops the script from reusing a value left over from a previous image.
- If a photo shows more than one valid code, the script keeps the value from the last one it processes.

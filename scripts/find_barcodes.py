#!/usr/bin/env python3

import cv2
import numpy as np
import zxingcpp
import re
import glob
import shutil

padding = 100                # pixels padding around bounding box of PCB detected in the image
prefixes = [                 # Find QR codes that begin with one of these prefixes and use the
    "d.superlab.au/",        # rest as the serial number
    "d.superhouse.tv/",
]
min_serial = 1               # Sanity bounds for a valid serial number. Leaves headroom while still
max_serial = 9999999         #  rejecting things like an individual component's own id getting misread as a serial.


def extract_serial(result):
    """Return the serial number encoded in a decoded barcode/QR result, or
    None if it doesn't look like a genuine board-label serial (e.g. it's a
    QR code for something else entirely, such as a microcontroller's own
    ID label, or a Data Matrix code from a component)."""
    text = result.text
    fmt = str(result.format)

    if fmt == "QR Code":
        # QR codes on these boards encode a URL. Anything else is a
        # different QR code that happened to be in frame.
        matched_prefix = next((p for p in prefixes if text.startswith(p)), None)
        if matched_prefix is None:
            return None
        candidate = text[len(matched_prefix):]
    elif fmt == "Code 128":
        candidate = text
    else:
        return None

    if not candidate.isdigit():
        return None
    if not (min_serial <= int(candidate) <= max_serial):
        return None
    return candidate

image_files = glob.glob("IncomingImages/*.jpg")

if image_files:
    print("Found images: ", image_files)
else:
    quit()

for image_filename in image_files:
    print(image_filename)
    #quit()

    # Reset per-image state. Without this, a value left over from a
    # previous iteration would be silently reused for an image where
    # nothing was actually detected.
    original_date = None
    image_date = None
    serial_number = None

    # Extract the image timestamp from its filename
    # Pattern to find "YYYY-MM-DD hh.mm.ss"
    pattern = r'\d{4}-\d{2}-\d{2} \d{2}\.\d{2}\.\d{2}'
    date_match = re.search(pattern, image_filename)

    if date_match:
        original_date = date_match.group(0)
        image_date = original_date.replace(" ", "_").replace(".", "-")
        print("Original:", original_date)
        print("Converted:", image_date)

    if image_date is None:
        print("No date found in the image filename. Skipping.")
        continue


    # Load the image
    #image = cv2.imread('IncomingImages/2025-06-11 16.38.12.jpg')
    image = cv2.imread(image_filename)

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Otsu's binarisation (automatic global threshold based on histogram):
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Find contours of the object
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # If at least one contour is found, we've detected an object
    if contours:
        # Find the largest contour (assumes object is the biggest blob)
        largest_contour = max(contours, key=cv2.contourArea)

        # Get bounding box coordinates
        x, y, w, h = cv2.boundingRect(largest_contour)

        # Add padding
        x_pad = max(x - padding, 0)
        y_pad = max(y - padding, 0)
        x_end = min(x + w + padding, image.shape[1])
        y_end = min(y + h + padding, image.shape[0])

        # Crop to bounding box
        cropped_image = image[y_pad:y_end, x_pad:x_end]

        # --- Barcode / QR Code Detection ---
        # Detect on a downscaled copy. At full resolution, dense silkscreen
        # detail on some boards sends zxingcpp's finder-pattern search into
        # a pathological, effectively non-terminating slowdown; downscaling
        # avoids it, while cropped_image (saved below) stays full resolution.
        detection_max_dimension = 2000
        scale = min(1.0, detection_max_dimension / max(cropped_image.shape[:2]))
        if scale < 1.0:
            detection_image = cv2.resize(cropped_image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        else:
            detection_image = cropped_image
        results = zxingcpp.read_barcodes(detection_image)

        for result in results:
            print(f"{result.format} detected:", result.text)
            candidate = extract_serial(result)
            if candidate is None:
                print("  -> ignored (not a valid board serial)")
            else:
                serial_number = candidate

        # Save the cropped image if we have a serial number
        if serial_number is None:
            print("Can't find a serial number in the image")
        else:
            print("### Serial is: " + serial_number)
            new_filename = 'ProcessedImages/' + serial_number + '-' + image_date + '.jpg'
            cv2.imwrite(new_filename, cropped_image)
            print("Cropped image saved as '" + new_filename + "'")
            backup_image_filename = 'ImageBackups/' + original_date + '.jpg'
            shutil.move(image_filename, backup_image_filename)

    else:
        print("No object detected.")


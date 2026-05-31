#!/usr/bin/python3

import cv2
import numpy as np
from pyzbar import pyzbar
import re
import glob
import shutil
import os

padding = 100               # pixels padding around bounding box of PCB detected in the image
prefix = "d.superlab.au/"   # Find QR codes that begin with this prefix and use the rest as the serial number

image_files = glob.glob("IncomingImages/*.jpg")

if image_files:
    print("Found images: ", image_files)
else:
    quit()

for image_filename in image_files:
    print(image_filename)
    #quit()
    # Extract the image timestamp from its filename
    # Pattern to find "YYYY-MM-DD hh.mm.ss"
    pattern = r'\d{4}-\d{2}-\d{2} \d{2}\.\d{2}\.\d{2}'
    date_match = re.search(pattern, image_filename)

    if date_match:
        original_date = date_match.group(0)
        image_date = original_date.replace(" ", "_").replace(".", "-")
        print("Original:", original_date)
        print("Converted:", image_date)

    try:
        image_date
    except NameError:
        print("No date found in the image filename. Skipping.")
        continue


    # Load the image
    #image = cv2.imread('IncomingImages/2025-06-11 16.38.12.jpg')
    image = cv2.imread(image_filename)

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Invert image if needed (depending on object/background contrast)
    #gray = cv2.bitwise_not(gray)

    # Threshold the image to separate object from background
    # Basic manual threshold:
    #_, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    # Otsu's binarisation (automatic global threshold based on histogram):
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Adaptive thresholding:
    #thresh = cv2.adaptiveThreshold(
    #    gray, 255,
    #    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,  # or ADAPTIVE_THRESH_MEAN_C
    #    cv2.THRESH_BINARY_INV,
    #    blockSize=11,  # neighborhood size
    #    C=2            # constant subtracted from mean
    #)


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

        # --- Barcode Detection ---
        barcodes = pyzbar.decode(cropped_image)

        if barcodes:
            for barcode in barcodes:
                barcode_data = barcode.data.decode("utf-8")
                print("Barcode detected:", barcode_data)
                if barcode_data.startswith(prefix):
                    serial_number = barcode_data[len(prefix):]
                else:
                    serial_number = barcode_data

        # --- QR Code Detection ---
        qr_detector = cv2.QRCodeDetector()
        qr_data, bbox, _ = qr_detector.detectAndDecode(cropped_image)

        if qr_data:
            print("QR Code detected:", qr_data)
            if qr_data.startswith(prefix):
                serial_number = qr_data[len(prefix):]
                print("####### Serial is: " + serial_number)
            else:
                print("QR Code detected, but prefix not matched:", qr_data)

        # Save the cropped image if we have a serial number
        try:
            serial_number
        except NameError:
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


# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import base64
from io import BytesIO

import qrcode


def generate_qr_data_uri(value, *, box_size=8, border=2):
    """Render value (a URL or any other string) to a QR code PNG as a base64 data URI.

    Generating server-side rather than via a JS library means the image is plain HTML
    by the time a page is printed or exported to PDF, with no dependency on a browser
    finishing a canvas render first.
    """
    image = qrcode.make(value, box_size=box_size, border=border)
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f'data:image/png;base64,{encoded}'

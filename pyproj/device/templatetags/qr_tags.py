# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django import template

from device.qr import generate_qr_data_uri

register = template.Library()


@register.filter
def qr_code(value):
    """Render value as a QR code PNG data URI, for direct use as an <img> src."""
    if not value:
        return ''
    return generate_qr_data_uri(str(value))

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe

from erp.models import STOCK_TREND_PERIOD

register = template.Library()

# Matches erp/templates/erp/part_edit.html's chart palette: '#898781' is the app's
# muted/axis-label tone (the sparkline's de-emphasis hue), '#2a78d6' the categorical
# slot-1 blue used as its accent.
_SPARKLINE_LINE_COLOR = '#898781'
_SPARKLINE_ACCENT_COLOR = '#2a78d6'


def _stock_sparkline_points(timed_values, window_start, window_end, width, height, pad_x=2, pad_y=3):
    """Map (timestamp, value) pairs to (x, y) SVG coordinates.

    x is placed proportionally within the fixed [window_start, window_end] span
    (matching the Stock History chart's x-axis, not evenly spaced by index), so a
    sparkline with only a few recent readings shows them clustered near the right
    edge rather than stretched across the full width.
    """
    values = [v for _, v in timed_values]
    lo, hi = min(values), max(values)
    span = hi - lo
    usable_w = width - 2 * pad_x
    usable_h = height - 2 * pad_y
    window_span = (window_end - window_start).total_seconds()
    points = []
    for ts, v in timed_values:
        frac = (ts - window_start).total_seconds() / window_span
        x = pad_x + frac * usable_w
        y = pad_y + (usable_h / 2 if span == 0 else (1 - (v - lo) / span) * usable_h)
        points.append((round(x, 2), round(y, 2)))
    return points


@register.filter
def stock_sparkline_svg(source, dims='64x20'):
    """Render a tiny inline SVG sparkline of a PartSource's stock history.

    The line is drawn in a muted/de-emphasis tone with only the most recent reading
    picked out in the accent color, following the stat-tile trend-sparkline
    convention - the point is the shape of the trend, not a precise readout (the
    adjacent Stock cell already shows the current number), so it's static markup
    with no hover/JS behaviour. Only readings within the last STOCK_TREND_PERIOD are
    plotted (same fixed window as the Stock History chart); returns '' when fewer
    than two known-stock readings fall in that window, since a single point has no
    trend to show.
    """
    width, height = (int(x) for x in dims.split('x'))
    window_end = timezone.now()
    window_start = window_end - STOCK_TREND_PERIOD
    timed_values = [
        (h.recorded_dt, h.stock)
        for h in reversed(source.stock_history.all())
        if h.stock is not None and h.recorded_dt >= window_start
    ]
    if len(timed_values) < 2:
        return ''

    points = _stock_sparkline_points(timed_values, window_start, window_end, width, height)
    path = ' '.join(f'{x},{y}' for x, y in points)
    last_x, last_y = points[-1]
    values = [v for _, v in timed_values]

    svg = (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'class="stock-sparkline" aria-hidden="true" focusable="false">'
        f'<title>Stock trend: {min(values)}–{max(values)} (most recent {values[-1]})</title>'
        f'<polyline points="{path}" fill="none" stroke="{_SPARKLINE_LINE_COLOR}" '
        f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{last_x}" cy="{last_y}" r="2.5" fill="{_SPARKLINE_ACCENT_COLOR}"/>'
        f'</svg>'
    )
    return mark_safe(svg)

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django import template
from django.utils.safestring import mark_safe
from markdown_it import MarkdownIt

register = template.Library()

# Raw HTML is off, so any HTML in the text is shown escaped, not run. markdown-it also refuses
# javascript:, vbscript: and file: links. Clients read this output, so keep html off.
_md = MarkdownIt('commonmark', {'html': False, 'breaks': True}).enable(['table', 'strikethrough'])


@register.filter
def markdown(text):
    """Render Markdown text (a project log entry body) to safe HTML."""
    if not text:
        return ''
    return mark_safe(_md.render(text))

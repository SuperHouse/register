"""
Per-hostname branding (issue #150).

When the site is reached through a client's vanity hostname (a BrandedHost), pages show
that client's logo, name, colours and favicon instead of the Testomatic defaults below. Any
other hostname gets the defaults. No organisation is special here: SuperHouse's own hostnames
are branded with BrandedHost records like any client's. Branding is cosmetic only and never
changes what data a user can see.
"""

from django.templatetags.static import static
from django.http.request import split_domain_port

from crm.models import BrandedHost

DEFAULT_BRAND_NAME = 'Testomatic'
DEFAULT_LOGO_STATIC = 'img/testomatic-logo-transparent.png'
DEFAULT_LOGO_LINK = 'https://www.testomatic.io/'

# Text colours used on a branded background: CoreUI's own light and dark text colours.
LIGHT_TEXT_RGB = (255, 255, 255)
DARK_TEXT_RGB = (0, 0, 21)


def get_branded_host(request):
    """The BrandedHost for the hostname this request came in on, or None. Looked up once per request."""
    if not hasattr(request, '_branded_host'):
        domain, _port = split_domain_port(request.get_host())
        request._branded_host = (
            BrandedHost.objects.select_related('org').filter(hostname=domain.lower()).first() if domain else None
        )
    return request._branded_host


def get_brand_name(request):
    host = get_branded_host(request)
    return host.brand_name if host else DEFAULT_BRAND_NAME


def hex_to_rgb(colour):
    colour = colour.lstrip('#')
    return tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(*(max(0, min(255, round(c))) for c in rgb))


def relative_luminance(rgb):
    """WCAG relative luminance, 0 (black) to 1 (white)."""
    def channel(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(rgb1, rgb2):
    lighter, darker = sorted((relative_luminance(rgb1), relative_luminance(rgb2)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def needs_dark_text(rgb):
    """True if dark text reads better than light text on this background."""
    return contrast_ratio(rgb, DARK_TEXT_RGB) > contrast_ratio(rgb, LIGHT_TEXT_RGB)


def mix(rgb, other, amount):
    """Move `amount` (0-1) of the way from rgb towards other."""
    return tuple(c + (o - c) * amount for c, o in zip(rgb, other))


def readable_on_white(rgb, minimum=4.5):
    """The colour, darkened just enough to be readable as text on a white page."""
    for step in range(21):
        candidate = mix(rgb, (0, 0, 0), step * 0.05)
        if contrast_ratio(candidate, (255, 255, 255)) >= minimum:
            return candidate
    return (0, 0, 0)


def sidebar_style(colour):
    rgb = hex_to_rgb(colour)
    return {'colour': colour, 'dark_text': needs_dark_text(rgb)}


def accent_style(colour):
    """Every shade the accent colour needs: buttons, their hover/active states, text on them, and links."""
    rgb = hex_to_rgb(colour)
    dark_text = needs_dark_text(rgb)
    # CoreUI lightens a dark button on hover; a light button is darkened instead, so the change shows.
    towards = (0, 0, 0) if dark_text else (255, 255, 255)
    link = readable_on_white(rgb)
    return {
        'colour': colour,
        'rgb': '{}, {}, {}'.format(*rgb),
        'text': 'rgba(0, 0, 21, 0.87)' if dark_text else 'rgba(255, 255, 255, 0.87)',
        'hover': rgb_to_hex(mix(rgb, towards, 0.15)),
        'active': rgb_to_hex(mix(rgb, towards, 0.2)),
        'link': rgb_to_hex(link),
        'link_rgb': '{}, {}, {}'.format(*(round(c) for c in link)),
        'link_hover': rgb_to_hex(mix(link, (0, 0, 0), 0.2)),
    }


def branding_processor(request):
    """Template context for the brand of the hostname this request came in on.

    brand_favicon_url is None unless the BrandedHost has its own favicon (the page then links the
    Testomatic icons). brand_is_custom is False on unbranded hostnames, where the sidebar's
    "powered by Testomatic" mark would just repeat the logo above it.
    """
    host = get_branded_host(request)
    if host is None:
        return {
            'brand_name': DEFAULT_BRAND_NAME,
            'brand_logo_url': static(DEFAULT_LOGO_STATIC),
            'brand_logo_link': DEFAULT_LOGO_LINK,
            'brand_logo_external': True,
            'brand_favicon_url': None,
            'brand_is_custom': False,
            'brand_sidebar': None,
            'brand_accent': None,
        }
    return {
        'brand_name': host.brand_name,
        'brand_logo_url': host.logo.url,
        'brand_logo_link': host.logo_link_url or '/',
        'brand_logo_external': bool(host.logo_link_url),
        'brand_favicon_url': host.favicon.url if host.favicon else None,
        'brand_is_custom': True,
        'brand_sidebar': sidebar_style(host.sidebar_colour) if host.sidebar_colour else None,
        'brand_accent': accent_style(host.accent_colour) if host.accent_colour else None,
    }

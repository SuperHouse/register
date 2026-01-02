import re
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def tnt_tracking_link(text):
    """
    Convert TNT tracking numbers in text to clickable links.
    Looks for "TNT" followed by a number and makes the number a clickable link to TNT tracking.
    """
    if not text or text is None:
        return text or ""
    
    # Pattern: "TNT" followed by optional space/punctuation and then digits
    # This will match "TNT123456", "TNT 123456", "TNT: 123456", etc.
    pattern = r'\bTNT\s*:?\s*(\d+)\b'
    
    def replace_tnt(match):
        tracking_number = match.group(1)
        url = f'https://www.tnt.com/express/en_au/site/shipping-tools/tracking.html?searchType=con&cons={tracking_number}'
        # Replace "TNT" followed by the number with "TNT" followed by a clickable link
        return f'TNT <a href="{url}" target="_blank" rel="noopener noreferrer">{tracking_number}</a>'
    
    # Replace all TNT tracking numbers with links
    result = re.sub(pattern, replace_tnt, text, flags=re.IGNORECASE)
    
    return mark_safe(result)



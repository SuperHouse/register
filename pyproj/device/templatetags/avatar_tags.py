import hashlib
from django import template
from django.conf import settings

register = template.Library()


def get_user_initials(user):
    """Generate initials from user's name."""
    if user.full_name:
        # Split full name and get first letter of first and last words
        parts = user.full_name.strip().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        elif len(parts) == 1:
            return parts[0][0].upper()
    
    if user.preferred_name:
        return user.preferred_name[0].upper()
    
    # Fallback to email username
    if user.email:
        return user.email[0].upper()
    
    return "?"


def get_avatar_color(user):
    """Generate a consistent color for a user based on their email."""
    if user.email:
        # Hash the email to get a consistent color
        hash_obj = hashlib.md5(user.email.encode())
        hash_hex = hash_obj.hexdigest()
        # Use first 6 characters for color
        color = '#' + hash_hex[:6]
        # Ensure it's not too light (for text visibility)
        # Convert to RGB and adjust if too light
        r, g, b = int(hash_hex[0:2], 16), int(hash_hex[2:4], 16), int(hash_hex[4:6], 16)
        # If average is too high (light), darken it
        avg = (r + g + b) / 3
        if avg > 200:
            r, g, b = int(r * 0.7), int(g * 0.7), int(b * 0.7)
        color = f'#{r:02x}{g:02x}{b:02x}'
        return color
    
    # Default color if no email
    return '#6c757d'


def get_gravatar_url(email, size=40, default='identicon'):
    """Generate Gravatar URL for an email address."""
    if not email:
        return None
    
    # Hash the email
    email_hash = hashlib.md5(email.lower().strip().encode()).hexdigest()
    
    # Build Gravatar URL
    gravatar_url = f"https://www.gravatar.com/avatar/{email_hash}?s={size}&d={default}"
    
    return gravatar_url


@register.simple_tag
def user_avatar_url(user, size=40, use_gravatar=None):
    """
    Get avatar URL for a user.
    
    Args:
        user: User object
        size: Size of avatar in pixels
        use_gravatar: Override user preference (True/False/None for user preference)
    
    Returns:
        URL string for avatar image, or None for initials
    """
    # Check user's avatar preference
    if use_gravatar is None:
        if hasattr(user, 'avatar_type'):
            use_gravatar = (user.avatar_type == user.GRAVATAR)
        else:
            # Fallback to system setting for backwards compatibility
            use_gravatar = getattr(settings, 'ENABLE_GRAVATAR', False)
    
    if use_gravatar and user.email:
        return get_gravatar_url(user.email, size=size)
    
    return None


@register.simple_tag
def user_avatar_initials(user):
    """Get initials for a user."""
    return get_user_initials(user)


@register.simple_tag
def user_avatar_color(user):
    """Get avatar background color for a user."""
    return get_avatar_color(user)


@register.inclusion_tag('device/avatar.html', takes_context=True)
def user_avatar(context, user, size=40, show_name=True, use_gravatar=None):
    """
    Render a user avatar (Gravatar or initials).
    
    Args:
        user: User object
        size: Size of avatar in pixels
        show_name: Whether to show user name next to avatar
        use_gravatar: Override user preference (True/False/None for user preference)
    
    Returns:
        Template context for avatar rendering
    """
    # Check user's avatar preference
    if use_gravatar is None:
        # Use user's preference if available, otherwise default to initials
        if hasattr(user, 'avatar_type'):
            use_gravatar = (user.avatar_type == user.GRAVATAR)
        else:
            # Fallback to system setting for backwards compatibility
            use_gravatar = getattr(settings, 'ENABLE_GRAVATAR', False)
    
    avatar_url = None
    if use_gravatar and user.email:
        avatar_url = get_gravatar_url(user.email, size=size)
    
    # Calculate font size for initials (approximately 40% of avatar size)
    font_size = int(size * 0.4)
    
    return {
        'user': user,
        'avatar_url': avatar_url,
        'initials': get_user_initials(user) if not avatar_url else None,
        'avatar_color': get_avatar_color(user),
        'size': size,
        'font_size': font_size,
        'show_name': show_name,
    }


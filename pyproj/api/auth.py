import ipaddress

from django.conf import settings
from ninja.security import APIKeyHeader

from authuser.models import User


def _parse_allowed_networks(value):
    """Normalise API_ALLOW_IPV4_SUBNET into a list of ip_network objects.

    Accepts a single CIDR string, or a list/tuple of CIDR strings, for
    devices reached via more than one subnet.
    """
    if not value:
        return []
    if isinstance(value, str):
        value = [value]
    return [ipaddress.ip_network(subnet) for subnet in value]


def session_or_api_key_auth(request):
    """Auth that accepts either Django session auth or API key auth."""
    # Try session auth first
    if request.user and request.user.is_authenticated:
        return {'auth_type': 'session', 'user': request.user}

    # Try API key auth
    api_key = request.headers.get('X-API-Key')
    if api_key:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            request_from = x_forwarded_for.split(',')[0]
        else:
            request_from = request.META.get('REMOTE_ADDR')

        try:
            ip_addr = ipaddress.ip_address(request_from)

            allowed_ipv4_networks = _parse_allowed_networks(settings.API_ALLOW_IPV4_SUBNET)
            local_network = ipaddress.ip_network('127.0.0.0/24')

            allow = False
            if ip_addr in local_network:
                allow = True
            if any(ip_addr in network for network in allowed_ipv4_networks):
                allow = True

            if allow:
                user = User.objects.filter(api_key=api_key, is_active=True).first()
                if user:
                    return {'auth_type': 'api_key', 'user': user}
        except ValueError:
            pass

    return None


class AuthByApiKey(APIKeyHeader):
    param_name = 'X-API-Key'

    allowed_ipv4_networks = _parse_allowed_networks(settings.API_ALLOW_IPV4_SUBNET)
    local_network = ipaddress.ip_network('127.0.0.0/24')

    # https://stackoverflow.com/questions/4581789/how-do-i-get-user-ip-address-in-django
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def authenticate(self, request, key):
        request_from = self.get_client_ip(request)
        ip_addr = ipaddress.ip_address(request_from)

        allow = False
        if ip_addr in self.local_network:
            allow = True
        if any(ip_addr in network for network in self.allowed_ipv4_networks):
            allow = True

        if not allow:
            return None

        if not key:
            return None

        return User.objects.filter(api_key=key, is_active=True).first()

import ipaddress

from django.conf import settings
from ninja.security import APIKeyHeader


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

            allowed_ipv4_network = ipaddress.ip_network(settings.API_ALLOW_IPV4_SUBNET) if settings.API_ALLOW_IPV4_SUBNET else None
            local_network = ipaddress.ip_network('127.0.0.0/24')

            allow = False
            if ip_addr in local_network:
                allow = True
            if allowed_ipv4_network and ip_addr in allowed_ipv4_network:
                allow = True

            if allow and Org.objects.filter(api_key=api_key).exists():
                return {'auth_type': 'api_key', 'key': api_key}
        except ValueError:
            pass

    return None


class AuthByApiKey(APIKeyHeader):
    param_name = 'X-API-Key'

    allowed_ipv4_network = ipaddress.ip_network(settings.API_ALLOW_IPV4_SUBNET) if settings.API_ALLOW_IPV4_SUBNET else None
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
        if self.allowed_ipv4_network and ip_addr in self.allowed_ipv4_network:
            allow = True

        if not allow:
            return

        # TOOD: fine-grained access
        # if key and Org.objects.filter(api_key=key).exists():
        #     return key

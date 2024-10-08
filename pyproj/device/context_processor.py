from django.conf import settings

from device.models import Client


def background_processor(request):
    bg_settings = settings.BACKGROUND_SETTINGS[settings.DEPLOY_TYPE or 'dev']

    bg = {k.lower(): bg_settings[k] for k in bg_settings.keys()}

    return bg


def get_client_logo_processor(request):
    context = {
        'client_logo': None,
        'client_name': 'No name',
    }

    if request.user.is_authenticated:
        context['client_name'] = request.user.preferred_name
        c_set = Client.objects.filter(users=request.user)
        if c_set.exists():
            c = c_set.first()
            if c.logo:
                context['client_logo'] = c.logo.url

    return context

from django.conf import settings

from crm.models import Client


def background_processor(request):
    bg_settings = settings.BACKGROUND_SETTINGS[settings.DEPLOY_TYPE or 'dev']

    bg = {k.lower(): bg_settings[k] for k in bg_settings.keys()}

    return bg


def demo_processor(request):
    enable_demo_mode = settings.DEMO_MODE
    context = {
        'enable_demo_mode': enable_demo_mode,
    }
    if enable_demo_mode:
        context.update(
            {
                # FIXME: Handle demo session var being unset?
                'demo': request.session.get('demo'),
                'demo_name': request.session.get('demo_name', 'normal'),
            }
        )

    return context


def version_processor(request):
    return {'app_version': settings.VERSION}



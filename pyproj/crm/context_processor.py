from crm.models import Org


def get_client_logo_processor(request):
    context = {
        'client_logo': None,
        'client_name': 'No name',
    }

    if request.user.is_authenticated:
        context['client_name'] = request.user.preferred_name
        c_set = Org.objects.filter(users=request.user)
        if c_set.exists():
            c = c_set.first()
            if c.logo:
                context['client_logo'] = c.logo.url

    return context

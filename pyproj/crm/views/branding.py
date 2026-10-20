from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.views.decorators.http import require_POST

from crm.branding import get_branded_host
from crm.forms import BrandedHostForm
from crm.models import BrandedHost, Org


def favicon(request):
    """/favicon.ico, for browsers that ask for it instead of reading the page's icon links.

    A temporary redirect: browsers keep a permanent one forever, so a changed icon would never show.
    """
    host = get_branded_host(request)
    return redirect(host.favicon.url if host and host.favicon else static('favicon.ico'))


def _edit_page(request, org, form, branded_host=None):
    context = {'client': org, 'form': form, 'branded_host': branded_host}
    return render(request, 'device/branded_host_edit.html', context)


@staff_member_required
def branded_host_add(request, client_id):
    org = get_object_or_404(Org, pk=client_id)
    if request.method == 'POST':
        form = BrandedHostForm(request.POST, request.FILES, instance=BrandedHost(org=org))
        if form.is_valid():
            branded_host = form.save()
            messages.success(request, f'Branding added for {branded_host.hostname}.')
            return redirect('organisation_edit', client_id=org.pk)
    else:
        form = BrandedHostForm(initial={'display_name': org.company_name})
    return _edit_page(request, org, form)


@staff_member_required
def branded_host_edit(request, branded_host_id):
    branded_host = get_object_or_404(BrandedHost.objects.select_related('org'), pk=branded_host_id)
    if request.method == 'POST':
        old_logo_name = branded_host.logo.name
        old_favicon_name = branded_host.favicon.name
        form = BrandedHostForm(request.POST, request.FILES, instance=branded_host)
        if form.is_valid():
            form.save()
            if branded_host.logo.name != old_logo_name:
                branded_host.logo.storage.delete(old_logo_name)
            if old_favicon_name and branded_host.favicon.name != old_favicon_name:
                branded_host.favicon.storage.delete(old_favicon_name)
            messages.success(request, f'Branding updated for {branded_host.hostname}.')
            return redirect('organisation_edit', client_id=branded_host.org_id)
    else:
        form = BrandedHostForm(instance=branded_host)
    return _edit_page(request, branded_host.org, form, branded_host)


@staff_member_required
@require_POST
def branded_host_delete(request, branded_host_id):
    branded_host = get_object_or_404(BrandedHost, pk=branded_host_id)
    org_id = branded_host.org_id
    branded_host.logo.delete(save=False)
    if branded_host.favicon:
        branded_host.favicon.delete(save=False)
    branded_host.delete()
    messages.success(request, f'Branding removed for {branded_host.hostname}.')
    return redirect('organisation_edit', client_id=org_id)

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect

from crm.models import Client
from device.forms import ClientForm
from device.models import Design, Device


# Create your views here.
@staff_member_required
def organisation_list(request):
    """List all clients/organisations."""
    clients = Client.objects.all().order_by('company_name')

    q = request.GET.get('q', '').strip()
    if q:
        clients = clients.filter(company_name__icontains=q)

    paginator = Paginator(clients, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'clients': page_obj,
        'page_obj': page_obj,
        'q': q,
    }

    return render(request, 'device/organisation_list.html', context)


@staff_member_required
def organisation_detail(request, client_id):
    """Detail view for a single organisation."""
    client = get_object_or_404(Client, pk=client_id)
    designs = Design.objects.filter(client=client).order_by('sku')
    board_count = Device.objects.filter(design__client=client).count()

    context = {
        'client': client,
        'designs': designs,
        'board_count': board_count,
    }

    return render(request, 'device/organisation_detail.html', context)


@staff_member_required
def organisation_edit(request, client_id):
    """Edit a client/organisation."""
    client = get_object_or_404(Client, pk=client_id)

    if request.method == "POST":
        form = ClientForm(request.POST, request.FILES, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, 'Organisation updated successfully.')
            return redirect("organisation_detail", client_id=client.pk)
        else:
            messages.warning(
                request,
                "Some field values have errors. Please review, and amend as required.",
            )
    else:
        form = ClientForm(instance=client)

    context = {
        'form': form,
        'client': client,
    }

    return render(request, 'device/organisation_edit.html', context)

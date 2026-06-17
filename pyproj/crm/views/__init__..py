from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect

from django.db.models import Prefetch, Q

from crm.models import Org
from device.views.forms import ClientForm
from device.models import Design, Device


@staff_member_required
def organisation_list(request):
    """List all clients/organisations."""
    clients = Org.objects.all().order_by('company_name')

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
    client = get_object_or_404(Org, pk=client_id)
    pcb_top_qs = DesignAsset.objects.filter(asset_type=DesignAsset.PCB_TOP)
    designs = Design.objects.filter(client=client).prefetch_related(
        Prefetch('designasset_set', queryset=pcb_top_qs, to_attr='pcb_top_assets'),
    ).order_by('sku')
    has_designs = designs.exists()

    q = request.GET.get('q', '').strip()
    if q:
        designs = designs.filter(
            Q(sku__icontains=q) |
            Q(name__icontains=q) |
            Q(hw_version__icontains=q)
        )

    board_count = Device.objects.filter(design__client=client).count()

    context = {
        'client': client,
        'designs': designs,
        'has_designs': has_designs,
        'board_count': board_count,
        'q': q,
    }

    return render(request, 'device/organisation_detail.html', context)


@staff_member_required
def organisation_edit(request, client_id):
    """Edit a client/organisation."""
    client = get_object_or_404(Org, pk=client_id)

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

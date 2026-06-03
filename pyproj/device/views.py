# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db.models.functions import TruncMonth
import json

from login_required import login_not_required

from .forms import ClientForm, DesignAssetEditForm, DesignAssetForm, DeviceEventForm, DeviceImageEditForm, DeviceImageForm, TestRecordForm
from .models import Client, Design, DesignAsset, Device, DeviceEvent, DeviceImage, TestRecord


def dashboard(request):
    """Dashboard view showing summary statistics."""
    clients = Client.objects.all()
    designs = Design.objects.all()
    devices = Device.objects.all()

    if not request.user.is_staff:
        clients = clients.filter(users=request.user)
        designs = designs.filter(client__in=clients)
        devices = devices.filter(design__client__in=clients)

    # Calculate devices created per month
    devices_by_month = (
        devices
        .annotate(month=TruncMonth('creation_dt'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    
    # Prepare data for chart
    chart_labels = []
    chart_data = []
    
    for item in devices_by_month:
        # Format month as "MMM YYYY" for better readability (e.g., "Jan 2024")
        if item['month']:
            month_str = item['month'].strftime('%b %Y')
            chart_labels.append(month_str)
            chart_data.append(item['count'])
    
    context = {
        'client_count': clients.count(),
        'design_count': designs.count(),
        'device_count': devices.count(),
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }

    return render(request, 'device/dashboard.html', context)


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


def top(request):
    devices = Device.objects.prefetch_related("design").order_by('pk').all()

    if not request.user.is_staff:
        clients = Client.objects.filter(users=request.user)
        devices = devices.filter(design__client__in=clients)

    q = request.GET.get('q', '').strip()
    if q:
        devices = devices.filter(
            Q(pk__icontains=q) |
            Q(design__sku__icontains=q) |
            Q(design__name__icontains=q) |
            Q(design__hw_version__icontains=q)
        )

    paginator = Paginator(devices, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'devices': page_obj,
        'q': q,
    }

    return render(request, 'device/top.html', context)


def design_list(request):
    """List all designs."""
    designs = Design.objects.prefetch_related("client").order_by('client', 'sku').all()

    if not request.user.is_staff:
        clients = Client.objects.filter(users=request.user)
        designs = designs.filter(client__in=clients)

    q = request.GET.get('q', '').strip()
    if q:
        designs = designs.filter(
            Q(client__company_name__icontains=q) |
            Q(sku__icontains=q) |
            Q(name__icontains=q) |
            Q(hw_version__icontains=q)
        )

    paginator = Paginator(designs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'designs': page_obj,
        'page_obj': page_obj,
        'q': q,
    }

    return render(request, 'device/design_list.html', context)


def design_detail(request, design_id):
    """Detail view for a single design."""
    if request.user.is_staff:
        design = get_object_or_404(Design, pk=design_id)
        assets = design.designasset_set.all()
    else:
        clients = Client.objects.filter(users=request.user)
        design = get_object_or_404(Design, pk=design_id, client__in=clients)
        assets = design.designasset_set.filter(internal=False)

    devices = Device.objects.filter(design=design).order_by('pk')

    core_type_order = [
        (DesignAsset.PCB_3D, 'PCB 3D View'),
        (DesignAsset.PCB_TOP, 'PCB Top View'),
        (DesignAsset.PCB_BOTTOM, 'PCB Bottom View'),
        (DesignAsset.FUSION, 'Fusion Electronics Project'),
        (DesignAsset.SCHEMATIC, 'Schematic Design File'),
        (DesignAsset.PCB_DESIGN, 'PCB Design File'),
        (DesignAsset.BOM, 'Bill of Materials'),
        (DesignAsset.FIRMWARE, 'Firmware Binary'),
    ]
    existing_core = {a.asset_type: a for a in assets.filter(asset_type__in=DesignAsset.CORE_ASSET_TYPES)}
    core_assets = [(type_key, label, existing_core.get(type_key)) for type_key, label in core_type_order]
    has_core_assets = bool(existing_core)

    attachments = assets.filter(asset_type=DesignAsset.ATTACHMENT)
    pcb_top_asset = existing_core.get(DesignAsset.PCB_TOP)

    context = {
        'design': design,
        'devices': devices,
        'device_count': devices.count(),
        'core_assets': core_assets,
        'has_core_assets': has_core_assets,
        'attachments': attachments,
        'asset_form': DesignAssetForm() if request.user.is_staff else None,
        'pcb_top_asset': pcb_top_asset,
    }

    return render(request, 'device/design_detail.html', context)


@staff_member_required
def design_asset_add(request, design_id):
    design = get_object_or_404(Design, pk=design_id)

    if request.method == 'POST':
        form = DesignAssetForm(request.POST, request.FILES)
        if form.is_valid():
            form.instance.design = design
            asset_type = form.cleaned_data['asset_type']
            replaced = False
            if asset_type in DesignAsset.CORE_ASSET_TYPES:
                existing = DesignAsset.objects.filter(design=design, asset_type=asset_type).first()
                if existing:
                    existing.file.delete(save=False)
                    existing.delete()
                    replaced = True
            form.save()
            messages.success(request, 'File replaced successfully.' if replaced else 'File uploaded successfully.')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')

    return redirect('design_detail', design_id=design.pk)


@staff_member_required
def design_asset_edit(request, asset_id):
    asset = get_object_or_404(DesignAsset, pk=asset_id)
    design = asset.design

    if request.method == 'POST':
        form = DesignAssetEditForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            messages.success(request, 'Asset updated.')
            return redirect('design_detail', design_id=design.pk)
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = DesignAssetEditForm(instance=asset)

    ctx = {
        'form': form,
        'asset': asset,
        'design': design,
    }

    return render(request, 'device/design_asset_edit.html', ctx)


@staff_member_required
def design_asset_delete(request, asset_id):
    asset = get_object_or_404(DesignAsset, pk=asset_id)
    design = asset.design

    if request.method == 'POST':
        asset.file.delete(save=False)
        asset.delete()
        messages.success(request, 'Asset deleted.')
        return redirect('design_detail', design_id=design.pk)

    ctx = {
        'asset': asset,
        'design': design,
    }

    return render(request, 'device/design_asset_delete.html', ctx)


def bootstrap_demo(request):
    context = {}

    return render(request, 'device/bootstrap-demo.html', context)


def inc_demo(request):
    demo_names = (
        'normal',
        'sldemo',
        'b5demo',
    )

    demo_level = request.session.get('demo')
    if demo_level is None:
        demo_level = 1
    else:
        demo_level += 1
    if demo_level >= len(demo_names):
        demo_level = 0

    request.session['demo'] = demo_level
    request.session['demo_name'] = demo_names[demo_level]

    from_url = request.headers['Referer']
    if from_url:
        return HttpResponseRedirect(from_url)
    else:
        return redirect('home')


@login_not_required
def perm_report(request):
    context = {}

    return render(request, 'device/perm_report.html', context)


def general_action(request):
    return render(request, 'device/general_action.html')


@staff_member_required
def device_grid(request):
    # FIXME: Very slow to run, so the user has to agree first that
    # they know it's going to be slow.  The slowdown isn't in the db.
    # FIXME: Doesn't show device events.
    # FIXME: Fix Frappe-datatable layout problem in second tab.
    def provide1():
        for device in (
            Device.objects.select_related('design').prefetch_related('testrecord_set').all()
        ):  # .select_related("testrecord_set")
            tr_set = device.testrecord_set.all()
            if tr_set:
                if tr_set.count() > 1:
                    tr_str = ', '.join([tr.get_test_dt_as_string() for tr in tr_set])
                    tr_str = f'({tr_str})'
                else:
                    tr_str = tr_set.first().get_test_dt_as_string()
            else:
                tr_str = ''

            row = (
                device.pk,
                device.design_id,
                device.get_creation_dt_as_string(),
                tr_str,
                device.latest_sw_version() or '',
                device.notes or '',
                device.design.name,
                device.design.hw_version,
                device.invoice or '',
            )

            yield row

    def provide2():
        for design in Design.objects.all():
            row = (
                design.pk,
                design.client.pk,
                design.sku,
                design.name,
                design.hw_version,
                design.client.company_name,
                design.price or '',
                design.price2 or '',
            )

            yield row

    context = {
        'warned': False,
    }

    if request.GET.get('warned'):
        context.update(
            {
                'warned': True,
                'headings1': 'Serial/DeviceTypeSerial/Assembled/Tested/Firmware/Notes/Device/HW Version/Invoice'.split(
                    '/'
                ),
                'data1': provide1(),
                'headings2': 'Serial/ClientSerial/SKU/Name/HW Version/Customer/Price/Price2'.split('/'),
                'data2': provide2(),
            }
        )

    return render(request, 'device/device_grid.html', context)


def device_detail(request, device_number):
    if request.user.is_staff:
        device = get_object_or_404(Device, pk=device_number)
        events = device.deviceevent_set.all()
    else:
        clients = Client.objects.filter(users=request.user)
        device = get_object_or_404(Device, design__client__in=clients, pk=device_number)
        events = device.deviceevent_set.exclude(internal=True)

    device_images = device.deviceimage_set.all()

    context = {
        'device': device,
        'events': events,
        'device_images': device_images,
    }

    return render(request, 'device/device_detail.html', context)


@staff_member_required
def device_action(request, device_number):
    if request.user.is_staff:
        device = get_object_or_404(Device, pk=device_number)
    else:
        clients = Client.objects.filter(users=request.user)
        device = get_object_or_404(Device, design__client__in=clients, pk=device_number)

    context = {
        'device': device,
    }

    messages.success(request, 'Action worked just fine!')

    return render(request, 'device/device_action.html', context)


def device_search(request):
    q = request.GET.get('q') or ''
    msg = ''

    if q:
        # FIXME: Try doing this with a .get().
        try:
            device_set = Device.objects.filter(pk=q)
        except ValueError:
            msg = 'Please enter a numeric serial number.'

        if not msg:
            if not request.user.is_staff:
                clients = Client.objects.filter(users=request.user)
                device_set = device_set.filter(design__client__in=clients)
            if device_set:
                device = device_set.first()
                return redirect("device:device_detail", device_number=device.pk)
            msg = "There's no board with that serial number."

    if msg:
        messages.error(request, msg)

    context = {
        'q': q,
    }

    return render(request, 'device/device_search.html', context)


@staff_member_required
def device_event_add(request, device_number):
    device = get_object_or_404(Device, pk=device_number)

    if request.method == "POST":
        form = DeviceEventForm(request.POST, initial={'device': device})
        if form.is_valid():
            form.instance.device = device
            event = form.save()

            messages.success(request, 'Event added.')

            return redirect("device:device_detail", device_number=event.device.pk)
        else:
            messages.warning(
                request,
                "Some field values have errors.  Please review, and amend as required.",
            )
            # Drop through to re-render the form with the error messages

    else:
        # if a GET (or any other method) we'll create a blank form
        form = DeviceEventForm()

    ctx = {
        'form': form,
        'device': device,
        'operation': 'Add',
        'ts': None,
    }

    return render(request, "device/device_event_edit.html", ctx)


@staff_member_required
def device_event_edit(request, device_event_number):
    event = get_object_or_404(DeviceEvent, pk=device_event_number)

    if request.method == "POST":
        form = DeviceEventForm(request.POST, instance=event)
        if form.is_valid():
            form.instance.event_dt = timezone.now()
            event = form.save()

            messages.success(request, 'Event saved.')

            return redirect("device:device_detail", device_number=event.device.pk)
        else:
            messages.warning(
                request,
                "Some field values have errors.  Please review, and amend as required.",
            )
            # Drop through to re-render the form with the error messages

    else:
        # if a GET (or any other method) we'll create a blank form
        form = DeviceEventForm(instance=event)

    ctx = {
        'form': form,
        'device': event.device,
        'operation': 'Edit',
    }

    return render(request, "device/device_event_edit.html", ctx)


@staff_member_required
def device_event_delete(request, device_event_number):
    event = get_object_or_404(DeviceEvent, pk=device_event_number)

    if request.method == "POST":
        event.delete()
        messages.success(
            request,
            "Device event deleted.",
        )

        return redirect("device:device_detail", device_number=event.device.pk)

    ctx = {
        'event': event,
    }

    return render(request, "device/device_event_delete.html", ctx)


@staff_member_required
def test_record_add(request, device_number):
    device = get_object_or_404(Device, pk=device_number)

    if request.method == "POST":
        form = TestRecordForm(request.POST, initial={'device': device})
        if form.is_valid():
            form.instance.device = device
            event = form.save()

            messages.success(request, 'Test record added.')

            return redirect("device:device_detail", device_number=event.device.pk)
        else:
            messages.warning(
                request,
                "Some field values have errors.  Please review, and amend as required.",
            )
            # Drop through to re-render the form with the error messages

    else:
        # if a GET (or any other method) we'll create a blank form
        form = TestRecordForm()

    ctx = {
        'form': form,
        'device': device,
        'operation': 'Add',
        'ts': None,
    }

    return render(request, "device/device_event_edit.html", ctx)


@staff_member_required
def test_record_edit(request, test_record_number):
    test_record = get_object_or_404(TestRecord, pk=test_record_number)

    if request.method == "POST":
        form = TestRecordForm(request.POST, instance=test_record)
        if form.is_valid():
            form.save()

            messages.success(request, 'Test record saved.')

            return redirect("device:device_detail", device_number=test_record.device.pk)
        else:
            messages.warning(
                request,
                "Some field values have errors.  Please review, and amend as required.",
            )
            # Drop through to re-render the form with the error messages

    else:
        # if a GET (or any other method) we'll create a blank form
        form = TestRecordForm(instance=test_record)

    ctx = {
        'form': form,
        'device': test_record.device,
        'operation': 'Edit',
        'ts': test_record.test_dt,
    }

    return render(request, "device/test_record_edit.html", ctx)


@staff_member_required
def device_image_add(request, device_number):
    device = get_object_or_404(Device, pk=device_number)

    if request.method == "POST":
        form = DeviceImageForm(request.POST, request.FILES, initial={'device': device})
        if form.is_valid():
            form.instance.device = device
            device_image = form.save()

            messages.success(request, 'Image uploaded successfully.')

            return redirect("device:device_detail", device_number=device_image.device.pk)
        else:
            messages.warning(
                request,
                "Some field values have errors.  Please review, and amend as required.",
            )
            # Drop through to re-render the form with the error messages

    else:
        # if a GET (or any other method) we'll create a blank form
        form = DeviceImageForm(initial={'device': device})

    ctx = {
        'form': form,
        'device': device,
        'operation': 'Upload',
    }

    return render(request, "device/device_image_upload.html", ctx)


@staff_member_required
def device_image_edit(request, device_image_number):
    device_image = get_object_or_404(DeviceImage, pk=device_image_number)
    device = device_image.device

    if request.method == "POST":
        form = DeviceImageEditForm(request.POST, instance=device_image)
        if form.is_valid():
            form.save()
            messages.success(request, 'Image notes updated.')

            return redirect("device:device_detail", device_number=device.pk)
        else:
            messages.warning(
                request,
                "Some field values have errors.  Please review, and amend as required.",
            )
            # Drop through to re-render the form with the error messages

    else:
        # if a GET (or any other method) we'll create a form with the current instance
        form = DeviceImageEditForm(instance=device_image)

    ctx = {
        'form': form,
        'device_image': device_image,
        'device': device,
        'operation': 'Edit',
    }

    return render(request, "device/device_image_edit.html", ctx)


@staff_member_required
def device_image_delete(request, device_image_number):
    device_image = get_object_or_404(DeviceImage, pk=device_image_number)
    device = device_image.device

    if request.method == "POST":
        device_image.delete()
        messages.success(
            request,
            "Device image deleted.",
        )

        return redirect("device:device_detail", device_number=device.pk)

    ctx = {
        'device_image': device_image,
        'device': device,
    }

    return render(request, "device/device_image_delete.html", ctx)


def test_messages(request):
    mtype = request.GET.get('mtype') or ''

    if mtype == 'debug':
        messages.debug(request, 'This is a debug message.')
    elif mtype == 'info':
        messages.info(request, 'This is an info message.')
    elif mtype == 'success':
        messages.success(request, 'This is a success message.')
    elif mtype == 'warning':
        messages.warning(request, 'This is a warning message.')
    elif mtype == 'error':
        messages.error(request, 'This is an error message.')
    elif mtype == 'all':
        messages.debug(request, 'This is a debug message.')
        messages.info(request, 'This is an info message.')
        messages.success(request, 'This is a success message.')
        messages.warning(request, 'This is a warning message.')
        messages.error(request, 'This is an error message.')

    context = {
        'mtype': mtype,
    }

    return render(request, 'device/messages.html', context)

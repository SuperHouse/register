# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import os
import tempfile
from pathlib import Path

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.files import File
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q, Sum
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db.models.functions import TruncMonth
import json

from fusionextractor.exceptions import FusionExtractorError
from fusionextractor.f3z import FusionProject

from login_required import login_not_required

from .forms import DesignAssetEditForm, DesignAssetForm, DeviceAssetEditForm, DeviceAssetForm, DeviceEventForm, DeviceImageEditForm, DeviceImageForm, TestRecordForm
from .models import Design, DesignAsset, Device, DeviceAsset, DeviceEvent, DeviceImage, TestRecord
from crm.models import Org
from erp.forms import DesignBomEntryForm
from erp.models import Batch, Part


def dashboard(request):
    """Dashboard view showing summary statistics."""
    clients = Org.objects.all()
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
        'part_count': Part.objects.count(),
        'batch_count': Batch.objects.count(),
        'stock_count': Part.objects.aggregate(total=Sum('stock'))['total'] or 0,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }

    return render(request, 'device/dashboard.html', context)


def top(request):
    devices = Device.objects.prefetch_related("design").order_by('pk').all()

    if not request.user.is_staff:
        clients = Org.objects.filter(users=request.user)
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
    pcb_top_qs = DesignAsset.objects.filter(asset_type=DesignAsset.PCB_TOP)

    if not request.user.is_staff:
        clients = Org.objects.filter(users=request.user)
        pcb_top_qs = pcb_top_qs.filter(internal=False)

    designs = Design.objects.prefetch_related(
        "client",
        Prefetch('designasset_set', queryset=pcb_top_qs, to_attr='pcb_top_assets'),
    ).order_by('obsolete', 'client', 'sku').all()

    if not request.user.is_staff:
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
        clients = Org.objects.filter(users=request.user)
        design = get_object_or_404(Design, pk=design_id, client__in=clients)
        assets = design.designasset_set.filter(internal=False)

    devices = Device.objects.filter(design=design).order_by('pk')

    core_type_order = [
        (DesignAsset.FUSION, 'Fusion Electronics Project'),
        (DesignAsset.PCB_3D, 'PCB 3D View'),
        (DesignAsset.PCB_TOP, 'PCB Top View'),
        (DesignAsset.PCB_BOTTOM, 'PCB Bottom View'),
        (DesignAsset.SCHEMATIC, 'Schematic Design File'),
        (DesignAsset.PCB_DESIGN, 'PCB Design File'),
        (DesignAsset.BOM, 'Bill of Materials'),
    ]
    testing_type_order = [
        (DesignAsset.FIRMWARE, 'Firmware Binary'),
    ]
    existing_core = {a.asset_type: a for a in assets.filter(asset_type__in=DesignAsset.CORE_ASSET_TYPES)}
    core_assets = [(type_key, label, existing_core.get(type_key)) for type_key, label in core_type_order]
    has_core_assets = any(asset for _, _, asset in core_assets)
    testing_assets = [(type_key, label, existing_core.get(type_key)) for type_key, label in testing_type_order]
    has_testing_assets = any(asset for _, _, asset in testing_assets)

    attachments = assets.filter(asset_type=DesignAsset.ATTACHMENT)
    pcb_top_asset = existing_core.get(DesignAsset.PCB_TOP)
    pcb_bottom_asset = existing_core.get(DesignAsset.PCB_BOTTOM)
    bom_csv_asset = existing_core.get(DesignAsset.BOM)
    bom_entries = sorted(
        design.bom_entries.select_related('part', 'part__category').all(),
        key=lambda entry: entry.reference_sort_key,
    )
    bom_total_smt_joints = sum(entry.part.smt_joints or 0 for entry in bom_entries)
    bom_total_pth_joints = sum(entry.part.pth_joints or 0 for entry in bom_entries)

    context = {
        'design': design,
        'devices': devices,
        'device_count': devices.count(),
        'core_assets': core_assets,
        'has_core_assets': has_core_assets,
        'testing_assets': testing_assets,
        'has_testing_assets': has_testing_assets,
        'attachments': attachments,
        'asset_form': DesignAssetForm() if request.user.is_staff else None,
        'pcb_top_asset': pcb_top_asset,
        'pcb_bottom_asset': pcb_bottom_asset,
        'bom_entries': bom_entries,
        'bom_total_smt_joints': bom_total_smt_joints,
        'bom_total_pth_joints': bom_total_pth_joints,
        'bom_csv_asset': bom_csv_asset,
        'bom_entry_form': DesignBomEntryForm() if request.user.is_staff else None,
    }

    return render(request, 'device/design_detail.html', context)


def _extract_fusion_assets(design, f3z_path, stem):
    """Extract BOM, board, schematic, and PCB renders from a .f3z file and save as DesignAssets."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        with FusionProject(f3z_path) as proj:
            bom_path = proj.extract_bom(tmpdir_path)
            board_path = proj.extract_board(tmpdir_path)
            sch_path = proj.extract_schematic(tmpdir_path)
            pcb_top_path = proj.extract_board_image('pcb_3d_top', tmpdir_path)
            pcb_bottom_path = proj.extract_board_image('pcb_3d_bottom', tmpdir_path)
            pcb_3d_path = None
            for preview in proj.get_previews(include_large_images=False):
                if preview.source == '3d_model':
                    pcb_3d_path = tmpdir_path / '3d_model__small.png'
                    pcb_3d_path.write_bytes(preview.data)
                    break

        for asset_type, extracted_path, name_suffix, suffix in [
            (DesignAsset.BOM, bom_path, '', '.csv'),
            (DesignAsset.PCB_DESIGN, board_path, '', '.brd'),
            (DesignAsset.SCHEMATIC, sch_path, '', '.sch'),
            (DesignAsset.PCB_TOP, pcb_top_path, '-top', pcb_top_path.suffix),
            (DesignAsset.PCB_BOTTOM, pcb_bottom_path, '-bottom', pcb_bottom_path.suffix),
            (DesignAsset.PCB_3D, pcb_3d_path, '-3d', '.png'),
        ]:
            if extracted_path is None:
                continue
            existing = DesignAsset.objects.filter(design=design, asset_type=asset_type).first()
            if existing:
                existing.file.delete(save=False)
                existing.delete()

            asset = DesignAsset(design=design, name=stem, asset_type=asset_type)
            with open(extracted_path, 'rb') as f:
                asset.file.save(f"{stem}{name_suffix}{suffix}", File(f), save=True)


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
            saved_asset = form.save()
            messages.success(request, 'File replaced successfully.' if replaced else 'File uploaded successfully.')

            if asset_type == DesignAsset.FUSION and saved_asset.filename.lower().endswith('.f3z'):
                stem = Path(saved_asset.filename).stem
                try:
                    _extract_fusion_assets(design, saved_asset.file.path, stem)
                    messages.success(request, 'BOM, PCB design file, schematic, and PCB renders extracted from Fusion project.')
                except FusionExtractorError as e:
                    messages.warning(request, f'Fusion project uploaded, but asset extraction failed: {e}')
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


@staff_member_required
def design_swap_pcb_images(request, design_id):
    """Swap the files of the PCB Top View and PCB Bottom View assets.

    FusionExtractor occasionally extracts the top/bottom renders the wrong way
    round. Swapping the files on disk (rather than the DesignAsset rows) means
    each asset keeps its own pk/name/description and nothing else needs to
    change its references to them.
    """
    design = get_object_or_404(Design, pk=design_id)

    if request.method == 'POST':
        top_asset = DesignAsset.objects.filter(design=design, asset_type=DesignAsset.PCB_TOP).first()
        bottom_asset = DesignAsset.objects.filter(design=design, asset_type=DesignAsset.PCB_BOTTOM).first()

        if not top_asset or not bottom_asset:
            messages.warning(request, 'Both a PCB Top View and PCB Bottom View must be uploaded before they can be swapped.')
        else:
            top_path = Path(top_asset.file.path)
            bottom_path = Path(bottom_asset.file.path)
            temp_path = top_path.with_name(f'.swap-{top_path.name}')

            top_path.rename(temp_path)
            bottom_path.rename(top_path)
            temp_path.rename(bottom_path)

            # Renaming preserves each file's original mtime, which would
            # otherwise let a cache keyed on Last-Modified serve stale content
            # from the swapped-in file's old path. Setting an explicit mtime
            # (unlike the renames above) requires owning the file, not just
            # having group write access, so this is skipped rather than
            # left to crash the request for assets owned by another user
            # (e.g. restored from a backup or extracted via a script).
            now = timezone.now().timestamp()
            try:
                os.utime(top_path, (now, now))
                os.utime(bottom_path, (now, now))
            except PermissionError:
                pass

            messages.success(request, 'PCB Top View and PCB Bottom View images swapped.')

    return redirect('design_detail', design_id=design.pk)


@staff_member_required
def design_toggle_obsolete(request, design_id):
    """Toggle a design's obsolete flag."""
    design = get_object_or_404(Design, pk=design_id)

    if request.method == 'POST':
        design.obsolete = not design.obsolete
        design.save()
        messages.success(request, f'Design marked as {"obsolete" if design.obsolete else "current"}.')

    return redirect('design_detail', design_id=design.pk)


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
        assets = device.deviceasset_set.all()
    else:
        clients = Org.objects.filter(users=request.user)
        device = get_object_or_404(Device, design__client__in=clients, pk=device_number)
        events = device.deviceevent_set.exclude(internal=True)
        assets = device.deviceasset_set.filter(internal=False)

    device_images = device.deviceimage_set.all()
    attachments = assets.filter(asset_type=DeviceAsset.ATTACHMENT)

    context = {
        'device': device,
        'events': events,
        'device_images': device_images,
        'attachments': attachments,
    }

    return render(request, 'device/device_detail.html', context)


@staff_member_required
def device_action(request, device_number):
    if request.user.is_staff:
        device = get_object_or_404(Device, pk=device_number)
    else:
        clients = Org.objects.filter(users=request.user)
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
                clients = Org.objects.filter(users=request.user)
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
def device_asset_add(request, device_number):
    device = get_object_or_404(Device, pk=device_number)

    if request.method == 'POST':
        form = DeviceAssetForm(request.POST, request.FILES)
        if form.is_valid():
            form.instance.device = device
            form.save()
            messages.success(request, 'File uploaded successfully.')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')

    return redirect('device:device_detail', device_number=device.pk)


@staff_member_required
def device_asset_edit(request, asset_id):
    asset = get_object_or_404(DeviceAsset, pk=asset_id)
    device = asset.device

    if request.method == 'POST':
        form = DeviceAssetEditForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            messages.success(request, 'Asset updated.')
            return redirect('device:device_detail', device_number=device.pk)
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = DeviceAssetEditForm(instance=asset)

    ctx = {
        'form': form,
        'asset': asset,
        'device': device,
    }

    return render(request, 'device/device_asset_edit.html', ctx)


@staff_member_required
def device_asset_delete(request, asset_id):
    asset = get_object_or_404(DeviceAsset, pk=asset_id)
    device = asset.device

    if request.method == 'POST':
        asset.file.delete(save=False)
        asset.delete()
        messages.success(request, 'Asset deleted.')
        return redirect('device:device_detail', device_number=device.pk)

    ctx = {
        'asset': asset,
        'device': device,
    }

    return render(request, 'device/device_asset_delete.html', ctx)


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

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import csv
import io
import json
import os
from pathlib import Path

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Prefetch, ProtectedError, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import (
    BatchApplyTemplateForm,
    BatchForm,
    BatchProductionStageAddForm,
    BatchProductionStageUpdateForm,
    LocationForm,
    PartAssetForm,
    PartCategoryForm,
    PartForm,
    PartSourceForm,
    ProductionStageForm,
    ProductionStageTemplateForm,
    ProductionStageTemplateStepForm,
)
from device.models import DesignAsset
from .models import Batch, BatchProductionStage, Location, Part, PartAsset, PartCategory, PartSource, ProductionStage, ProductionStageTemplate, ProductionStageTemplateStep


def _apply_template_to_batch(batch, template):
    last_stage = batch.production_stages.order_by('-order').first()
    next_order = (last_stage.order + 1) if last_stage else 1

    existing_names = set(batch.production_stages.values_list('name', flat=True))

    for step in template.steps.select_related('production_stage').order_by('order'):
        if step.production_stage.name in existing_names:
            continue

        BatchProductionStage.objects.create(
            batch=batch,
            name=step.production_stage.name,
            color=step.production_stage.color,
            order=next_order,
            status=BatchProductionStage.NOT_STARTED,
        )
        next_order += 1
        existing_names.add(step.production_stage.name)


@staff_member_required
def settings_index(request):
    return render(request, 'erp/settings_index.html')


@staff_member_required
def production_stage_list(request):
    production_stages = ProductionStage.objects.all()

    if request.method == 'POST':
        form = ProductionStageForm(request.POST)
        if form.is_valid():
            last_stage = ProductionStage.objects.order_by('-order').first()
            next_order = (last_stage.order + 1) if last_stage else 1

            stage = form.save(commit=False)
            stage.order = next_order
            stage.save()
            messages.success(request, 'Production stage added.')
            return redirect('erp:production_stage_list')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = ProductionStageForm()

    ctx = {
        'production_stages': production_stages,
        'form': form,
    }

    return render(request, 'erp/production_stage_list.html', ctx)


@staff_member_required
def production_stage_edit(request, production_stage_id):
    production_stage = get_object_or_404(ProductionStage, pk=production_stage_id)

    if request.method == 'POST':
        form = ProductionStageForm(request.POST, instance=production_stage)
        if form.is_valid():
            form.save()
            messages.success(request, 'Production stage updated.')
            return redirect('erp:production_stage_list')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = ProductionStageForm(instance=production_stage)

    ctx = {
        'form': form,
        'production_stage': production_stage,
    }

    return render(request, 'erp/production_stage_edit.html', ctx)


@staff_member_required
def production_stage_reorder(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        stages_by_id = {stage.pk: stage for stage in ProductionStage.objects.all()}

        for index, stage_id in enumerate(data.get('order', []), start=1):
            stage = stages_by_id.get(int(stage_id))
            if stage and stage.order != index:
                stage.order = index
                stage.save(update_fields=['order'])

    return JsonResponse({'status': 'ok'})


@staff_member_required
def production_stage_delete(request, production_stage_id):
    production_stage = get_object_or_404(ProductionStage, pk=production_stage_id)

    if request.method == 'POST':
        try:
            production_stage.delete()
            messages.success(request, 'Production stage deleted.')
        except ProtectedError:
            messages.warning(request, 'This production stage cannot be deleted because it is used by one or more templates.')
        return redirect('erp:production_stage_list')

    ctx = {
        'production_stage': production_stage,
    }

    return render(request, 'erp/production_stage_delete.html', ctx)


@staff_member_required
def production_stage_template_reorder(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        templates_by_id = {t.pk: t for t in ProductionStageTemplate.objects.all()}
        for index, template_id in enumerate(data.get('order', []), start=1):
            template = templates_by_id.get(int(template_id))
            if template and template.order != index:
                template.order = index
                template.save(update_fields=['order'])
    return JsonResponse({'status': 'ok'})


@staff_member_required
def production_stage_template_list(request):
    templates = ProductionStageTemplate.objects.all()

    if request.method == 'POST':
        form = ProductionStageTemplateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Template added.')
            return redirect('erp:production_stage_template_list')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = ProductionStageTemplateForm()

    ctx = {
        'templates': templates,
        'form': form,
    }

    return render(request, 'erp/production_stage_template_list.html', ctx)


@staff_member_required
def production_stage_template_edit(request, template_id):
    template = get_object_or_404(ProductionStageTemplate, pk=template_id)

    if request.method == 'POST':
        form = ProductionStageTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, 'Template updated.')
            return redirect('erp:production_stage_template_edit', template_id=template.pk)
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = ProductionStageTemplateForm(instance=template)

    ctx = {
        'form': form,
        'template': template,
        'steps': template.steps.select_related('production_stage'),
        'step_form': ProductionStageTemplateStepForm(),
    }

    return render(request, 'erp/production_stage_template_edit.html', ctx)


@staff_member_required
def production_stage_template_delete(request, template_id):
    template = get_object_or_404(ProductionStageTemplate, pk=template_id)

    if request.method == 'POST':
        template.delete()
        messages.success(request, 'Template deleted.')
        return redirect('erp:production_stage_template_list')

    ctx = {
        'template': template,
    }

    return render(request, 'erp/production_stage_template_delete.html', ctx)


@staff_member_required
def production_stage_template_step_add(request, template_id):
    template = get_object_or_404(ProductionStageTemplate, pk=template_id)

    if request.method == 'POST':
        form = ProductionStageTemplateStepForm(request.POST)
        if form.is_valid():
            last_step = template.steps.order_by('-order').first()
            next_order = (last_step.order + 1) if last_step else 1

            step = form.save(commit=False)
            step.template = template
            step.order = next_order
            step.save()
            messages.success(request, 'Step added.')
        else:
            messages.warning(request, 'Please select a production stage to add.')

    return redirect('erp:production_stage_template_edit', template_id=template.pk)


@staff_member_required
def production_stage_template_step_delete(request, step_id):
    step = get_object_or_404(ProductionStageTemplateStep, pk=step_id)
    template_id = step.template_id

    if request.method == 'POST':
        step.delete()
        messages.success(request, 'Step removed.')

    return redirect('erp:production_stage_template_edit', template_id=template_id)


@staff_member_required
def production_stage_template_step_reorder(request, template_id):
    template = get_object_or_404(ProductionStageTemplate, pk=template_id)

    if request.method == 'POST':
        data = json.loads(request.body)
        steps_by_id = {step.pk: step for step in template.steps.all()}

        for index, step_id in enumerate(data.get('order', []), start=1):
            step = steps_by_id.get(int(step_id))
            if step and step.order != index:
                step.order = index
                step.save(update_fields=['order'])

    return JsonResponse({'status': 'ok'})


# --- Location views ---

def _build_location_tree(all_locations, parent_id=None, depth=0):
    """Return a flat list of (location, depth) tuples in depth-first tree order."""
    result = []
    for loc in all_locations:
        if loc.parent_id == parent_id:
            result.append((loc, depth))
            result.extend(_build_location_tree(all_locations, loc.pk, depth + 1))
    return result


@staff_member_required
def location_list(request):
    all_locations = list(Location.objects.select_related('parent').all())
    tree = _build_location_tree(all_locations)
    ctx = {'tree': tree}
    return render(request, 'erp/location_list.html', ctx)


@staff_member_required
def location_add(request):
    initial = {}
    parent_id = request.GET.get('parent')
    if parent_id:
        initial['parent'] = parent_id

    if request.method == 'POST':
        form = LocationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Location added.')
            return redirect('erp:location_list')
        messages.warning(request, 'Please correct the errors below.')
    else:
        form = LocationForm(initial=initial)

    ctx = {'form': form}
    return render(request, 'erp/location_edit.html', ctx)


@staff_member_required
def location_edit(request, location_id):
    location = get_object_or_404(Location, pk=location_id)

    if request.method == 'POST':
        form = LocationForm(request.POST, instance=location, exclude_pk=location.pk)
        if form.is_valid():
            form.save()
            messages.success(request, 'Location updated.')
            return redirect('erp:location_list')
        messages.warning(request, 'Please correct the errors below.')
    else:
        form = LocationForm(instance=location, exclude_pk=location.pk)

    ctx = {'form': form, 'location': location}
    return render(request, 'erp/location_edit.html', ctx)


@staff_member_required
def location_delete(request, location_id):
    location = get_object_or_404(Location, pk=location_id)
    child_count = location.children.count()

    if request.method == 'POST':
        location.delete()
        messages.success(request, 'Location deleted.')
        return redirect('erp:location_list')

    ctx = {'location': location, 'child_count': child_count}
    return render(request, 'erp/location_delete.html', ctx)


# --- Part views ---

@staff_member_required
def part_list(request):
    q = request.GET.get('q', '').strip()
    parts_qs = Part.objects.order_by('name')
    if q:
        q_filter = Q(name__icontains=q) | Q(value__icontains=q) | Q(package__icontains=q) | Q(device__icontains=q)
        parts_qs = parts_qs.filter(q_filter)
        category_filter = Q(parts__in=Part.objects.filter(q_filter))
    else:
        category_filter = Q(parts__isnull=False)

    uncategorised = list(parts_qs.filter(category__isnull=True))
    categories_with_parts = (
        PartCategory.objects
        .filter(category_filter)
        .prefetch_related(Prefetch('parts', queryset=parts_qs))
        .distinct()
        .order_by('order', 'name')
    )
    ctx = {
        'uncategorised': uncategorised,
        'categories_with_parts': categories_with_parts,
        'q': q,
    }
    return render(request, 'erp/part_list.html', ctx)


@staff_member_required
def part_import_bom(request):
    if request.method != 'POST':
        return redirect('erp:part_list')

    csv_file = request.FILES.get('csv_file')
    if not csv_file:
        messages.warning(request, 'No file was uploaded.')
        return redirect('erp:part_list')

    try:
        content = csv_file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content))

        added = 0
        skipped = 0

        for row in reader:
            device = (row.get('device') or '').strip()
            package = (row.get('package') or '').strip()
            value = (row.get('value') or '').strip()
            library = (row.get('library') or '').strip()

            if Part.objects.filter(device__iexact=device, package__iexact=package, value__iexact=value).exists():
                skipped += 1
                continue

            name = ' '.join(p for p in [value, package, device.capitalize()] if p) or 'Unnamed Part'
            Part.objects.create(name=name, device=device, package=package, value=value, fusion_library=library)
            added += 1

        messages.success(
            request,
            f'BOM import complete: {added} part{"s" if added != 1 else ""} added, '
            f'{skipped} duplicate{"s" if skipped != 1 else ""} skipped.',
        )
    except Exception as e:
        messages.warning(request, f'Error reading CSV: {e}')

    return redirect('erp:part_list')


@staff_member_required
def part_add(request):
    if request.method == 'POST':
        form = PartForm(request.POST, request.FILES)
        if form.is_valid():
            part = form.save()
            messages.success(request, 'Part added.')
            return redirect('erp:part_edit', part_id=part.pk)
        messages.warning(request, 'Please correct the errors below.')
    else:
        form = PartForm()

    ctx = {'form': form}
    return render(request, 'erp/part_edit.html', ctx)


@staff_member_required
def part_edit(request, part_id):
    part = get_object_or_404(Part, pk=part_id)

    if request.method == 'POST':
        form = PartForm(request.POST, request.FILES, instance=part)
        if form.is_valid():
            form.save()
            messages.success(request, 'Part updated.')
            return redirect('erp:part_list')
        messages.warning(request, 'Please correct the errors below.')
    else:
        form = PartForm(instance=part)

    ctx = {
        'form': form,
        'part': part,
        'source_form': PartSourceForm(),
        'asset_form': PartAssetForm(),
    }
    return render(request, 'erp/part_edit.html', ctx)


@staff_member_required
def part_delete(request, part_id):
    part = get_object_or_404(Part, pk=part_id)

    if request.method == 'POST':
        if part.image:
            part.image.delete(save=False)
        part.delete()
        messages.success(request, 'Part deleted.')
        return redirect('erp:part_list')

    ctx = {'part': part}
    return render(request, 'erp/part_delete.html', ctx)


@staff_member_required
def part_asset_add(request, part_id):
    part = get_object_or_404(Part, pk=part_id)

    if request.method == 'POST':
        form = PartAssetForm(request.POST, request.FILES)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.part = part
            asset.save()
            messages.success(request, 'Attachment added.')
        else:
            messages.warning(request, 'Please correct the errors below.')

    return redirect('erp:part_edit', part_id=part.pk)


@staff_member_required
def part_asset_delete(request, asset_id):
    asset = get_object_or_404(PartAsset, pk=asset_id)
    part_id = asset.part_id

    if request.method == 'POST':
        asset.file.delete(save=False)
        asset.delete()
        messages.success(request, 'Attachment deleted.')

    return redirect('erp:part_edit', part_id=part_id)


@staff_member_required
def part_source_add(request, part_id):
    part = get_object_or_404(Part, pk=part_id)

    if request.method == 'POST':
        form = PartSourceForm(request.POST)
        if form.is_valid():
            source = form.save(commit=False)
            source.part = part
            source.save()
            messages.success(request, 'Source added.')
        else:
            messages.warning(request, 'Please correct the errors below.')

    return redirect('erp:part_edit', part_id=part.pk)


def _digikey_base_url():
    """Return the appropriate DigiKey base URL based on DIGIKEY_CLIENT_SANDBOX."""
    sandbox = os.environ.get('DIGIKEY_CLIENT_SANDBOX', '').lower() in ('true', '1', 'yes')
    return 'https://sandbox-api.digikey.com' if sandbox else 'https://api.digikey.com'


@staff_member_required
def digikey_connect(request):
    client_id = os.environ.get('DIGIKEY_CLIENT_ID', '').strip()
    if not client_id:
        messages.warning(request, 'DIGIKEY_CLIENT_ID is not configured in .env.')
        return redirect('erp:part_list')

    callback_url = request.build_absolute_uri(reverse('erp:digikey_callback'))
    from urllib.parse import urlencode
    auth_url = _digikey_base_url() + '/v1/oauth2/authorize?' + urlencode({
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': callback_url,
    })
    return redirect(auth_url)


@staff_member_required
def digikey_callback(request):
    import time
    import requests as http_requests
    from pathlib import Path

    error = request.GET.get('error')
    if error:
        messages.warning(request, f'DigiKey authorisation denied: {error}')
        return redirect('erp:part_list')

    code = request.GET.get('code')
    if not code:
        messages.warning(request, 'No authorisation code received from DigiKey.')
        return redirect('erp:part_list')

    client_id = os.environ.get('DIGIKEY_CLIENT_ID', '').strip()
    client_secret = os.environ.get('DIGIKEY_CLIENT_SECRET', '').strip()
    storage_path = os.environ.get('DIGIKEY_STORAGE_PATH', '').strip()

    if not client_id or not client_secret or not storage_path:
        messages.warning(request, 'DigiKey credentials are not fully configured in .env.')
        return redirect('erp:part_list')

    callback_url = request.build_absolute_uri(reverse('erp:digikey_callback'))

    try:
        r = http_requests.post(
            _digikey_base_url() + '/v1/oauth2/token',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': callback_url,
            },
            timeout=15,
        )
        r.raise_for_status()
        token_json = r.json()
        token_json['expires'] = int(token_json['expires_in']) + time.time() - 60

        token_file = Path(storage_path) / 'token_storage.json'
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(json.dumps(token_json))

        messages.success(request, 'DigiKey connected successfully. You can now use the DigiKey fetch button.')
    except Exception as e:
        messages.warning(request, f'DigiKey token exchange failed: {e}')

    return redirect('erp:part_list')


@staff_member_required
def part_source_fetch_lcsc(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        sku = (data.get('sku') or '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'ok': False, 'error': 'Invalid request body'}, status=400)

    if not sku:
        return JsonResponse({'ok': False, 'error': 'No SKU provided'})

    part_id = data.get('part_id')
    part = get_object_or_404(Part, pk=part_id) if part_id else None

    try:
        import os
        import requests as http_requests
        from django.core.files.base import ContentFile
        from lcsc import LcscClient
        from lcsc.errors import LcscError

        with LcscClient() as c:
            result = c.search(sku)
        if not result.is_product:
            return JsonResponse({'ok': False, 'error': f'No product found for "{sku}"'})
        p = result.product

        image_url = None
        if part and not part.image and p.product_images:
            remote_url = p.product_images[0]
            img_resp = http_requests.get(remote_url, timeout=10)
            img_resp.raise_for_status()
            ext = os.path.splitext(remote_url)[1] or '.jpg'
            part.image.save(f'lcsc_{p.product_code}{ext}', ContentFile(img_resp.content), save=True)
            image_url = part.image.url

        lcsc_packaging = p.product_arrange or ''

        if part and not part.description and p.product_intro_en:
            part.description = p.product_intro_en
            part.save(update_fields=['description'])

        source_saved = False
        if part and not part.sources.filter(supplier_sku__iexact=sku).exists():
            PartSource.objects.create(
                part=part,
                supplier_name='LCSC',
                supplier_sku=p.product_code,
                manufacturer_sku=p.product_model or '',
                packaging=lcsc_packaging,
                url=f'https://www.lcsc.com/product-detail/{p.product_code}.html',
                stock=p.stock_number,
            )
            source_saved = True

        return JsonResponse({
            'ok': True,
            'supplier_name': 'LCSC',
            'manufacturer_sku': p.product_model or '',
            'packaging': lcsc_packaging,
            'url': f'https://www.lcsc.com/product-detail/{p.product_code}.html',
            'stock': p.stock_number,
            'image_url': image_url,
            'source_saved': source_saved,
        })
    except LcscError as e:
        return JsonResponse({'ok': False, 'error': str(e)})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Lookup failed: {e}'})


@staff_member_required
def part_source_fetch_mouser(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        sku = (data.get('sku') or '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'ok': False, 'error': 'Invalid request body'}, status=400)

    if not sku:
        return JsonResponse({'ok': False, 'error': 'No SKU provided'})

    part_id = data.get('part_id')
    part = get_object_or_404(Part, pk=part_id) if part_id else None

    try:
        import requests as http_requests
        from django.core.files.base import ContentFile

        api_key = os.environ.get('MOUSER_API_KEY', '').strip()
        if not api_key:
            return JsonResponse({'ok': False, 'error': 'MOUSER_API_KEY is not configured in .env.'})

        resp = http_requests.post(
            f'https://api.mouser.com/api/v1/search/partnumber?apiKey={api_key}',
            json={'SearchByPartRequest': {'mouserPartNumber': sku, 'partSearchOptions': ''}},
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()

        errors = result.get('Errors', [])
        if errors:
            return JsonResponse({'ok': False, 'error': f'Mouser API error: {errors[0]}'})

        parts = result.get('SearchResults', {}).get('Parts', [])
        if not parts:
            return JsonResponse({'ok': False, 'error': f'No product found for "{sku}" on Mouser'})

        p = next((x for x in parts if x.get('MouserPartNumber', '').lower() == sku.lower()), parts[0])

        mouser_pn = p.get('MouserPartNumber') or sku
        manufacturer_pn = p.get('ManufacturerPartNumber') or ''
        mouser_description = p.get('Description') or ''
        product_url = p.get('ProductDetailUrl') or ''
        image_remote_url = p.get('ImagePath') or ''

        stock_str = p.get('AvailabilityInStock') or ''
        try:
            stock = int(stock_str) if stock_str else None
        except (ValueError, TypeError):
            stock = None

        packaging = ''
        for attr in p.get('ProductAttributes', []):
            if 'packag' in (attr.get('AttributeName') or '').lower():
                packaging = attr.get('AttributeValue') or ''
                break

        if part and not part.description and mouser_description:
            part.description = mouser_description
            part.save(update_fields=['description'])

        image_url = None
        if part and not part.image and image_remote_url:
            img_resp = http_requests.get(image_remote_url, timeout=10)
            img_resp.raise_for_status()
            ext = os.path.splitext(image_remote_url)[1] or '.jpg'
            part.image.save(f'mouser_{mouser_pn.replace("/", "_")}{ext}', ContentFile(img_resp.content), save=True)
            image_url = part.image.url

        source_saved = False
        if part and not part.sources.filter(supplier_sku__iexact=sku).exists():
            PartSource.objects.create(
                part=part,
                supplier_name='Mouser',
                supplier_sku=mouser_pn,
                manufacturer_sku=manufacturer_pn,
                packaging=packaging,
                url=product_url,
                stock=stock,
            )
            source_saved = True

        return JsonResponse({
            'ok': True,
            'supplier_name': 'Mouser',
            'manufacturer_sku': manufacturer_pn,
            'packaging': packaging,
            'url': product_url,
            'stock': stock,
            'image_url': image_url,
            'source_saved': source_saved,
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Lookup failed: {e}'})


def _get_digikey_access_token():
    """
    Return a valid DigiKey access token, refreshing it if expired.
    Saves the refreshed token back to token_storage.json in the same format
    that digikey_callback uses, so the digikey-api library stays in sync.
    Raises RuntimeError if credentials are missing or the refresh request fails.
    """
    import time
    import requests as http_requests

    client_id = os.environ.get('DIGIKEY_CLIENT_ID', '').strip()
    client_secret = os.environ.get('DIGIKEY_CLIENT_SECRET', '').strip()
    storage_path = os.environ.get('DIGIKEY_STORAGE_PATH', '').strip()
    if not client_id or not client_secret:
        raise RuntimeError('DigiKey credentials are not configured in .env.')
    if not storage_path:
        raise RuntimeError('DIGIKEY_STORAGE_PATH is not configured in .env.')

    token_file = Path(storage_path) / 'token_storage.json'
    if not token_file.exists():
        raise RuntimeError('DigiKey token not found. Visit /parts/source/digikey-connect/ to authorise.')

    token_data = json.loads(token_file.read_text())

    if time.time() >= token_data.get('expires', 0):
        r = http_requests.post(
            _digikey_base_url() + '/v1/oauth2/token',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'grant_type': 'refresh_token',
                'refresh_token': token_data['refresh_token'],
                'client_id': client_id,
                'client_secret': client_secret,
            },
            timeout=15,
        )
        if r.status_code != 200:
            raise RuntimeError(
                f'Token refresh failed ({r.status_code}). '
                'Re-authorise by visiting /parts/source/digikey-connect/'
            )
        token_data = r.json()
        token_data['expires'] = int(token_data['expires_in']) + time.time() - 60
        token_file.write_text(json.dumps(token_data))

    return client_id, token_data['access_token']


@staff_member_required
def part_source_fetch_digikey(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        sku = (data.get('sku') or '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'ok': False, 'error': 'Invalid request body'}, status=400)

    if not sku:
        return JsonResponse({'ok': False, 'error': 'No SKU provided'})

    part_id = data.get('part_id')
    part = get_object_or_404(Part, pk=part_id) if part_id else None

    try:
        import requests as http_requests
        from django.core.files.base import ContentFile

        client_id, access_token = _get_digikey_access_token()

        resp = http_requests.get(
            _digikey_base_url() + f'/products/v4/search/{sku}/productdetails',
            headers={
                'Authorization': f'Bearer {access_token}',
                'X-DIGIKEY-Client-Id': client_id,
                'Accept': 'application/json',
            },
            timeout=15,
        )
        if resp.status_code in (401, 403):
            try:
                body = resp.json()
                detail = body.get('ErrorMessage') or body.get('error_description') or body.get('message') or str(body)
            except Exception:
                detail = resp.text[:300]
            return JsonResponse({'ok': False, 'error': f'DigiKey API {resp.status_code}: {detail}'})
        if resp.status_code == 404:
            return JsonResponse({'ok': False, 'error': f'No product found for "{sku}"'})
        resp.raise_for_status()
        p = resp.json()

        # v4 wraps the product in a 'Product' key; field names differ from v3
        product = p.get('Product') or p
        digi_key_pn = product.get('DigiKeyPartNumber') or sku
        manufacturer_pn = product.get('ManufacturerProductNumber') or ''
        product_url = product.get('ProductUrl') or f'https://www.digikey.com/en/products/detail/{sku}'
        quantity = product.get('QuantityAvailable')
        stock = int(quantity) if quantity is not None else None
        primary_photo = product.get('PhotoUrl')
        variations = product.get('ProductVariations', [])
        dk_packaging = ''
        for v in variations:
            if v.get('DigiKeyProductNumber', '').lower() == sku.lower():
                dk_packaging = v.get('PackageType', {}).get('Name', '')
                break

        image_url = None
        if part and not part.image and primary_photo:
            img_resp = http_requests.get(primary_photo, timeout=10)
            img_resp.raise_for_status()
            ext = os.path.splitext(primary_photo)[1] or '.jpg'
            part.image.save(f'digikey_{digi_key_pn.replace("/", "_")}{ext}', ContentFile(img_resp.content), save=True)
            image_url = part.image.url

        dk_description = (product.get('Description') or {}).get('DetailedDescription', '')
        if part and not part.description and dk_description:
            part.description = dk_description
            part.save(update_fields=['description'])

        source_saved = False
        if part and not part.sources.filter(supplier_sku__iexact=sku).exists():
            PartSource.objects.create(
                part=part,
                supplier_name='DigiKey',
                supplier_sku=digi_key_pn,
                manufacturer_sku=manufacturer_pn,
                packaging=dk_packaging,
                url=product_url,
                stock=stock,
            )
            source_saved = True

        return JsonResponse({
            'ok': True,
            'supplier_name': 'DigiKey',
            'manufacturer_sku': manufacturer_pn,
            'packaging': dk_packaging,
            'url': product_url,
            'stock': stock,
            'image_url': image_url,
            'source_saved': source_saved,
        })
    except RuntimeError as e:
        return JsonResponse({'ok': False, 'error': str(e)})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Lookup failed: {e}'})


@staff_member_required
def part_source_refresh(request, source_id):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    source = get_object_or_404(PartSource, pk=source_id)
    part = source.part
    sku = source.supplier_sku
    supplier = source.supplier_name.lower()

    try:
        import requests as http_requests
        from django.core.files.base import ContentFile

        image_remote_url = None

        if supplier == 'lcsc':
            from lcsc import LcscClient
            with LcscClient() as c:
                result = c.search(sku)
            if not result.is_product:
                return JsonResponse({'ok': False, 'error': f'No product found for "{sku}" on LCSC'})
            p = result.product
            manufacturer_sku = p.product_model or ''
            packaging = p.product_arrange or ''
            url = f'https://www.lcsc.com/product-detail/{p.product_code}.html'
            stock = p.stock_number
            supplier_description = p.product_intro_en or ''
            if p.product_images:
                image_remote_url = p.product_images[0]
            image_filename_prefix = f'lcsc_{p.product_code}'

        elif 'digikey' in supplier:
            client_id, access_token = _get_digikey_access_token()
            resp = http_requests.get(
                _digikey_base_url() + f'/products/v4/search/{sku}/productdetails',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'X-DIGIKEY-Client-Id': client_id,
                    'Accept': 'application/json',
                },
                timeout=15,
            )
            if resp.status_code in (401, 403):
                try:
                    body = resp.json()
                    detail = body.get('ErrorMessage') or body.get('error_description') or body.get('message') or str(body)
                except Exception:
                    detail = resp.text[:300]
                return JsonResponse({'ok': False, 'error': f'DigiKey API {resp.status_code}: {detail}'})
            if resp.status_code == 404:
                return JsonResponse({'ok': False, 'error': f'No product found for "{sku}" on DigiKey'})
            resp.raise_for_status()
            product = resp.json().get('Product') or resp.json()
            manufacturer_sku = product.get('ManufacturerProductNumber') or ''
            url = product.get('ProductUrl') or ''
            quantity = product.get('QuantityAvailable')
            stock = int(quantity) if quantity is not None else None
            image_remote_url = product.get('PhotoUrl')
            image_filename_prefix = f'digikey_{sku.replace("/", "_")}'
            variations = product.get('ProductVariations', [])
            packaging = ''
            for v in variations:
                if v.get('DigiKeyProductNumber', '').lower() == sku.lower():
                    packaging = v.get('PackageType', {}).get('Name', '')
                    break
            supplier_description = (product.get('Description') or {}).get('DetailedDescription', '')

        elif supplier == 'mouser':
            import requests as http_requests
            api_key = os.environ.get('MOUSER_API_KEY', '').strip()
            if not api_key:
                return JsonResponse({'ok': False, 'error': 'MOUSER_API_KEY is not configured in .env.'})
            resp = http_requests.post(
                f'https://api.mouser.com/api/v1/search/partnumber?apiKey={api_key}',
                json={'SearchByPartRequest': {'mouserPartNumber': sku, 'partSearchOptions': ''}},
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                timeout=15,
            )
            resp.raise_for_status()
            result = resp.json()
            errors = result.get('Errors', [])
            if errors:
                return JsonResponse({'ok': False, 'error': f'Mouser API error: {errors[0]}'})
            parts = result.get('SearchResults', {}).get('Parts', [])
            if not parts:
                return JsonResponse({'ok': False, 'error': f'No product found for "{sku}" on Mouser'})
            p = next((x for x in parts if x.get('MouserPartNumber', '').lower() == sku.lower()), parts[0])
            manufacturer_sku = p.get('ManufacturerPartNumber') or ''
            url = p.get('ProductDetailUrl') or ''
            stock_str = p.get('AvailabilityInStock') or ''
            try:
                stock = int(stock_str) if stock_str else None
            except (ValueError, TypeError):
                stock = None
            packaging = ''
            for attr in p.get('ProductAttributes', []):
                if 'packag' in (attr.get('AttributeName') or '').lower():
                    packaging = attr.get('AttributeValue') or ''
                    break
            supplier_description = p.get('Description') or ''
            image_remote_url = p.get('ImagePath') or ''
            image_filename_prefix = f'mouser_{sku.replace("/", "_")}'

        else:
            return JsonResponse({'ok': False, 'error': f'No API integration for supplier "{source.supplier_name}"'})

        source.manufacturer_sku = manufacturer_sku
        source.packaging = packaging
        source.url = url
        source.stock = stock
        source.save()

        if not part.description and supplier_description:
            part.description = supplier_description
            part.save(update_fields=['description'])

        if not part.image and image_remote_url:
            img_resp = http_requests.get(image_remote_url, timeout=10)
            img_resp.raise_for_status()
            ext = os.path.splitext(image_remote_url)[1] or '.jpg'
            part.image.save(f'{image_filename_prefix}{ext}', ContentFile(img_resp.content), save=True)

        return JsonResponse({'ok': True})

    except RuntimeError as e:
        return JsonResponse({'ok': False, 'error': str(e)})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Refresh failed: {e}'})


@staff_member_required
def part_source_delete(request, source_id):
    source = get_object_or_404(PartSource, pk=source_id)
    part_id = source.part_id

    if request.method == 'POST':
        source.delete()
        messages.success(request, 'Source deleted.')

    return redirect('erp:part_edit', part_id=part_id)


# --- Part Category views ---

def _build_part_category_tree(all_categories, parent_id=None, depth=0):
    """Return a flat list of (category, depth) tuples in depth-first tree order."""
    result = []
    for cat in all_categories:
        if cat.parent_id == parent_id:
            result.append((cat, depth))
            result.extend(_build_part_category_tree(all_categories, cat.pk, depth + 1))
    return result


@staff_member_required
def part_category_list(request):
    all_categories = list(PartCategory.objects.select_related('parent').all())
    tree = _build_part_category_tree(all_categories)
    ctx = {'tree': tree}
    return render(request, 'erp/part_category_list.html', ctx)


@staff_member_required
def part_category_add(request):
    initial = {}
    parent_id = request.GET.get('parent')
    if parent_id:
        initial['parent'] = parent_id

    if request.method == 'POST':
        form = PartCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Part category added.')
            return redirect('erp:part_category_list')
        messages.warning(request, 'Please correct the errors below.')
    else:
        form = PartCategoryForm(initial=initial)

    ctx = {'form': form}
    return render(request, 'erp/part_category_edit.html', ctx)


@staff_member_required
def part_category_edit(request, part_category_id):
    part_category = get_object_or_404(PartCategory, pk=part_category_id)

    if request.method == 'POST':
        form = PartCategoryForm(request.POST, instance=part_category, exclude_pk=part_category.pk)
        if form.is_valid():
            form.save()
            messages.success(request, 'Part category updated.')
            return redirect('erp:part_category_list')
        messages.warning(request, 'Please correct the errors below.')
    else:
        form = PartCategoryForm(instance=part_category, exclude_pk=part_category.pk)

    ctx = {'form': form, 'part_category': part_category}
    return render(request, 'erp/part_category_edit.html', ctx)


@staff_member_required
def part_category_delete(request, part_category_id):
    part_category = get_object_or_404(PartCategory, pk=part_category_id)
    child_count = part_category.children.count()

    if request.method == 'POST':
        part_category.delete()
        messages.success(request, 'Part category deleted.')
        return redirect('erp:part_category_list')

    ctx = {'part_category': part_category, 'child_count': child_count}
    return render(request, 'erp/part_category_delete.html', ctx)


@staff_member_required
def batch_list(request):
    pcb_top_qs = DesignAsset.objects.filter(asset_type=DesignAsset.PCB_TOP)
    batches = Batch.objects.select_related('design__client').prefetch_related(
        Prefetch('design__designasset_set', queryset=pcb_top_qs, to_attr='pcb_top_assets'),
    )

    ctx = {
        'batches': batches,
    }

    return render(request, 'erp/batch_list.html', ctx)


@staff_member_required
def batch_add(request):
    if request.method == 'POST':
        form = BatchForm(request.POST)
        apply_template_form = BatchApplyTemplateForm(request.POST)
        if form.is_valid() and apply_template_form.is_valid():
            batch = form.save()

            template = apply_template_form.cleaned_data['template']
            if template:
                _apply_template_to_batch(batch, template)

            messages.success(request, 'Batch added.')
            return redirect('erp:batch_edit', batch_id=batch.pk)
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        initial = {}
        design_id = request.GET.get('design')
        if design_id:
            initial['design'] = design_id

        form = BatchForm(initial=initial)
        apply_template_form = BatchApplyTemplateForm()

    ctx = {
        'form': form,
        'apply_template_form': apply_template_form,
        'batch': None,
    }

    return render(request, 'erp/batch_edit.html', ctx)


@staff_member_required
def batch_edit(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)

    if request.method == 'POST':
        form = BatchForm(request.POST, instance=batch)
        if form.is_valid():
            form.save()
            messages.success(request, 'Batch updated.')
            return redirect('erp:batch_edit', batch_id=batch.pk)
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = BatchForm(instance=batch)

    production_stages_with_forms = [
        (batch_production_stage, BatchProductionStageUpdateForm(instance=batch_production_stage))
        for batch_production_stage in batch.production_stages.all()
    ]

    ctx = {
        'form': form,
        'batch': batch,
        'production_stages_with_forms': production_stages_with_forms,
        'apply_template_form': BatchApplyTemplateForm(),
        'add_production_stage_form': BatchProductionStageAddForm(),
    }

    return render(request, 'erp/batch_edit.html', ctx)


@staff_member_required
def batch_delete(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)

    if request.method == 'POST':
        batch.delete()
        messages.success(request, 'Batch deleted.')
        return redirect('erp:batch_list')

    ctx = {
        'batch': batch,
    }

    return render(request, 'erp/batch_delete.html', ctx)


@staff_member_required
def batch_apply_template(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)

    if request.method == 'POST':
        form = BatchApplyTemplateForm(request.POST)
        if form.is_valid() and form.cleaned_data['template']:
            _apply_template_to_batch(batch, form.cleaned_data['template'])
            messages.success(request, 'Template applied.')
        else:
            messages.warning(request, 'Please select a template to apply.')

    return redirect('erp:batch_edit', batch_id=batch.pk)


@staff_member_required
def batch_production_stage_add(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)

    if request.method == 'POST':
        form = BatchProductionStageAddForm(request.POST)
        if form.is_valid():
            production_stage = form.cleaned_data['production_stage']
            last_stage = batch.production_stages.order_by('-order').first()
            next_order = (last_stage.order + 1) if last_stage else 1

            BatchProductionStage.objects.create(
                batch=batch,
                name=production_stage.name,
                color=production_stage.color,
                order=next_order,
                status=BatchProductionStage.NOT_STARTED,
            )
            messages.success(request, 'Production stage added.')
        else:
            messages.warning(request, 'Please select a production stage to add.')

    return redirect('erp:batch_edit', batch_id=batch.pk)


@staff_member_required
def batch_production_stage_update(request, batch_production_stage_id):
    batch_production_stage = get_object_or_404(BatchProductionStage, pk=batch_production_stage_id)

    if request.method == 'POST':
        form = BatchProductionStageUpdateForm(request.POST, instance=batch_production_stage)
        if form.is_valid():
            form.save()
            messages.success(request, 'Production stage updated.')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')

    return redirect('erp:batch_edit', batch_id=batch_production_stage.batch_id)


@staff_member_required
def batch_production_stage_set_status(request, batch_production_stage_id, status):
    batch_production_stage = get_object_or_404(BatchProductionStage, pk=batch_production_stage_id)

    if request.method != 'POST' or status not in dict(BatchProductionStage.STATUS_CHOICES):
        return JsonResponse({'status': 'error'}, status=400)

    batch_production_stage.status = status
    if status == BatchProductionStage.DONE:
        batch_production_stage.completion_date = timezone.now()
    batch_production_stage.save()

    return JsonResponse({
        'status': batch_production_stage.status,
        'table_class': batch_production_stage.get_bootstrap_table_class(),
        'completion_date': timezone.localtime(batch_production_stage.completion_date).strftime('%Y-%m-%dT%H:%M:%S') if batch_production_stage.completion_date else '',
    })


@staff_member_required
def batch_production_stage_delete(request, batch_production_stage_id):
    batch_production_stage = get_object_or_404(BatchProductionStage, pk=batch_production_stage_id)
    batch_id = batch_production_stage.batch_id

    if request.method == 'POST':
        batch_production_stage.delete()
        messages.success(request, 'Production stage removed.')

    return redirect('erp:batch_edit', batch_id=batch_id)


@staff_member_required
def batch_production_stage_reorder(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)

    if request.method == 'POST':
        data = json.loads(request.body)
        stages_by_id = {stage.pk: stage for stage in batch.production_stages.all()}

        for index, stage_id in enumerate(data.get('order', []), start=1):
            stage = stages_by_id.get(int(stage_id))
            if stage and stage.order != index:
                stage.order = index
                stage.save(update_fields=['order'])

    return JsonResponse({'status': 'ok'})

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import csv
import io
import json

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Prefetch, ProtectedError, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
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
    ProductionStageForm,
    ProductionStageTemplateForm,
    ProductionStageTemplateStepForm,
)
from device.models import DesignAsset
from .models import Batch, BatchProductionStage, Location, Part, PartAsset, PartCategory, ProductionStage, ProductionStageTemplate, ProductionStageTemplateStep


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

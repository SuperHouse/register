# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import csv
import io
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from decimal import Decimal, InvalidOperation
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
    BomEquivalenceRuleForm,
    BomExclusionRuleForm,
    BomLibrarySettingForm,
    DesignBomEntryForm,
    LocationForm,
    PartAssetForm,
    PartCategoryForm,
    PartForm,
    PartSourceForm,
    PartSubstitutionForm,
    ProductionStageForm,
    ProductionStageTemplateForm,
    ProductionStageTemplateStepForm,
)
from device.models import Design, DesignAsset
from .models import (
    Batch, BatchProductionStage, BomEquivalenceRule, BomExclusionRule, BomLibrarySetting, DesignBomEntry, Location,
    Part, PartAsset, PartCategory, PartPriceBreak, PartSource, PartSourceVariant, PartSubstitution, ProductionStage,
    ProductionStageTemplate, ProductionStageTemplateStep,
)


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
    parts_qs = Part.objects.prefetch_related('sources__variants').order_by('name')
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


def _bom_field_matches(rule_value, row_value):
    """A blank rule field matches anything; otherwise compare case-insensitively."""
    return not rule_value or rule_value.strip().lower() == row_value.strip().lower()


def _bom_row_is_excluded(exclusion_rules, library, device, package, value):
    return any(
        _bom_field_matches(rule.library, library)
        and _bom_field_matches(rule.device, device)
        and _bom_field_matches(rule.package, package)
        and _bom_field_matches(rule.value, value)
        for rule in exclusion_rules
    )


def _bom_apply_equivalence(equivalence_rules, library, device, package, value):
    """Return (library, device, package, value) after applying the first matching equivalence rule, if any."""
    for rule in equivalence_rules:
        if (
            _bom_field_matches(rule.from_library, library)
            and _bom_field_matches(rule.from_device, device)
            and _bom_field_matches(rule.from_package, package)
            and _bom_field_matches(rule.from_value, value)
        ):
            return (
                rule.to_library or library,
                rule.to_device or device,
                rule.to_package or package,
                rule.to_value or value,
            )
    return library, device, package, value


def _resolve_bom_csv_row(row, exclusion_rules, equivalence_rules, library_settings_by_name):
    """Apply BOM import rules to one CSV row.

    Returns (reference, part, created) or None if the row is excluded. Shared by the Parts
    library CSV import (part_import_bom) and the per-design BOM import (design_bom_populate) —
    both consume the same reference/device/package/value/library CSV column format.
    """
    reference = (row.get('reference') or '').strip()
    device = (row.get('device') or '').strip()
    package = (row.get('package') or '').strip()
    value = (row.get('value') or '').strip()
    library = (row.get('library') or '').strip()

    if _bom_row_is_excluded(exclusion_rules, library, device, package, value):
        return None

    library, device, package, value = _bom_apply_equivalence(equivalence_rules, library, device, package, value)

    library_setting = library_settings_by_name.get(library.lower())
    if library_setting:
        if library_setting.ignore_device:
            device = ''
        if library_setting.ignore_package:
            package = ''
        if library_setting.ignore_value:
            value = ''

    part = Part.objects.filter(device__iexact=device, package__iexact=package, value__iexact=value).first()
    created = False
    if not part:
        name = ' '.join(p for p in [value, package, device.capitalize()] if p) or 'Unnamed Part'
        part = Part.objects.create(name=name, device=device, package=package, value=value, fusion_library=library)
        created = True

    return reference, part, created


_BRD_ROT_RE = re.compile(r'^(M)?R(-?\d+(?:\.\d+)?)$')


def _parse_brd_placements(brd_path):
    """Parse an EAGLE .brd file into {reference designator: {pos_x, pos_y, rotation, side}}.

    Reference designators (the <element name="..."> attribute) match the BOM CSV's `reference`
    column exactly, since both are generated from the same Fusion Electronics board for a given
    design — so it's used as the join key rather than library/device/package/value, which don't
    line up consistently between the two exports.
    """
    placements = {}
    try:
        elements = ET.parse(brd_path).find('drawing/board/elements')
    except ET.ParseError:
        return placements
    if elements is None:
        return placements

    for element in elements.findall('element'):
        reference = element.get('name')
        if not reference:
            continue
        match = _BRD_ROT_RE.match(element.get('rot', 'R0'))
        try:
            placements[reference] = {
                'pos_x': Decimal(element.get('x', '0')),
                'pos_y': Decimal(element.get('y', '0')),
                'rotation': Decimal(match.group(2)) if match else Decimal('0'),
                'side': DesignBomEntry.BOTTOM if match and match.group(1) else DesignBomEntry.TOP,
            }
        except InvalidOperation:
            continue
    return placements


def _apply_brd_placements(design):
    """Backfill pos_x/pos_y/rotation/side on a design's BOM entries from its PCB Design File asset.

    Returns the number of entries updated, or None if the design has no PCB Design File asset.
    """
    brd_asset = design.designasset_set.filter(asset_type=DesignAsset.PCB_DESIGN).first()
    if not brd_asset:
        return None

    placements = _parse_brd_placements(brd_asset.file.path)
    entries_to_update = []
    for entry in design.bom_entries.all():
        placement = placements.get(entry.reference)
        if not placement:
            continue
        entry.pos_x = placement['pos_x']
        entry.pos_y = placement['pos_y']
        entry.rotation = placement['rotation']
        entry.side = placement['side']
        entries_to_update.append(entry)

    if entries_to_update:
        DesignBomEntry.objects.bulk_update(entries_to_update, ['pos_x', 'pos_y', 'rotation', 'side'])
    return len(entries_to_update)


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

        exclusion_rules = list(BomExclusionRule.objects.all())
        equivalence_rules = list(BomEquivalenceRule.objects.all())
        library_settings_by_name = {
            ls.library.lower(): ls for ls in BomLibrarySetting.objects.all()
        }

        added = 0
        skipped = 0
        excluded = 0

        for row in reader:
            resolved = _resolve_bom_csv_row(row, exclusion_rules, equivalence_rules, library_settings_by_name)
            if resolved is None:
                excluded += 1
                continue

            _reference, _part, created = resolved
            if created:
                added += 1
            else:
                skipped += 1

        messages.success(
            request,
            f'BOM import complete: {added} part{"s" if added != 1 else ""} added, '
            f'{skipped} duplicate{"s" if skipped != 1 else ""} skipped, '
            f'{excluded} excluded by rule{"s" if excluded != 1 else ""}.',
        )
    except Exception as e:
        messages.warning(request, f'Error reading CSV: {e}')

    return redirect('erp:part_list')


@staff_member_required
def design_bom_populate(request, design_id):
    """Seed a design's BOM entries from its uploaded BOM CSV DesignAsset.

    Safe to run more than once: rows whose reference designator is already present on the
    design are skipped, so re-running after manual edits never overwrites or duplicates them.
    Also backfills pos_x/pos_y/rotation/side on every entry (new and pre-existing) from the
    design's PCB Design File asset, if one is attached — see _apply_brd_placements().
    """
    design = get_object_or_404(Design, pk=design_id)

    if request.method == 'POST':
        bom_asset = design.designasset_set.filter(asset_type=DesignAsset.BOM).first()
        if not bom_asset:
            messages.warning(request, 'This design has no BOM CSV uploaded to populate from.')
        else:
            try:
                content = bom_asset.file.read().decode('utf-8-sig')
                reader = csv.DictReader(io.StringIO(content))

                exclusion_rules = list(BomExclusionRule.objects.all())
                equivalence_rules = list(BomEquivalenceRule.objects.all())
                library_settings_by_name = {
                    ls.library.lower(): ls for ls in BomLibrarySetting.objects.all()
                }
                existing_references = set(design.bom_entries.values_list('reference', flat=True))

                added = 0
                skipped = 0
                excluded = 0
                new_parts = 0

                for row in reader:
                    resolved = _resolve_bom_csv_row(row, exclusion_rules, equivalence_rules, library_settings_by_name)
                    if resolved is None:
                        excluded += 1
                        continue

                    reference, part, created = resolved
                    if created:
                        new_parts += 1
                    if not reference or reference in existing_references:
                        skipped += 1
                        continue

                    DesignBomEntry.objects.create(design=design, part=part, reference=reference)
                    existing_references.add(reference)
                    added += 1

                positions_updated = _apply_brd_placements(design)
                position_msg = (
                    f' {positions_updated} position{"s" if positions_updated != 1 else ""} updated'
                    f' from PCB design file.' if positions_updated is not None else ''
                )
                new_parts_msg = (
                    f' {new_parts} new part{"s" if new_parts != 1 else ""} created in the Parts library.'
                    if new_parts else ''
                )

                messages.success(
                    request,
                    f'BOM populated: {added} entr{"y" if added == 1 else "ies"} added, '
                    f'{skipped} skipped (already present), '
                    f'{excluded} excluded by rule{"s" if excluded != 1 else ""}.{new_parts_msg}{position_msg}',
                )
            except Exception as e:
                messages.warning(request, f'Error reading CSV: {e}')

    return redirect('design_detail', design_id=design.pk)


@staff_member_required
def design_bom_entry_add(request, design_id):
    design = get_object_or_404(Design, pk=design_id)

    if request.method == 'POST':
        form = DesignBomEntryForm(request.POST)
        form.instance.design = design
        if form.is_valid():
            form.save()
            messages.success(request, 'BOM entry added.')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')

    return redirect('design_detail', design_id=design.pk)


@staff_member_required
def design_bom_entry_edit(request, entry_id):
    entry = get_object_or_404(DesignBomEntry, pk=entry_id)

    if request.method == 'POST':
        form = DesignBomEntryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, 'BOM entry updated.')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')

    return redirect('design_detail', design_id=entry.design_id)


@staff_member_required
def design_bom_entry_delete(request, entry_id):
    entry = get_object_or_404(DesignBomEntry, pk=entry_id)
    design_id = entry.design_id

    if request.method == 'POST':
        entry.delete()
        messages.success(request, 'BOM entry deleted.')

    return redirect('design_detail', design_id=design_id)


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
    part = get_object_or_404(
        Part.objects.prefetch_related('substitutions__substitute', 'sources__variants__price_breaks'),
        pk=part_id,
    )

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
        'substitution_form': PartSubstitutionForm(exclude_pk=part.pk),
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


def _get_or_create_supplier_listing(part, supplier_name, manufacturer_sku, stock):
    """Find or create the PartSource listing a new variant should be filed under.

    Only merges into an existing listing when manufacturer_sku is non-blank — supplier
    lookups that fail to report a manufacturer SKU would otherwise all match each other
    on the empty string and wrongly merge unrelated listings (and their stock).
    """
    if manufacturer_sku:
        listing = PartSource.objects.filter(
            part=part, supplier_name__iexact=supplier_name, manufacturer_sku__iexact=manufacturer_sku,
        ).first()
        if listing:
            listing.stock = stock
            listing.save(update_fields=['stock'])
            return listing

    return PartSource.objects.create(
        part=part, supplier_name=supplier_name, manufacturer_sku=manufacturer_sku, stock=stock,
    )


@staff_member_required
def part_source_add(request, part_id):
    part = get_object_or_404(Part, pk=part_id)

    if request.method == 'POST':
        form = PartSourceForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            listing = _get_or_create_supplier_listing(
                part, data['supplier_name'], data['manufacturer_sku'], data['stock'],
            )
            PartSourceVariant.objects.create(
                source=listing, supplier_sku=data['supplier_sku'], packaging=data['packaging'], url=data['url'],
                moq=data['moq'],
            )
            messages.success(request, 'Source added.')
        else:
            messages.warning(request, 'Please correct the errors below.')

    return redirect('erp:part_edit', part_id=part.pk)


_LCSC_HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.lcsc.com',
    'referer': 'https://www.lcsc.com/',
    'user-agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
}


def _lcsc_search(sku):
    """Look up a part by SKU on LCSC's unofficial JSON API.

    Replicates the relevant slice of the `lcsc` PyPI client's behaviour directly via
    `requests`, since that package requires Python >=3.13. Returns a dict with
    product_code/product_model/product_arrange/stock_number/product_intro_en/
    product_images, or None if no matching product was found.
    """
    import re

    import requests as http_requests

    body = {
        'keyword': sku,
        'secondKeyword': '',
        'brandIdList': [],
        'catalogIdList': [],
        'isStock': False,
        'isAsianBrand': False,
        'isDeals': False,
        'isEnvironment': False,
    }
    resp = http_requests.post(
        'https://wmsc.lcsc.com/ftps/wm/search/v3/global',
        json=body, headers=_LCSC_HEADERS, timeout=15,
    )
    resp.raise_for_status()
    envelope = resp.json()
    if envelope.get('code') != 200:
        raise RuntimeError(envelope.get('msg') or f'LCSC API error {envelope.get("code")}')
    result = envelope.get('result') or {}
    scene = result.get('scene')

    product = None
    if scene == 'FULL_MATCH' and result.get('exactMatchResult'):
        product = result['exactMatchResult'][0]
    elif scene == 'REDIRECT_PRODUCT_DETAIL' and result.get('tipProductDetailUrlVO'):
        tip = result['tipProductDetailUrlVO']
        detail_resp = http_requests.get(
            f'https://www.lcsc.com/product-detail/{tip["productCode"]}.html',
            headers={**_LCSC_HEADERS, 'accept': 'text/html'}, timeout=15,
        )
        detail_resp.raise_for_status()
        match = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', detail_resp.text, re.DOTALL,
        )
        page_props = json.loads(match.group(1)).get('props', {}).get('pageProps', {}) if match else {}
        if page_props.get('webData') and not page_props.get('dataIsNull'):
            product = page_props['webData']
        else:
            product = tip

    if product is None:
        return None

    price_breaks = []
    for item in (product.get('productPriceList') or []):
        qty = item.get('ladder')
        price = item.get('discountPrice')
        if qty is not None and price is not None:
            # LCSC's API only ever returns a "$" symbol, not an ISO code, so the
            # currency is assumed to be USD here like every other supplier.
            price_breaks.append({'quantity': qty, 'price': price, 'currency': 'USD'})

    return {
        'product_code': product.get('productCode', ''),
        'product_model': product.get('productModel') or '',
        'product_arrange': product.get('productArrange') or '',
        'stock_number': product.get('stockNumber') or 0,
        'product_intro_en': product.get('productIntroEn') or '',
        'product_images': product.get('productImages') or [],
        'price_breaks': price_breaks,
        'moq': product.get('minBuyNumber'),
    }


def _save_price_breaks(variant, price_breaks):
    """Replace all price breaks for a variant with the supplied list."""
    variant.price_breaks.all().delete()
    for pb in price_breaks:
        qty = pb.get('quantity')
        price = pb.get('price')
        if qty and price is not None:
            PartPriceBreak.objects.create(
                variant=variant,
                quantity=qty,
                price=price,
                currency=pb.get('currency') or 'USD',
            )


def _digikey_base_url():
    """Return the appropriate DigiKey base URL based on DIGIKEY_CLIENT_SANDBOX."""
    sandbox = os.environ.get('DIGIKEY_CLIENT_SANDBOX', '').lower() in ('true', '1', 'yes')
    return 'https://sandbox-api.digikey.com' if sandbox else 'https://api.digikey.com'


def _digikey_price_breaks(variation):
    """Extract price breaks from a DigiKey ProductVariation's StandardPricing list."""
    price_breaks = []
    for tier in (variation.get('StandardPricing') or []):
        qty = tier.get('BreakQuantity')
        price = tier.get('UnitPrice')
        if qty is not None and price is not None:
            price_breaks.append({'quantity': qty, 'price': price, 'currency': 'USD'})
    return price_breaks


def _mouser_price_breaks(p):
    """Extract price breaks from a Mouser Part's PriceBreaks list.

    Unlike DigiKey/LCSC, Mouser's Price field is a string with a currency
    symbol prefix (e.g. "$0.3600"), so it needs stripping before storage.
    """
    import re
    price_breaks = []
    for pb in (p.get('PriceBreaks') or []):
        qty = pb.get('Quantity')
        price = re.sub(r'[^\d.]', '', pb.get('Price') or '')
        if qty is not None and price:
            price_breaks.append({'quantity': qty, 'price': price, 'currency': pb.get('Currency') or 'USD'})
    return price_breaks


def _propagate_digikey_sibling_data(listing, variations):
    """Save price breaks and MOQ for every PartSourceVariant under listing found in variations.

    DigiKey's productdetails response includes every packaging variation's pricing and
    MOQ (not just the one that was looked up) in a single call, so one fetch or refresh
    can backfill this data for sibling SKUs under the same listing too.
    """
    by_digikey_pn = {v.get('DigiKeyProductNumber', '').lower(): v for v in variations}
    for sibling in listing.variants.all():
        variation = by_digikey_pn.get(sibling.supplier_sku.lower())
        if variation is not None:
            _save_price_breaks(sibling, _digikey_price_breaks(variation))
            sibling.moq = variation.get('MinimumOrderQuantity')
            sibling.save(update_fields=['moq'])


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

        p = _lcsc_search(sku)
        if p is None:
            return JsonResponse({'ok': False, 'error': f'No product found for "{sku}"'})

        image_url = None
        if part and not part.image and p['product_images']:
            remote_url = p['product_images'][0]
            img_resp = http_requests.get(remote_url, timeout=10)
            img_resp.raise_for_status()
            ext = os.path.splitext(remote_url)[1] or '.jpg'
            part.image.save(f'lcsc_{p["product_code"]}{ext}', ContentFile(img_resp.content), save=True)
            image_url = part.image.url

        lcsc_packaging = p['product_arrange']

        if part and not part.description and p['product_intro_en']:
            part.description = p['product_intro_en']
            part.save(update_fields=['description'])

        source_saved = False
        if part and not PartSourceVariant.objects.filter(source__part=part, supplier_sku__iexact=sku).exists():
            listing = _get_or_create_supplier_listing(part, 'LCSC', p['product_model'], p['stock_number'])
            variant = PartSourceVariant.objects.create(
                source=listing,
                supplier_sku=p['product_code'],
                packaging=lcsc_packaging,
                url=f'https://www.lcsc.com/product-detail/{p["product_code"]}.html',
                moq=p['moq'],
                last_refreshed=timezone.now(),
            )
            _save_price_breaks(variant, p['price_breaks'])
            source_saved = True

        return JsonResponse({
            'ok': True,
            'supplier_name': 'LCSC',
            'manufacturer_sku': p['product_model'],
            'packaging': lcsc_packaging,
            'url': f'https://www.lcsc.com/product-detail/{p["product_code"]}.html',
            'stock': p['stock_number'],
            'moq': p['moq'],
            'image_url': image_url,
            'source_saved': source_saved,
        })
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

        moq_str = p.get('Min') or ''
        try:
            moq = int(moq_str) if moq_str else None
        except (ValueError, TypeError):
            moq = None

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
        if part and not PartSourceVariant.objects.filter(source__part=part, supplier_sku__iexact=sku).exists():
            listing = _get_or_create_supplier_listing(part, 'Mouser', manufacturer_pn, stock)
            variant = PartSourceVariant.objects.create(
                source=listing, supplier_sku=mouser_pn, packaging=packaging, url=product_url, moq=moq,
                last_refreshed=timezone.now(),
            )
            _save_price_breaks(variant, _mouser_price_breaks(p))
            source_saved = True

        return JsonResponse({
            'ok': True,
            'supplier_name': 'Mouser',
            'manufacturer_sku': manufacturer_pn,
            'packaging': packaging,
            'url': product_url,
            'stock': stock,
            'moq': moq,
            'image_url': image_url,
            'source_saved': source_saved,
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Lookup failed: {e}'})


@staff_member_required
def part_source_fetch_element14(request):
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

        api_key = os.environ.get('ELEMENT14_API_KEY', '').strip()
        store_id = os.environ.get('ELEMENT14_STORE_ID', 'au.element14.com').strip()
        if not api_key:
            return JsonResponse({'ok': False, 'error': 'ELEMENT14_API_KEY is not configured in .env.'})

        resp = http_requests.get(
            'https://api.element14.com/catalog/products',
            params={
                'term': f'sku:{sku}',
                'storeInfo.id': store_id,
                'resultsSettings.offset': 0,
                'resultsSettings.numberOfResults': 1,
                'resultsSettings.responseGroup': 'large',
                'callInfo.responseDataFormat': 'json',
                'id': api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()

        products = result.get('keywordSearchReturn', {}).get('products', [])
        if not products:
            return JsonResponse({'ok': False, 'error': f'No product found for "{sku}" on Element14'})

        p = products[0]
        element14_sku = p.get('sku') or sku

        mfr_pns = p.get('manufacturerPartNumberList') or []
        manufacturer_pn = str(mfr_pns[0]) if isinstance(mfr_pns, list) and mfr_pns else ''

        element14_description = p.get('description') or ''

        stock = p.get('stock')
        try:
            stock = int(stock) if stock is not None else None
        except (ValueError, TypeError):
            stock = None

        packaging = ''
        for attr in (p.get('attributes') or []):
            if 'packag' in (attr.get('attributeLabel') or '').lower():
                packaging = attr.get('attributeValue') or ''
                break
        if not packaging:
            pack_size = p.get('packSize')
            if pack_size and int(pack_size) > 1:
                packaging = f'Pack of {pack_size}'

        image_remote_url = ''
        image_list = (p.get('imageList') or {}).get('image') or []
        if image_list:
            raw_url = image_list[0].get('url') or ''
            if raw_url.startswith('//'):
                raw_url = 'https:' + raw_url
            image_remote_url = raw_url

        product_url = p.get('productDetailUrl') or ''

        if part and not part.description and element14_description:
            part.description = element14_description
            part.save(update_fields=['description'])

        image_url = None
        if part and not part.image and image_remote_url:
            img_resp = http_requests.get(image_remote_url, timeout=10)
            img_resp.raise_for_status()
            ext = os.path.splitext(image_remote_url.split('?')[0])[1] or '.jpg'
            part.image.save(f'element14_{element14_sku}{ext}', ContentFile(img_resp.content), save=True)
            image_url = part.image.url

        source_saved = False
        if part and not PartSourceVariant.objects.filter(source__part=part, supplier_sku__iexact=sku).exists():
            listing = _get_or_create_supplier_listing(part, 'Element14', manufacturer_pn, stock)
            PartSourceVariant.objects.create(
                source=listing, supplier_sku=element14_sku, packaging=packaging, url=product_url,
                last_refreshed=timezone.now(),
            )
            source_saved = True

        return JsonResponse({
            'ok': True,
            'supplier_name': 'Element14',
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
            try:
                body = r.json()
                detail = body.get('ErrorMessage') or body.get('error_description') or body.get('error') or str(body)
            except Exception:
                detail = r.text[:300]
            raise RuntimeError(
                f'Token refresh failed ({r.status_code}): {detail}. '
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
        listing = None
        if part:
            if not PartSourceVariant.objects.filter(source__part=part, supplier_sku__iexact=sku).exists():
                listing = _get_or_create_supplier_listing(part, 'DigiKey', manufacturer_pn, stock)
                PartSourceVariant.objects.create(
                    source=listing, supplier_sku=digi_key_pn, packaging=dk_packaging, url=product_url,
                    last_refreshed=timezone.now(),
                )
                source_saved = True
            else:
                listing = PartSource.objects.filter(
                    part=part, supplier_name__iexact='DigiKey', manufacturer_sku__iexact=manufacturer_pn,
                ).first()

            if listing:
                _propagate_digikey_sibling_data(listing, variations)

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


def _refresh_variant(variant):
    """Re-fetch pricing/stock/MOQ for one PartSourceVariant from its supplier's API.

    Shared by the manual refresh view and the scheduled refresh_part_sources
    management command. Returns {'ok': True} or {'ok': False, 'error': '...'}.
    """
    listing = variant.source
    part = listing.part
    sku = variant.supplier_sku
    supplier = listing.supplier_name.lower()

    try:
        import requests as http_requests
        from django.core.files.base import ContentFile

        image_remote_url = None
        moq = None

        if supplier == 'lcsc':
            p = _lcsc_search(sku)
            if p is None:
                return {'ok': False, 'error': f'No product found for "{sku}" on LCSC'}
            manufacturer_sku = p['product_model']
            packaging = p['product_arrange']
            url = f'https://www.lcsc.com/product-detail/{p["product_code"]}.html'
            stock = p['stock_number']
            moq = p['moq']
            supplier_description = p['product_intro_en']
            if p['product_images']:
                image_remote_url = p['product_images'][0]
            image_filename_prefix = f'lcsc_{p["product_code"]}'
            _save_price_breaks(variant, p['price_breaks'])

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
                return {'ok': False, 'error': f'DigiKey API {resp.status_code}: {detail}'}
            if resp.status_code == 404:
                return {'ok': False, 'error': f'No product found for "{sku}" on DigiKey'}
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
            _propagate_digikey_sibling_data(listing, variations)

        elif supplier == 'mouser':
            import requests as http_requests
            api_key = os.environ.get('MOUSER_API_KEY', '').strip()
            if not api_key:
                return {'ok': False, 'error': 'MOUSER_API_KEY is not configured in .env.'}
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
                return {'ok': False, 'error': f'Mouser API error: {errors[0]}'}
            parts = result.get('SearchResults', {}).get('Parts', [])
            if not parts:
                return {'ok': False, 'error': f'No product found for "{sku}" on Mouser'}
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
            moq_str = p.get('Min') or ''
            try:
                moq = int(moq_str) if moq_str else None
            except (ValueError, TypeError):
                moq = None
            supplier_description = p.get('Description') or ''
            image_remote_url = p.get('ImagePath') or ''
            image_filename_prefix = f'mouser_{sku.replace("/", "_")}'
            _save_price_breaks(variant, _mouser_price_breaks(p))

        elif 'element14' in supplier or 'farnell' in supplier or 'newark' in supplier:
            api_key = os.environ.get('ELEMENT14_API_KEY', '').strip()
            store_id = os.environ.get('ELEMENT14_STORE_ID', 'au.element14.com').strip()
            if not api_key:
                return {'ok': False, 'error': 'ELEMENT14_API_KEY is not configured in .env.'}
            resp = http_requests.get(
                'https://api.element14.com/catalog/products',
                params={
                    'term': f'sku:{sku}',
                    'storeInfo.id': store_id,
                    'resultsSettings.offset': 0,
                    'resultsSettings.numberOfResults': 1,
                    'resultsSettings.responseGroup': 'large',
                    'callInfo.responseDataFormat': 'json',
                    'id': api_key,
                },
                timeout=15,
            )
            resp.raise_for_status()
            result = resp.json()
            products = result.get('keywordSearchReturn', {}).get('products', [])
            if not products:
                return {'ok': False, 'error': f'No product found for "{sku}" on Element14'}
            p = products[0]
            mfr_pns = p.get('manufacturerPartNumberList') or []
            manufacturer_sku = str(mfr_pns[0]) if isinstance(mfr_pns, list) and mfr_pns else ''
            url = p.get('productDetailUrl') or ''
            stock_raw = p.get('stock')
            try:
                stock = int(stock_raw) if stock_raw is not None else None
            except (ValueError, TypeError):
                stock = None
            packaging = ''
            for attr in (p.get('attributes') or []):
                if 'packag' in (attr.get('attributeLabel') or '').lower():
                    packaging = attr.get('attributeValue') or ''
                    break
            if not packaging:
                pack_size = p.get('packSize')
                if pack_size and int(pack_size) > 1:
                    packaging = f'Pack of {pack_size}'
            supplier_description = p.get('description') or ''
            image_list = (p.get('imageList') or {}).get('image') or []
            if image_list:
                raw_url = image_list[0].get('url') or ''
                image_remote_url = ('https:' + raw_url) if raw_url.startswith('//') else raw_url
            image_filename_prefix = f'element14_{sku}'

        else:
            return {'ok': False, 'error': f'No API integration for supplier "{listing.supplier_name}"'}

        listing.manufacturer_sku = manufacturer_sku
        listing.stock = stock
        listing.save(update_fields=['manufacturer_sku', 'stock'])

        variant.packaging = packaging
        variant.url = url
        update_fields = ['packaging', 'url']
        if moq is not None:
            variant.moq = moq
            update_fields.append('moq')
        variant.save(update_fields=update_fields)

        if not part.description and supplier_description:
            part.description = supplier_description
            part.save(update_fields=['description'])

        if not part.image and image_remote_url:
            img_resp = http_requests.get(image_remote_url, timeout=10)
            img_resp.raise_for_status()
            ext = os.path.splitext(image_remote_url)[1] or '.jpg'
            part.image.save(f'{image_filename_prefix}{ext}', ContentFile(img_resp.content), save=True)

        return {'ok': True}

    except RuntimeError as e:
        return {'ok': False, 'error': str(e)}
    except Exception as e:
        return {'ok': False, 'error': f'Refresh failed: {e}'}


@staff_member_required
def part_source_refresh(request, variant_id):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    variant = get_object_or_404(PartSourceVariant, pk=variant_id)
    result = _refresh_variant(variant)
    variant.last_refreshed = timezone.now()
    variant.save(update_fields=['last_refreshed'])

    return JsonResponse(result)


@staff_member_required
def part_source_delete(request, source_id):
    source = get_object_or_404(PartSource, pk=source_id)
    part_id = source.part_id

    if request.method == 'POST':
        source.delete()
        messages.success(request, 'Source deleted.')

    return redirect('erp:part_edit', part_id=part_id)


@staff_member_required
def part_source_variant_delete(request, variant_id):
    variant = get_object_or_404(PartSourceVariant, pk=variant_id)
    listing = variant.source
    part_id = listing.part_id

    if request.method == 'POST':
        variant.delete()
        # Don't leave a listing with no orderable SKUs behind.
        if not listing.variants.exists():
            listing.delete()
        messages.success(request, 'Source deleted.')

    return redirect('erp:part_edit', part_id=part_id)


@staff_member_required
def part_substitution_add(request, part_id):
    part = get_object_or_404(Part, pk=part_id)

    if request.method == 'POST':
        form = PartSubstitutionForm(request.POST, exclude_pk=part.pk)
        if form.is_valid():
            substitution = form.save(commit=False)
            substitution.part = part
            substitution.save()
            messages.success(request, 'Substitution added.')
        else:
            messages.warning(request, 'Please correct the errors below.')

    return redirect('erp:part_edit', part_id=part.pk)


@staff_member_required
def part_substitution_delete(request, substitution_id):
    substitution = get_object_or_404(PartSubstitution, pk=substitution_id)
    part_id = substitution.part_id

    if request.method == 'POST':
        substitution.delete()
        messages.success(request, 'Substitution deleted.')

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


def _part_import_filter_context(exclusion_form=None, equivalence_form=None, library_form=None):
    """Shared context for the merged Part Import Filters page.

    Sections are ordered to match the order rules are applied in part_import_bom:
    exclusion, then equivalence, then library (ignore-value) settings.
    """
    return {
        'exclusion_rules': BomExclusionRule.objects.all(),
        'exclusion_form': exclusion_form or BomExclusionRuleForm(),
        'equivalence_rules': BomEquivalenceRule.objects.all(),
        'equivalence_form': equivalence_form or BomEquivalenceRuleForm(),
        'library_settings': BomLibrarySetting.objects.all(),
        'library_form': library_form or BomLibrarySettingForm(),
    }


@staff_member_required
def part_import_filter_list(request):
    return render(request, 'erp/part_import_filter_list.html', _part_import_filter_context())


@staff_member_required
def bom_exclusion_rule_add(request):
    if request.method != 'POST':
        return redirect('erp:part_import_filter_list')

    form = BomExclusionRuleForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, 'Exclusion rule added.')
        return redirect('erp:part_import_filter_list')

    messages.warning(request, 'Please correct the errors below.')
    return render(request, 'erp/part_import_filter_list.html', _part_import_filter_context(exclusion_form=form))


@staff_member_required
def bom_exclusion_rule_edit(request, exclusion_rule_id):
    exclusion_rule = get_object_or_404(BomExclusionRule, pk=exclusion_rule_id)

    if request.method == 'POST':
        form = BomExclusionRuleForm(request.POST, instance=exclusion_rule)
        if form.is_valid():
            form.save()
            messages.success(request, 'Exclusion rule updated.')
            return redirect('erp:part_import_filter_list')
        messages.warning(request, 'Please correct the errors below.')
    else:
        form = BomExclusionRuleForm(instance=exclusion_rule)

    ctx = {'form': form, 'exclusion_rule': exclusion_rule}
    return render(request, 'erp/bom_exclusion_rule_edit.html', ctx)


@staff_member_required
def bom_exclusion_rule_delete(request, exclusion_rule_id):
    exclusion_rule = get_object_or_404(BomExclusionRule, pk=exclusion_rule_id)

    if request.method == 'POST':
        exclusion_rule.delete()
        messages.success(request, 'Exclusion rule deleted.')
        return redirect('erp:part_import_filter_list')

    ctx = {'exclusion_rule': exclusion_rule}
    return render(request, 'erp/bom_exclusion_rule_delete.html', ctx)


@staff_member_required
def bom_equivalence_rule_add(request):
    if request.method != 'POST':
        return redirect('erp:part_import_filter_list')

    form = BomEquivalenceRuleForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, 'Transformation rule added.')
        return redirect('erp:part_import_filter_list')

    messages.warning(request, 'Please correct the errors below.')
    return render(request, 'erp/part_import_filter_list.html', _part_import_filter_context(equivalence_form=form))


@staff_member_required
def bom_equivalence_rule_edit(request, equivalence_rule_id):
    equivalence_rule = get_object_or_404(BomEquivalenceRule, pk=equivalence_rule_id)

    if request.method == 'POST':
        form = BomEquivalenceRuleForm(request.POST, instance=equivalence_rule)
        if form.is_valid():
            form.save()
            messages.success(request, 'Transformation rule updated.')
            return redirect('erp:part_import_filter_list')
        messages.warning(request, 'Please correct the errors below.')
    else:
        form = BomEquivalenceRuleForm(instance=equivalence_rule)

    ctx = {'form': form, 'equivalence_rule': equivalence_rule}
    return render(request, 'erp/bom_equivalence_rule_edit.html', ctx)


@staff_member_required
def bom_equivalence_rule_delete(request, equivalence_rule_id):
    equivalence_rule = get_object_or_404(BomEquivalenceRule, pk=equivalence_rule_id)

    if request.method == 'POST':
        equivalence_rule.delete()
        messages.success(request, 'Transformation rule deleted.')
        return redirect('erp:part_import_filter_list')

    ctx = {'equivalence_rule': equivalence_rule}
    return render(request, 'erp/bom_equivalence_rule_delete.html', ctx)


@staff_member_required
def bom_library_setting_add(request):
    if request.method != 'POST':
        return redirect('erp:part_import_filter_list')

    form = BomLibrarySettingForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, 'Library setting added.')
        return redirect('erp:part_import_filter_list')

    messages.warning(request, 'Please correct the errors below.')
    return render(request, 'erp/part_import_filter_list.html', _part_import_filter_context(library_form=form))


@staff_member_required
def bom_library_setting_edit(request, library_setting_id):
    library_setting = get_object_or_404(BomLibrarySetting, pk=library_setting_id)

    if request.method == 'POST':
        form = BomLibrarySettingForm(request.POST, instance=library_setting)
        if form.is_valid():
            form.save()
            messages.success(request, 'Library setting updated.')
            return redirect('erp:part_import_filter_list')
        messages.warning(request, 'Please correct the errors below.')
    else:
        form = BomLibrarySettingForm(instance=library_setting)

    ctx = {'form': form, 'library_setting': library_setting}
    return render(request, 'erp/bom_library_setting_edit.html', ctx)


@staff_member_required
def bom_library_setting_delete(request, library_setting_id):
    library_setting = get_object_or_404(BomLibrarySetting, pk=library_setting_id)

    if request.method == 'POST':
        library_setting.delete()
        messages.success(request, 'Library setting deleted.')
        return redirect('erp:part_import_filter_list')

    ctx = {'library_setting': library_setting}
    return render(request, 'erp/bom_library_setting_delete.html', ctx)


@staff_member_required
def batch_list(request):
    pcb_top_qs = DesignAsset.objects.filter(asset_type=DesignAsset.PCB_TOP)
    batches = Batch.objects.select_related('design__client').prefetch_related(
        Prefetch('design__designasset_set', queryset=pcb_top_qs, to_attr='pcb_top_assets'),
        'production_stages',
    )

    ctx = {
        'batches': batches,
    }

    return render(request, 'erp/batch_list.html', ctx)


@staff_member_required
def batch_list_data(request):
    """JSON snapshot of every batch's production stage statuses, for polling on the Batches list page."""
    batches = Batch.objects.prefetch_related('production_stages')
    return JsonResponse({
        'batches': [
            {
                'id': batch.pk,
                'stages': [
                    {
                        'name': stage.name,
                        'status_display': stage.get_status_display(),
                        'color_class': stage.get_status_color_class(),
                    }
                    for stage in batch.production_stages.all()
                ],
            }
            for batch in batches
        ],
    })


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


def _batch_parts_required(batch):
    """One row per distinct Part on the batch's design, with quantity-per-board (the number of
    DesignBomEntry rows for that part) multiplied by the batch's quantity."""
    entries = batch.design.bom_entries.select_related('part').prefetch_related('part__sources__variants')

    counts = Counter()
    parts_by_id = {}
    for entry in entries:
        counts[entry.part_id] += 1
        parts_by_id[entry.part_id] = entry.part

    rows = [
        {'part': parts_by_id[part_id], 'required': count * batch.quantity}
        for part_id, count in counts.items()
    ]
    rows.sort(key=lambda row: row['part'].name.lower())
    return rows


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
        'parts_required': _batch_parts_required(batch),
    }

    return render(request, 'erp/batch_edit.html', ctx)


@staff_member_required
def batch_print(request, batch_id):
    batch = get_object_or_404(Batch.objects.select_related('design__client'), pk=batch_id)
    batch_url = request.build_absolute_uri(reverse('erp:batch_edit', args=[batch.pk]))
    ctx = {'batch': batch, 'batch_url': batch_url}
    return render(request, 'erp/batch_print.html', ctx)


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
def batch_duplicate(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)

    if request.method != 'POST':
        return redirect('erp:batch_edit', batch_id=batch.pk)

    new_batch = Batch.objects.create(
        design=batch.design,
        po=batch.po,
        quantity=batch.quantity,
    )

    for stage in batch.production_stages.all():
        BatchProductionStage.objects.create(
            batch=new_batch,
            name=stage.name,
            color=stage.color,
            order=stage.order,
            status=BatchProductionStage.NOT_STARTED,
        )

    messages.success(request, 'Batch duplicated.')
    return redirect('erp:batch_list')


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

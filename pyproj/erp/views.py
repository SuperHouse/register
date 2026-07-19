# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import csv
import io
import json
import os
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote as urlquote
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, ProtectedError, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import (
    AssemblyCostSettingsForm,
    BatchApplyTemplateForm,
    BatchForm,
    BatchProductionStageAddForm,
    BatchProductionStageUpdateForm,
    BomEquivalenceRuleForm,
    BomExclusionRuleForm,
    BomLibrarySettingForm,
    BomSupplementRuleForm,
    DesignBomEntryForm,
    LocationForm,
    PartAssetForm,
    PartCategoryForm,
    PartForm,
    PartReparentForm,
    PartSourceForm,
    PartSubstitutionForm,
    ProductionStageForm,
    ProductionStageTemplateForm,
    ProductionStageTemplateStepForm,
)
from device.models import Design, DesignAsset
from .models import (
    AssemblyCostSettings, Batch, BatchProductionStage, BomEquivalenceRule, BomExclusionRule, BomLibrarySetting,
    BomSupplementRule, DesignBomEntry, Location, Part, PartAsset, PartCategory, PartPriceBreak,
    PartPriceBreakHistory, PartSource, PartSourceVariant, PartSubstitution, PartsOrder, PartsOrderLine,
    ProductionStage, ProductionStageTemplate, ProductionStageTemplateStep, STOCK_TREND_PERIOD,
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
def assembly_cost_settings_edit(request):
    settings_obj = AssemblyCostSettings.get_solo()

    if request.method == 'POST':
        form = AssemblyCostSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Assembly cost settings updated.')
            return redirect('erp:assembly_cost_settings_edit')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = AssemblyCostSettingsForm(instance=settings_obj)

    return render(request, 'erp/assembly_cost_settings_edit.html', {'form': form})


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
    parts_qs = Part.objects.prefetch_related('sources__variants').annotate(bom_entry_count=Count('design_bom_entries')).order_by('name')
    if q:
        q_filter = Q(name__icontains=q) | Q(value__icontains=q) | Q(package__icontains=q) | Q(device__icontains=q)
        parts_qs = parts_qs.filter(q_filter)
        category_filter = Q(parts__in=Part.objects.filter(q_filter))
    else:
        category_filter = Q(parts__isnull=False)

    # Parts within each category are sorted by value_sort_key (natural magnitude order, e.g.
    # "120R" before "10K") rather than plain alphabetical name — see issue #87. Prefetching with
    # to_attr instead of the default cache gives an ordinary list that's safe to .sort() directly.
    uncategorised = list(parts_qs.filter(category__isnull=True))
    uncategorised.sort(key=lambda part: part.value_sort_key)
    categories_with_parts = list(
        PartCategory.objects
        .filter(category_filter)
        .prefetch_related(Prefetch('parts', queryset=parts_qs, to_attr='sorted_parts'))
        .distinct()
        .order_by('order', 'name')
    )
    for category in categories_with_parts:
        category.sorted_parts.sort(key=lambda part: part.value_sort_key)

    # A filter should reveal its matches even inside a collapsed category, without
    # actually persisting that category as expanded for the next unfiltered visit.
    expanded_categories = set(request.session.get('parts_expanded_categories', []))
    uncategorised_expanded = bool(q) or 'uncategorised' in expanded_categories
    for category in categories_with_parts:
        category.is_expanded = bool(q) or str(category.pk) in expanded_categories

    ctx = {
        'uncategorised': uncategorised,
        'uncategorised_expanded': uncategorised_expanded,
        'categories_with_parts': categories_with_parts,
        'q': q,
    }
    return render(request, 'erp/part_list.html', ctx)


@staff_member_required
def part_category_toggle_collapse(request):
    if request.method == 'POST':
        category_key = request.POST.get('category', '')
        expanded = request.POST.get('expanded') == 'true'
        expanded_categories = set(request.session.get('parts_expanded_categories', []))
        if expanded:
            expanded_categories.add(category_key)
        else:
            expanded_categories.discard(category_key)
        request.session['parts_expanded_categories'] = list(expanded_categories)

    return JsonResponse({'status': 'ok'})


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


def _bom_supplement_matches(rule, library, device, package, value):
    return (
        _bom_field_matches(rule.library, library)
        and _bom_field_matches(rule.device, device)
        and _bom_field_matches(rule.package, package)
        and _bom_field_matches(rule.value, value)
    )


def _expand_bom_supplement_rows(row, supplement_rules):
    """Return [row] plus one synthetic row per BomSupplementRule matching it.

    Matching is against the row's raw CSV fields, before exclusion/equivalence/library-setting
    rules run - a supplement rule describes the BOM as exported by Fusion, not some already
    transformed version of it. Every rule that matches contributes one extra row (e.g. a fuse
    holder footprint whose Value implies a same-value fuse part that never gets its own PCB
    footprint). Each returned row - the original and every supplement - is then run through the
    normal per-row pipeline independently, exactly as if the CSV had contained that many rows
    to begin with.
    """
    reference = (row.get('reference') or '').strip()
    device = (row.get('device') or '').strip()
    package = (row.get('package') or '').strip()
    value = (row.get('value') or '').strip()
    library = (row.get('library') or '').strip()

    rows = [row]
    for rule in supplement_rules:
        if _bom_supplement_matches(rule, library, device, package, value):
            rows.append({
                'reference': f'{reference}{rule.reference_suffix}' if reference else '',
                'device': rule.supplement_device or device,
                'package': rule.supplement_package or package,
                'value': rule.supplement_value or value,
                'library': rule.supplement_library or library,
            })
    return rows


def _resolve_bom_csv_row(row, exclusion_rules, equivalence_rules, library_settings_by_name):
    """Apply BOM import rules to one CSV row.

    Returns (reference, part, created) or None if the row is excluded. Shared by the Parts
    library CSV import (part_import_bom) and the per-design BOM import (design_bom_populate) —
    both consume the same reference/device/package/value/library CSV column format. Callers
    should first pass each raw CSV row through _expand_bom_supplement_rows() so any supplement
    rows it generates are resolved the same way as a normal imported row.
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

    # order_by('pk') overrides Part's default Meta.ordering (name) so that, if more than one
    # Part already matches this tuple (e.g. an old duplicate that was never cleaned up), the
    # earliest-created - almost always the canonical one other designs already reference - wins
    # deterministically, rather than whichever happens to sort first alphabetically by name.
    part = Part.objects.filter(
        device__iexact=device, package__iexact=package, value__iexact=value,
    ).order_by('pk').first()
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
        DesignBomEntry.objects.bulk_update(
            entries_to_update, ['pos_x', 'pos_y', 'rotation', 'side'], batch_size=100
        )
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

        supplement_rules = list(BomSupplementRule.objects.all())
        exclusion_rules = list(BomExclusionRule.objects.all())
        equivalence_rules = list(BomEquivalenceRule.objects.all())
        library_settings_by_name = {
            ls.library.lower(): ls for ls in BomLibrarySetting.objects.all()
        }

        added = 0
        skipped = 0
        excluded = 0

        for row in reader:
            for expanded_row in _expand_bom_supplement_rows(row, supplement_rules):
                resolved = _resolve_bom_csv_row(
                    expanded_row, exclusion_rules, equivalence_rules, library_settings_by_name,
                )
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

                supplement_rules = list(BomSupplementRule.objects.all())
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
                    for expanded_row in _expand_bom_supplement_rows(row, supplement_rules):
                        resolved = _resolve_bom_csv_row(
                            expanded_row, exclusion_rules, equivalence_rules, library_settings_by_name,
                        )
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
            return redirect(reverse('design_detail', args=[entry.design_id]) + '#bom')
        messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = DesignBomEntryForm(instance=entry)

    return render(request, 'erp/design_bom_entry_edit.html', {'form': form, 'entry': entry})


@staff_member_required
def design_bom_entry_delete(request, entry_id):
    entry = get_object_or_404(DesignBomEntry, pk=entry_id)
    design_id = entry.design_id

    if request.method == 'POST':
        entry.delete()
        messages.success(request, 'BOM entry deleted.')

    return redirect('design_detail', design_id=design_id)


def _part_stock_chart_data(part):
    """Build Chart.js-ready datasets for the Part detail page's stock history chart.

    One dataset per PartSource (its own recorded stock readings over time, oldest
    first) plus, when the part has more than one source with any history, a Total
    dataset built by forward-filling each source's last known reading as of every
    distinct timestamp across all sources and summing only the sources with a known
    reading at that point - a source with no reading yet is excluded from the sum
    rather than counted as zero stock, so the Total doesn't dip misleadingly low
    before a newly added source's first refresh. Returns None if no source on the
    part has any stock history yet, so the caller can skip rendering the chart card.

    Also returns x_min/x_max: a fixed STOCK_TREND_PERIOD-wide window ending now,
    regardless of how much history actually exists, so a part with only a few days
    of data doesn't render as an artificially stretched-out trend filling the whole
    chart width. Chart.js clips each dataset to this window itself - the datasets
    above are left untouched (not pre-filtered to the window) so widening
    STOCK_TREND_PERIOD later doesn't require changing how data is gathered here.
    """
    per_source_points = {}
    for source in part.sources.all():
        points = [
            (h.recorded_dt, h.stock)
            for h in reversed(source.stock_history.all())
            if h.stock is not None
        ]
        if points:
            per_source_points[source.pk] = points

    if not per_source_points:
        return None

    datasets = []
    for source in part.sources.all():
        points = per_source_points.get(source.pk)
        if points:
            datasets.append({
                'label': source.supplier_name,
                'total': False,
                'data': [{'x': dt.timestamp() * 1000, 'y': stock} for dt, stock in points],
            })

    if len(per_source_points) > 1:
        all_timestamps = sorted({dt for points in per_source_points.values() for dt, _ in points})
        cursor = {pk: 0 for pk in per_source_points}
        last_known = {}
        total_points = []
        for ts in all_timestamps:
            for pk, points in per_source_points.items():
                i = cursor[pk]
                while i < len(points) and points[i][0] <= ts:
                    last_known[pk] = points[i][1]
                    i += 1
                cursor[pk] = i
            if last_known:
                total_points.append({'x': ts.timestamp() * 1000, 'y': sum(last_known.values())})
        datasets.append({'label': 'Total', 'total': True, 'data': total_points})

    window_end = timezone.now()
    window_start = window_end - STOCK_TREND_PERIOD
    return {
        'datasets': datasets,
        'x_min': window_start.timestamp() * 1000,
        'x_max': window_end.timestamp() * 1000,
    }


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
        Part.objects.prefetch_related(
            'substitutions__substitute',
            'sources__variants__price_breaks',
            'sources__stock_history',
            'design_bom_entries__design__client',
        ),
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

    # Group BOM entries by design for the BOM References card.
    _by_design = {}
    for entry in part.design_bom_entries.all():
        if entry.design_id not in _by_design:
            _by_design[entry.design_id] = {'design': entry.design, 'refs': []}
        _by_design[entry.design_id]['refs'].append(entry.reference)
    bom_refs = sorted(_by_design.values(), key=lambda x: x['design'].sku)
    for row in bom_refs:
        row['refs'].sort()

    ctx = {
        'form': form,
        'part': part,
        'source_form': PartSourceForm(),
        'asset_form': PartAssetForm(),
        'substitution_form': PartSubstitutionForm(exclude_pk=part.pk),
        'reparent_form': PartReparentForm(exclude_pk=part.pk),
        'bom_refs': bom_refs,
        'stock_chart_data': _part_stock_chart_data(part),
    }
    return render(request, 'erp/part_edit.html', ctx)


@staff_member_required
def part_reparent(request, part_id):
    part = get_object_or_404(Part, pk=part_id)

    if request.method == 'POST':
        form = PartReparentForm(request.POST, exclude_pk=part.pk)
        if form.is_valid():
            target = form.cleaned_data['target_part']
            count = DesignBomEntry.objects.filter(part=part).update(part=target)
            messages.success(
                request,
                f'Reparented {count} BOM {"entry" if count == 1 else "entries"} from '
                f'"{part.name}" to "{target.name}".',
            )
            return redirect('erp:part_edit', part_id=part.pk)
        messages.warning(request, 'Please select a valid target part.')

    return redirect('erp:part_edit', part_id=part.pk)


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
    """Replace all price breaks for a variant with the supplied list.

    Also appends a PartPriceBreakHistory snapshot of the resulting breaks, but only when
    they differ from what was previously stored, so a refresh that reports unchanged
    pricing (the common case day to day) doesn't grow the history table with duplicate
    rows. Compares against DB-normalised values on both sides (the old set is read before
    the delete; the new set is read back after creating the replacement rows) rather than
    the raw API values, so Decimal/string/float formatting differences in what a supplier
    API returns can't cause a false "changed" reading.
    """
    old_breaks = set(variant.price_breaks.values_list('quantity', 'price', 'currency'))
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

    new_breaks = set(variant.price_breaks.values_list('quantity', 'price', 'currency'))
    if new_breaks != old_breaks:
        PartPriceBreakHistory.objects.bulk_create([
            PartPriceBreakHistory(variant=variant, quantity=qty, price=price, currency=currency)
            for qty, price, currency in new_breaks
        ])


def _digikey_base_url():
    """Return the appropriate DigiKey base URL based on DIGIKEY_CLIENT_SANDBOX."""
    sandbox = os.environ.get('DIGIKEY_CLIENT_SANDBOX', '').lower() in ('true', '1', 'yes')
    return 'https://sandbox-api.digikey.com' if sandbox else 'https://api.digikey.com'


def _digikey_locale_currency():
    """The ISO currency code DigiKey is asked to price in, per DIGIKEY_LOCALE_CURRENCY."""
    return os.environ.get('DIGIKEY_LOCALE_CURRENCY', 'AUD').strip() or 'AUD'


def _digikey_locale_headers():
    """Locale headers for DigiKey API requests, so ProductUrl and pricing come back for the
    configured region (DIGIKEY_LOCALE_SITE/_LANGUAGE/_CURRENCY, defaulting to AU/en/AUD to match
    this deployment — same convention as ELEMENT14_STORE_ID defaulting to au.element14.com)
    instead of DigiKey's own US default. Without these, ProductUrl is always a www.digikey.com
    link regardless of the requester's region, which sends users to a site where their regional
    cart/session doesn't apply (#86).
    """
    return {
        'X-DIGIKEY-Locale-Site': os.environ.get('DIGIKEY_LOCALE_SITE', 'AU').strip() or 'AU',
        'X-DIGIKEY-Locale-Language': os.environ.get('DIGIKEY_LOCALE_LANGUAGE', 'en').strip() or 'en',
        'X-DIGIKEY-Locale-Currency': _digikey_locale_currency(),
    }


def _digikey_price_breaks(variation):
    """Extract price breaks from a DigiKey ProductVariation's StandardPricing list.

    Unit prices come back in whatever currency was requested via the X-DIGIKEY-Locale-Currency
    header (see _digikey_locale_headers/_digikey_locale_currency), not always USD.
    """
    currency = _digikey_locale_currency()
    price_breaks = []
    for tier in (variation.get('StandardPricing') or []):
        qty = tier.get('BreakQuantity')
        price = tier.get('UnitPrice')
        if qty is not None and price is not None:
            price_breaks.append({'quantity': qty, 'price': price, 'currency': currency})
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


def _sync_digikey_sibling_variants(listing, variations, product_url=''):
    """Create/update every PartSourceVariant under `listing` from DigiKey's productdetails
    response.

    DigiKey's response includes every packaging variation's pricing and MOQ (not just the
    one that was looked up) in a single call. Existing sibling variants get their price
    breaks, MOQ, and last_refreshed updated; variations with no matching variant yet are
    created too, since the same response already has everything needed for them (issue #88)
    - so adding or refreshing any one DigiKey SKU keeps the whole packaging family in sync,
    instead of requiring the same lookup to be repeated once per SKU. DigiKey doesn't return
    a per-variation product URL, so newly-created siblings share `product_url` (the one
    product page lets a user pick packaging there anyway). MarketPlace variations
    (third-party resellers, not genuine DigiKey stock) are only updated if a variant for one
    already exists - never auto-created.

    Returns (created, updated) - lists of PartSourceVariant - so callers can tell whether any
    brand-new SKU was added.
    """
    now = timezone.now()
    existing_by_sku = {v.supplier_sku.lower(): v for v in listing.variants.all()}
    created, updated = [], []
    for variation in variations:
        digikey_pn = variation.get('DigiKeyProductNumber', '')
        if not digikey_pn:
            continue
        sibling = existing_by_sku.get(digikey_pn.lower())
        is_new = sibling is None
        if is_new:
            if variation.get('MarketPlace'):
                continue
            sibling = PartSourceVariant.objects.create(
                source=listing, supplier_sku=digikey_pn,
                packaging=(variation.get('PackageType') or {}).get('Name', ''), url=product_url,
            )

        _save_price_breaks(sibling, _digikey_price_breaks(variation))
        sibling.last_refreshed = now
        update_fields = ['last_refreshed']
        moq = variation.get('MinimumOrderQuantity')
        if moq is not None:
            sibling.moq = moq
            update_fields.append('moq')
        sibling.save(update_fields=update_fields)

        (created if is_new else updated).append(sibling)

    return created, updated


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
            _digikey_base_url() + f'/products/v4/search/{urlquote(sku, safe="")}/productdetails',
            headers={
                'Authorization': f'Bearer {access_token}',
                'X-DIGIKEY-Client-Id': client_id,
                'Accept': 'application/json',
                **_digikey_locale_headers(),
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
        product_url = product.get('ProductUrl') or f'https://www.digikey.com/en/products/detail/{urlquote(sku, safe="")}'
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
            listing = _get_or_create_supplier_listing(part, 'DigiKey', manufacturer_pn, stock)
            created, _updated = _sync_digikey_sibling_variants(listing, variations, product_url=product_url)
            source_saved = bool(created)

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
                _digikey_base_url() + f'/products/v4/search/{urlquote(sku, safe="")}/productdetails',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'X-DIGIKEY-Client-Id': client_id,
                    'Accept': 'application/json',
                    **_digikey_locale_headers(),
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
            _sync_digikey_sibling_variants(listing, variations, product_url=url)

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


# --- Parts Orders (DigiKey order-status sync, issue #90) ---
#
# Named "PartsOrder"/"PartsOrderLine" rather than "Order"/"OrderLine" to leave that name
# free for a possible future customer-order feature. DigiKey only for now - LCSC/Mouser/
# Element14 don't have a comparably self-service order-tracking API (see the issue #90
# plan for the research behind that call). There's no manual "Add Order" UI: every
# PartsOrder/PartsOrderLine row is created/updated by _sync_digikey_parts_orders(), driven
# by the refresh_parts_orders management command (or the parts_order_refresh view).
#
# NOTE: the DigiKey Order Status API's exact response shape is unconfirmed (it's a
# separate API product from the Product Information API already used elsewhere in this
# file, and its docs are gated behind a logged-in developer account) - every field name
# guessed below is isolated to a small function specifically so it's fast to correct once
# a real response has been seen. See the issue #90 plan for the full list of assumptions.

# How far back a refresh looks by default - a rolling window rather than a "last synced"
# cursor, so a status change on an older still-open order, a missed cron run, or a
# locally-deleted PartsOrder all self-heal on the next run without separate bookkeeping.
# Shared by the parts_order_refresh view and the refresh_parts_orders management command
# (which also exposes it as an overridable --lookback-days flag).
PARTS_ORDER_REFRESH_LOOKBACK_DAYS = 90


def _digikey_search_orders(access_token, client_id, from_date, to_date):
    """List DigiKey order summaries placed within [from_date, to_date] via SearchOrders.

    Returns a list of raw order-summary dicts from the API. May raise (HTTP errors) -
    it's the caller's job (_sync_digikey_parts_orders) to catch, matching the "fetch may
    raise, orchestration never does" split used by _get_digikey_access_token/_refresh_variant.

    ASSUMED PATH/PARAMS - see the "Explicitly flagged" section of the issue #90 plan.
    """
    import requests as http_requests

    resp = http_requests.get(
        _digikey_base_url() + '/orderstatus/v3/orders',
        headers={
            'Authorization': f'Bearer {access_token}',
            'X-DIGIKEY-Client-Id': client_id,
            'Accept': 'application/json',
            **_digikey_locale_headers(),
        },
        params={'startDate': from_date.isoformat(), 'endDate': to_date.isoformat()},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get('Orders', [])


def _digikey_retrieve_order(access_token, client_id, salesorder_id):
    """Fetch full line-item detail for one DigiKey order via RetrieveSalesOrder.

    ASSUMED PATH - see the "Explicitly flagged" section of the issue #90 plan.
    """
    import requests as http_requests

    resp = http_requests.get(
        _digikey_base_url() + f'/orderstatus/v3/orders/{urlquote(str(salesorder_id), safe="")}',
        headers={
            'Authorization': f'Bearer {access_token}',
            'X-DIGIKEY-Client-Id': client_id,
            'Accept': 'application/json',
            **_digikey_locale_headers(),
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_digikey_dt(raw):
    """Parse a DigiKey timestamp/date string into a datetime, or None if missing/
    unparseable. Format is assumed ISO 8601 - unconfirmed, see plan."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None


def _parse_digikey_date(raw):
    dt = _parse_digikey_dt(raw)
    return dt.date() if dt else None


def _map_digikey_line_status(raw_status):
    """Map DigiKey's raw per-line (or per-order, if no per-line status is reported -
    see plan) status string to PartsOrderLine.STATUS_CHOICES. Falls back to OPEN for
    anything unrecognised, which is the safe default: an unmapped real status should
    keep contributing to Part.incoming_stock rather than silently disappear from it.

    ASSUMED VOCABULARY - see the "Explicitly flagged" section of the issue #90 plan.
    """
    s = (raw_status or '').strip().lower()
    if s in ('shipped', 'in transit', 'backorder-shipped'):
        return PartsOrderLine.SHIPPED
    if s in ('delivered', 'received', 'complete', 'closed'):
        return PartsOrderLine.RECEIVED
    if s in ('cancelled', 'canceled'):
        return PartsOrderLine.CANCELLED
    return PartsOrderLine.OPEN


def _parse_digikey_order_line(raw_line):
    """ASSUMED FIELD NAMES - see the "Explicitly flagged" section of the issue #90 plan."""
    return {
        'supplier_sku': raw_line.get('DigiKeyProductNumber') or '',
        'description': raw_line.get('ProductDescription') or '',
        'quantity': raw_line.get('QuantityOrdered') or 0,
        'unit_price': raw_line.get('UnitPrice'),
        'currency': _digikey_locale_currency(),
        'status': _map_digikey_line_status(raw_line.get('Status') or raw_line.get('LineStatus')),
    }


def _parse_digikey_order(raw_order):
    """Convert one raw DigiKey order-detail dict (from _digikey_retrieve_order) into the
    flat shape _upsert_parts_order() needs. Pure/no I/O, so it's unit-testable against
    hand-built dict fixtures without a mocking library - see
    erp/tests/test_digikey_parts_order_sync.py.

    ASSUMED FIELD NAMES - see the "Explicitly flagged" section of the issue #90 plan.
    """
    return {
        'supplier_order_number': str(raw_order.get('SalesOrderId') or ''),
        'order_dt': _parse_digikey_dt(raw_order.get('OrderDate')),
        'expected_arrival_date': _parse_digikey_date(raw_order.get('ExpectedDeliveryDate')),
        'status': raw_order.get('Status') or '',
        'lines': [_parse_digikey_order_line(li) for li in (raw_order.get('LineItems') or [])],
    }


def _match_or_create_part_for_digikey_line(supplier_sku, description):
    """Resolve a DigiKey order line's SKU to a Part, creating a bare Part (plus a
    matching PartSource/PartSourceVariant) if nothing matches - per issue #90's "new
    parts discovered in orders would be created automatically" requirement.

    Matching order:
      1. Case-insensitive exact match on an existing PartSourceVariant.supplier_sku
         under a PartSource with supplier_name 'DigiKey' - the same natural key
         part_source_fetch_digikey/_sync_digikey_sibling_variants already use to
         identify a DigiKey SKU.
      2. No match: create a new bare Part (name=supplier_sku - no category/value/etc,
         same minimal-fields convention as any other auto-created record here), a
         PartSource (manufacturer_sku='' - unknown until a product lookup separately
         fills it in via the existing refresh_part_sources path), and a
         PartSourceVariant with this supplier_sku.

    Deliberately does not reuse _get_or_create_supplier_listing() - that function's merge
    key is manufacturer_sku (known once a product lookup has run), but here only the
    supplier SKU is known, so a fresh PartSource is always created for a genuinely new
    match, same as the manual part_source_add path does.

    Returns (part, part_source_variant); both None if supplier_sku is blank.
    """
    if not supplier_sku:
        return None, None

    variant = PartSourceVariant.objects.filter(
        supplier_sku__iexact=supplier_sku, source__supplier_name__iexact='DigiKey',
    ).select_related('source__part').first()
    if variant:
        return variant.source.part, variant

    part = Part.objects.create(name=supplier_sku, description=description or '')
    listing = PartSource.objects.create(part=part, supplier_name='DigiKey', manufacturer_sku='')
    variant = PartSourceVariant.objects.create(source=listing, supplier_sku=supplier_sku)
    return part, variant


def _upsert_parts_order(parsed_order, supplier_name='DigiKey'):
    """Create/update one PartsOrder and its PartsOrderLines from a _parse_digikey_order()
    result. Replaces all lines on every call (delete then recreate, same convention as
    _save_price_breaks) rather than diffing, since a DigiKey order-detail call always
    returns a complete line list - correct because there's nothing partial to merge.

    May raise - it's the caller's (_sync_digikey_parts_orders) job to catch, matching the
    "fetch/upsert may raise, orchestration never does" convention used elsewhere in this
    file (e.g. _refresh_variant).
    """
    parts_order, _created = PartsOrder.objects.update_or_create(
        supplier_name=supplier_name,
        supplier_order_number=parsed_order['supplier_order_number'],
        defaults={
            'order_dt': parsed_order['order_dt'],
            'expected_arrival_date': parsed_order['expected_arrival_date'],
            'status': parsed_order['status'],
            'last_refreshed': timezone.now(),
        },
    )

    parts_order.lines.all().delete()
    for line in parsed_order['lines']:
        part, variant = _match_or_create_part_for_digikey_line(line['supplier_sku'], line['description'])
        PartsOrderLine.objects.create(
            parts_order=parts_order, part=part, part_source_variant=variant,
            supplier_sku=line['supplier_sku'], description=line['description'],
            quantity=line['quantity'], unit_price=line['unit_price'], currency=line['currency'],
            status=line['status'],
        )

    return parts_order


def _recompute_incoming_stock():
    """Recompute every Part's incoming_stock from currently-open PartsOrderLines, as a
    single grouped-aggregate query rather than a per-Part loop. Called once per
    refresh_parts_orders run (not incrementally), so a cancelled/received line, a
    deleted PartsOrder, or a changed Part match all self-correct without per-event
    bookkeeping. Mirrors PartSource.stock: "last known truth, silently overwritten on
    refresh" - a manually-edited incoming_stock value is intentionally clobbered here.
    """
    open_totals = dict(
        PartsOrderLine.objects.filter(status=PartsOrderLine.OPEN, part__isnull=False)
        .values('part_id').annotate(total=Sum('quantity')).values_list('part_id', 'total')
    )

    Part.objects.exclude(pk__in=open_totals.keys()).exclude(incoming_stock__isnull=True) \
        .update(incoming_stock=None)
    for part_id, total in open_totals.items():
        Part.objects.filter(pk=part_id).exclude(incoming_stock=total).update(incoming_stock=total)


def _sync_digikey_parts_orders(from_date, to_date):
    """Discover and upsert every DigiKey order placed in [from_date, to_date], then
    recompute Part.incoming_stock from the result. Never raises - mirrors
    _refresh_variant's {'ok': True/False, 'error': ...} contract. The single function
    called by both the refresh_parts_orders management command and the optional
    parts_order_refresh "Refresh now" view.
    """
    try:
        client_id, access_token = _get_digikey_access_token()
        raw_orders = _digikey_search_orders(access_token, client_id, from_date, to_date)

        synced = 0
        for raw_summary in raw_orders:
            order_id = raw_summary.get('SalesOrderId')
            if not order_id:
                continue
            detail = _digikey_retrieve_order(access_token, client_id, order_id)
            parsed = _parse_digikey_order(detail)
            _upsert_parts_order(parsed, supplier_name='DigiKey')
            synced += 1

        _recompute_incoming_stock()
        return {'ok': True, 'orders_synced': synced}

    except RuntimeError as e:
        return {'ok': False, 'error': str(e)}
    except Exception as e:
        return {'ok': False, 'error': f'DigiKey order sync failed: {e}'}


@staff_member_required
def parts_order_list(request):
    """List all supplier orders, newest first, filterable by ?q= against
    supplier_order_number/supplier_name (same server-side initServerFilter AJAX pattern
    as Parts/Designs)."""
    q = request.GET.get('q', '').strip()
    parts_orders_qs = PartsOrder.objects.prefetch_related('lines__part').order_by('-order_dt')
    if q:
        parts_orders_qs = parts_orders_qs.filter(
            Q(supplier_order_number__icontains=q) | Q(supplier_name__icontains=q)
        )

    paginator = Paginator(parts_orders_qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'erp/parts_order_list.html', {'parts_orders': page_obj, 'page_obj': page_obj, 'q': q})


@staff_member_required
def parts_order_detail(request, parts_order_id):
    parts_order = get_object_or_404(
        PartsOrder.objects.prefetch_related('lines__part', 'lines__part_source_variant'), pk=parts_order_id
    )
    return render(request, 'erp/parts_order_detail.html', {'parts_order': parts_order})


@staff_member_required
def parts_order_refresh(request):
    """POST-only AJAX endpoint: force a DigiKey order sync now (parallels
    part_source_refresh), using the same rolling lookback window as the
    refresh_parts_orders management command's default, not a full historical resync."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    to_date = timezone.now().date()
    from_date = to_date - timedelta(days=PARTS_ORDER_REFRESH_LOOKBACK_DAYS)
    result = _sync_digikey_parts_orders(from_date, to_date)
    return JsonResponse(result)


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


def _part_import_filter_context(
    supplement_form=None, exclusion_form=None, equivalence_form=None, library_form=None,
):
    """Shared context for the merged Part Import Filters page.

    Sections are ordered to match the order rules are applied in part_import_bom / _expand_bom_supplement_rows
    / _resolve_bom_csv_row: supplement expansion first, then exclusion, then equivalence, then library
    (ignore-value) settings.
    """
    return {
        'supplement_rules': BomSupplementRule.objects.all(),
        'supplement_form': supplement_form or BomSupplementRuleForm(),
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
def bom_supplement_rule_add(request):
    if request.method != 'POST':
        return redirect('erp:part_import_filter_list')

    form = BomSupplementRuleForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, 'Supplemental part rule added.')
        return redirect('erp:part_import_filter_list')

    messages.warning(request, 'Please correct the errors below.')
    return render(request, 'erp/part_import_filter_list.html', _part_import_filter_context(supplement_form=form))


@staff_member_required
def bom_supplement_rule_edit(request, supplement_rule_id):
    supplement_rule = get_object_or_404(BomSupplementRule, pk=supplement_rule_id)

    if request.method == 'POST':
        form = BomSupplementRuleForm(request.POST, instance=supplement_rule)
        if form.is_valid():
            form.save()
            messages.success(request, 'Supplemental part rule updated.')
            return redirect('erp:part_import_filter_list')
        messages.warning(request, 'Please correct the errors below.')
    else:
        form = BomSupplementRuleForm(instance=supplement_rule)

    ctx = {'form': form, 'supplement_rule': supplement_rule}
    return render(request, 'erp/bom_supplement_rule_edit.html', ctx)


@staff_member_required
def bom_supplement_rule_delete(request, supplement_rule_id):
    supplement_rule = get_object_or_404(BomSupplementRule, pk=supplement_rule_id)

    if request.method == 'POST':
        supplement_rule.delete()
        messages.success(request, 'Supplemental part rule deleted.')
        return redirect('erp:part_import_filter_list')

    ctx = {'supplement_rule': supplement_rule}
    return render(request, 'erp/bom_supplement_rule_delete.html', ctx)


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

    groups = {'new': [], 'in_progress': [], 'complete': []}
    for batch in batches:
        groups[batch.progress_category].append(batch)

    ctx = {
        'batch_groups': [
            ('New', 'new', groups['new']),
            ('In Progress', 'in_progress', groups['in_progress']),
            ('Complete', 'complete', groups['complete']),
        ],
        'has_batches': any(groups.values()),
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
                        'status': stage.status,
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


def compute_bom_pricing(parts_by_id, per_board_counts, pricing_quantities):
    """For each distinct Part in `per_board_counts` (a {part_id: quantity} mapping — how many of
    that part one board needs, e.g. Design.bom_part_counts()), look up its cheapest reachable
    price break at the quantity given for that part in `pricing_quantities` (a separate
    {part_id: quantity} mapping — the volume actually being priced at).

    Passing `pricing_quantities = per_board_counts` prices at a single board's volume (the
    Design detail page's Build Costing); passing `per_board_counts` scaled up by a Batch's
    build quantity instead prices at the batch's actual order volume, while the returned
    bom_total_cost stays a per-board figure (the Batch detail page's Build Costing) — see
    Part.cheapest_price_break_for_quantity() for why buying in bulk can reach a cheaper break.

    Returns (price_break_by_part_id, bom_total_cost, bom_total_smt_joints, bom_total_pth_joints).
    """
    price_break_by_part_id = {
        part_id: parts_by_id[part_id].cheapest_price_break_for_quantity(pricing_quantities.get(part_id, 0))
        for part_id in per_board_counts
    }
    bom_total_smt_joints = sum(
        (parts_by_id[part_id].smt_joints or 0) * count for part_id, count in per_board_counts.items()
    )
    bom_total_pth_joints = sum(
        (parts_by_id[part_id].pth_joints or 0) * count for part_id, count in per_board_counts.items()
    )
    known_costs = [
        price_break_by_part_id[part_id].price * count
        for part_id, count in per_board_counts.items() if price_break_by_part_id[part_id]
    ]
    bom_total_cost = sum(known_costs) if known_costs else None
    return price_break_by_part_id, bom_total_cost, bom_total_smt_joints, bom_total_pth_joints


def build_costing_rows(design, bom_cost, bom_total_smt_joints, bom_total_pth_joints, assembly_cost_settings):
    """The Build Costing breakdown for one board of `design` — same rows shown on the Design
    detail page — given a BoM cost and joint totals (see compute_bom_pricing()) and the global
    AssemblyCostSettings rates. Returns (rows, total) as a list of (label, Decimal) pairs and
    their Decimal sum; shared by the Design detail page and the Batch detail page (the latter
    prices the BoM Cost row at the batch's build volume via compute_bom_pricing(), but the
    other rows and this breakdown itself are unaffected by quantity and stay per-board).
    Conformal Coating and Anti-Shock Glue are omitted from the returned rows (though still
    included in `total`) when they come to zero, since most designs use neither."""
    bom_cost = bom_cost or Decimal('0')
    rows = [
        ('BoM Cost', bom_cost),
        ('BoM Kitting Fee', bom_cost * assembly_cost_settings.kitting_margin_percent / Decimal('100')),
        ('Additional BoM', design.additional_materials),
        ('PCB', design.pcb_cost),
        ('Production Consumables', (
            Decimal(bom_total_pth_joints) * assembly_cost_settings.pth_joint_cost_cents
            + Decimal(bom_total_smt_joints) * assembly_cost_settings.smt_joint_cost_cents
        ) / Decimal('100')),
        ('Packaging', design.packaging),
        ('Conformal Coating', assembly_cost_settings.conformal_coating_charge if design.conformal_coating else Decimal('0')),
        ('Anti-Shock Glue', assembly_cost_settings.anti_shock_glue_charge if design.anti_shock_glue else Decimal('0')),
        ('Assembly Fee', Decimal(design.assembly_time_minutes) / Decimal('60') * assembly_cost_settings.labour_rate),
    ]
    total = sum(value for _, value in rows)
    hide_if_zero = {'Conformal Coating', 'Anti-Shock Glue'}
    rows = [(label, value) for label, value in rows if value != 0 or label not in hide_if_zero]
    return rows, total


def _batch_parts_required(batch):
    """One row per distinct Part on the batch's design, with quantity-per-board (the number of
    DesignBomEntry rows for that part) multiplied by the batch's quantity. Each row also carries
    the per-board count on its own (`per_board`) — reused by batch_edit to price the Batch
    detail page's Build Costing section at the batch's actual order volume (see
    compute_bom_pricing()) without recomputing the same counts twice."""
    entries = batch.design.bom_entries.select_related('part').prefetch_related(
        'part__sources__variants__price_breaks'
    )

    counts = Counter()
    parts_by_id = {}
    for entry in entries:
        counts[entry.part_id] += 1
        parts_by_id[entry.part_id] = entry.part

    rows = [
        {'part': parts_by_id[part_id], 'per_board': count, 'required': count * batch.quantity}
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

    parts_required = _batch_parts_required(batch)
    parts_by_id = {row['part'].pk: row['part'] for row in parts_required}
    per_board_counts = {row['part'].pk: row['per_board'] for row in parts_required}
    pricing_quantities = {row['part'].pk: row['required'] for row in parts_required}
    _, bom_cost, bom_total_smt_joints, bom_total_pth_joints = compute_bom_pricing(
        parts_by_id, per_board_counts, pricing_quantities
    )
    build_costing_rows_data, build_costing_total = build_costing_rows(
        batch.design, bom_cost, bom_total_smt_joints, bom_total_pth_joints, AssemblyCostSettings.get_solo()
    )

    ctx = {
        'form': form,
        'batch': batch,
        'production_stages_with_forms': production_stages_with_forms,
        'apply_template_form': BatchApplyTemplateForm(),
        'add_production_stage_form': BatchProductionStageAddForm(),
        'parts_required': parts_required,
        'boards': batch.devices.order_by('pk'),
        'pcb_top': DesignAsset.objects.filter(
            design=batch.design, asset_type=DesignAsset.PCB_TOP).first(),
        'build_costing_rows': build_costing_rows_data,
        'build_costing_total': build_costing_total,
        'total_batch_cost': build_costing_total * batch.quantity,
    }

    return render(request, 'erp/batch_edit.html', ctx)


@staff_member_required
def batch_print(request, batch_id):
    batch = get_object_or_404(Batch.objects.select_related('design__client'), pk=batch_id)
    batch_url = request.build_absolute_uri(reverse('erp:batch_edit', args=[batch.pk]))
    ctx = {
        'batch': batch,
        'batch_url': batch_url,
        'pcb_top': DesignAsset.objects.filter(
            design=batch.design, asset_type=DesignAsset.PCB_TOP).first(),
    }
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

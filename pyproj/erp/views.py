# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    BatchApplyTemplateForm,
    BatchForm,
    BatchProductionStageAddForm,
    BatchProductionStageUpdateForm,
    ProductionStageForm,
    ProductionStageTemplateForm,
    ProductionStageTemplateStepForm,
)
from .models import Batch, BatchProductionStage, ProductionStage, ProductionStageTemplate, ProductionStageTemplateStep


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
def production_stage_move(request, production_stage_id, direction):
    production_stage = get_object_or_404(ProductionStage, pk=production_stage_id)

    if request.method == 'POST':
        stages = list(ProductionStage.objects.order_by('order'))
        index = stages.index(production_stage)

        if direction == 'up' and index > 0:
            other = stages[index - 1]
        elif direction == 'down' and index < len(stages) - 1:
            other = stages[index + 1]
        else:
            other = None

        if other:
            production_stage.order, other.order = other.order, production_stage.order
            production_stage.save()
            other.save()

    return redirect('erp:production_stage_list')


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
def production_stage_template_step_move(request, step_id, direction):
    step = get_object_or_404(ProductionStageTemplateStep, pk=step_id)
    template_id = step.template_id

    if request.method == 'POST':
        steps = list(step.template.steps.order_by('order'))
        index = steps.index(step)

        if direction == 'up' and index > 0:
            other = steps[index - 1]
        elif direction == 'down' and index < len(steps) - 1:
            other = steps[index + 1]
        else:
            other = None

        if other:
            step.order, other.order = other.order, step.order
            step.save()
            other.save()

    return redirect('erp:production_stage_template_edit', template_id=template_id)


@staff_member_required
def batch_list(request):
    batches = Batch.objects.select_related('design')

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
def batch_production_stage_delete(request, batch_production_stage_id):
    batch_production_stage = get_object_or_404(BatchProductionStage, pk=batch_production_stage_id)
    batch_id = batch_production_stage.batch_id

    if request.method == 'POST':
        batch_production_stage.delete()
        messages.success(request, 'Production stage removed.')

    return redirect('erp:batch_edit', batch_id=batch_id)


@staff_member_required
def batch_production_stage_move(request, batch_production_stage_id, direction):
    batch_production_stage = get_object_or_404(BatchProductionStage, pk=batch_production_stage_id)
    batch_id = batch_production_stage.batch_id

    if request.method == 'POST':
        stages = list(batch_production_stage.batch.production_stages.order_by('order'))
        index = stages.index(batch_production_stage)

        if direction == 'up' and index > 0:
            other = stages[index - 1]
        elif direction == 'down' and index < len(stages) - 1:
            other = stages[index + 1]
        else:
            other = None

        if other:
            batch_production_stage.order, other.order = other.order, batch_production_stage.order
            batch_production_stage.save()
            other.save()

    return redirect('erp:batch_edit', batch_id=batch_id)

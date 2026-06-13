# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from .forms import OperationForm, OperationTemplateForm, OperationTemplateStepForm
from .models import Operation, OperationTemplate, OperationTemplateStep


@staff_member_required
def settings_index(request):
    return render(request, 'erp/settings_index.html')


@staff_member_required
def operation_list(request):
    operations = Operation.objects.all()

    if request.method == 'POST':
        form = OperationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Operation added.')
            return redirect('erp:operation_list')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = OperationForm()

    ctx = {
        'operations': operations,
        'form': form,
    }

    return render(request, 'erp/operation_list.html', ctx)


@staff_member_required
def operation_edit(request, operation_id):
    operation = get_object_or_404(Operation, pk=operation_id)

    if request.method == 'POST':
        form = OperationForm(request.POST, instance=operation)
        if form.is_valid():
            form.save()
            messages.success(request, 'Operation updated.')
            return redirect('erp:operation_list')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = OperationForm(instance=operation)

    ctx = {
        'form': form,
        'operation': operation,
    }

    return render(request, 'erp/operation_edit.html', ctx)


@staff_member_required
def operation_delete(request, operation_id):
    operation = get_object_or_404(Operation, pk=operation_id)

    if request.method == 'POST':
        try:
            operation.delete()
            messages.success(request, 'Operation deleted.')
        except ProtectedError:
            messages.warning(request, 'This operation cannot be deleted because it is used by one or more templates.')
        return redirect('erp:operation_list')

    ctx = {
        'operation': operation,
    }

    return render(request, 'erp/operation_delete.html', ctx)


@staff_member_required
def template_list(request):
    templates = OperationTemplate.objects.all()

    if request.method == 'POST':
        form = OperationTemplateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Template added.')
            return redirect('erp:template_list')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = OperationTemplateForm()

    ctx = {
        'templates': templates,
        'form': form,
    }

    return render(request, 'erp/template_list.html', ctx)


@staff_member_required
def template_edit(request, template_id):
    template = get_object_or_404(OperationTemplate, pk=template_id)

    if request.method == 'POST':
        form = OperationTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, 'Template updated.')
            return redirect('erp:template_edit', template_id=template.pk)
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = OperationTemplateForm(instance=template)

    ctx = {
        'form': form,
        'template': template,
        'steps': template.steps.select_related('operation'),
        'step_form': OperationTemplateStepForm(),
    }

    return render(request, 'erp/template_edit.html', ctx)


@staff_member_required
def template_delete(request, template_id):
    template = get_object_or_404(OperationTemplate, pk=template_id)

    if request.method == 'POST':
        template.delete()
        messages.success(request, 'Template deleted.')
        return redirect('erp:template_list')

    ctx = {
        'template': template,
    }

    return render(request, 'erp/template_delete.html', ctx)


@staff_member_required
def template_step_add(request, template_id):
    template = get_object_or_404(OperationTemplate, pk=template_id)

    if request.method == 'POST':
        form = OperationTemplateStepForm(request.POST)
        if form.is_valid():
            last_step = template.steps.order_by('-order').first()
            next_order = (last_step.order + 1) if last_step else 1

            step = form.save(commit=False)
            step.template = template
            step.order = next_order
            step.save()
            messages.success(request, 'Step added.')
        else:
            messages.warning(request, 'Please select an operation to add.')

    return redirect('erp:template_edit', template_id=template.pk)


@staff_member_required
def template_step_delete(request, step_id):
    step = get_object_or_404(OperationTemplateStep, pk=step_id)
    template_id = step.template_id

    if request.method == 'POST':
        step.delete()
        messages.success(request, 'Step removed.')

    return redirect('erp:template_edit', template_id=template_id)


@staff_member_required
def template_step_move(request, step_id, direction):
    step = get_object_or_404(OperationTemplateStep, pk=step_id)
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

    return redirect('erp:template_edit', template_id=template_id)

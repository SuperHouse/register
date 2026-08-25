# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import json

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from device.models import Design
from .forms import (
    CompatibleDesignAddForm, CopyTestStepsFromForm, TesterForm, TestModuleForm, TestModuleTypeForm,
    TestStepForm, TestStepTypeAddForm, TestSuiteSaveNewVersionForm,
)
from .models import Tester, TestModule, TestModuleType, TestStep, TestSuite


@staff_member_required
def tester_list(request):
    # The two inline-add forms share this page, so each gets a prefix to
    # keep its field names and HTML ids distinct.
    ctx = {
        'testers': Tester.objects.all(),
        'modules': TestModule.objects.select_related('module_type'),
        'tester_form': TesterForm(prefix='tester'),
        'module_form': TestModuleForm(prefix='module'),
    }
    return render(request, 'testing/tester_list.html', ctx)


@staff_member_required
def test_module_type_list(request):
    # Test module types are the abstract definitions, managed in Settings
    # (distinct from the concrete Testers/Test Modules in the Testers section).
    ctx = {
        'module_types': TestModuleType.objects.prefetch_related('compatible_designs', 'modules'),
        'module_type_form': TestModuleTypeForm(prefix='module_type'),
    }
    return render(request, 'testing/test_module_type_list.html', ctx)


@staff_member_required
def tester_add(request):
    if request.method == 'POST':
        form = TesterForm(request.POST, prefix='tester')
        if form.is_valid():
            form.save()
            messages.success(request, 'Tester added.')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    return redirect('testing:tester_list')


@staff_member_required
def tester_edit(request, tester_id):
    tester = get_object_or_404(Tester, pk=tester_id)

    if request.method == 'POST':
        form = TesterForm(request.POST, instance=tester)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tester updated.')
            return redirect('testing:tester_list')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = TesterForm(instance=tester)

    ctx = {'form': form, 'tester': tester}
    return render(request, 'testing/tester_edit.html', ctx)


@staff_member_required
def tester_delete(request, tester_id):
    tester = get_object_or_404(Tester, pk=tester_id)

    if request.method == 'POST':
        tester.delete()
        messages.success(request, 'Tester deleted.')
        return redirect('testing:tester_list')

    ctx = {'tester': tester}
    return render(request, 'testing/tester_delete.html', ctx)


@staff_member_required
def test_module_add(request):
    if request.method == 'POST':
        form = TestModuleForm(request.POST, prefix='module')
        if form.is_valid():
            form.save()
            messages.success(request, 'Test module added.')
        else:
            messages.warning(request, 'Please select a test module type to add.')
    return redirect('testing:tester_list')


@staff_member_required
def test_module_edit(request, module_id):
    module = get_object_or_404(TestModule, pk=module_id)

    if request.method == 'POST':
        form = TestModuleForm(request.POST, instance=module)
        if form.is_valid():
            form.save()
            messages.success(request, 'Test module updated.')
            return redirect('testing:tester_list')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = TestModuleForm(instance=module)

    ctx = {'form': form, 'module': module}
    return render(request, 'testing/test_module_edit.html', ctx)


@staff_member_required
def test_module_delete(request, module_id):
    module = get_object_or_404(TestModule, pk=module_id)

    if request.method == 'POST':
        module.delete()
        messages.success(request, 'Test module deleted.')
        return redirect('testing:tester_list')

    ctx = {'module': module}
    return render(request, 'testing/test_module_delete.html', ctx)


@staff_member_required
def test_module_type_add(request):
    if request.method == 'POST':
        form = TestModuleTypeForm(request.POST, prefix='module_type')
        if form.is_valid():
            module_type = form.save()
            messages.success(request, 'Test module type added.')
            return redirect('testing:test_module_type_edit', module_type_id=module_type.pk)
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    return redirect('testing:test_module_type_list')


@staff_member_required
def test_module_type_edit(request, module_type_id):
    module_type = get_object_or_404(TestModuleType, pk=module_type_id)

    if request.method == 'POST':
        form = TestModuleTypeForm(request.POST, instance=module_type)
        if form.is_valid():
            form.save()
            messages.success(request, 'Test module type updated.')
            return redirect('testing:test_module_type_edit', module_type_id=module_type.pk)
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = TestModuleTypeForm(instance=module_type)

    ctx = {
        'form': form,
        'module_type': module_type,
        'compatible_designs': module_type.compatible_designs.select_related('client').order_by(
            'client__company_name', 'sku', 'name', 'hw_version'
        ),
        'design_form': CompatibleDesignAddForm(module_type=module_type),
        'modules': module_type.modules.all(),
    }
    return render(request, 'testing/test_module_type_edit.html', ctx)


@staff_member_required
def test_module_type_delete(request, module_type_id):
    module_type = get_object_or_404(TestModuleType, pk=module_type_id)

    if request.method == 'POST':
        try:
            module_type.delete()
            messages.success(request, 'Test module type deleted.')
        except ProtectedError:
            messages.warning(request, 'This test module type cannot be deleted because one or more physical test modules are of this type.')
        return redirect('testing:test_module_type_list')

    ctx = {'module_type': module_type}
    return render(request, 'testing/test_module_type_delete.html', ctx)


@staff_member_required
def test_module_type_design_add(request, module_type_id):
    module_type = get_object_or_404(TestModuleType, pk=module_type_id)

    if request.method == 'POST':
        form = CompatibleDesignAddForm(request.POST, module_type=module_type)
        if form.is_valid():
            module_type.compatible_designs.add(form.cleaned_data['design'])
            messages.success(request, 'Compatible design added.')
        else:
            messages.warning(request, 'Please select a design to add.')

    return redirect('testing:test_module_type_edit', module_type_id=module_type.pk)


@staff_member_required
def test_module_type_design_remove(request, module_type_id, design_id):
    module_type = get_object_or_404(TestModuleType, pk=module_type_id)
    design = get_object_or_404(Design, pk=design_id)

    if request.method == 'POST':
        module_type.compatible_designs.remove(design)
        messages.success(request, 'Compatible design removed.')

    return redirect('testing:test_module_type_edit', module_type_id=module_type.pk)


def _get_or_create_current_suite(design):
    """Every Design has exactly one *current* Test Suite - the highest-`version` row for that
    design - which may not exist yet if nobody has touched this design's testing setup. Lazily
    creates version 1 (with no steps) the first time it's needed, rather than requiring an
    explicit "Add Test Suite" step - that step has been dropped in favour of this implicit
    model."""
    suite = design.test_suites.first()  # TestSuite.Meta.ordering = ['design', '-version']
    if suite is None:
        suite = TestSuite.objects.create(design=design, version=1)
    return suite


def _is_current_suite(suite):
    return suite.design.test_suites.first().pk == suite.pk


@staff_member_required
def test_suite_current(request, design_id):
    design = get_object_or_404(Design, pk=design_id)
    suite = _get_or_create_current_suite(design)

    ctx = {
        'design': design,
        'suite': suite,
        'steps': suite.steps.all(),
        'step_type_add_form': TestStepTypeAddForm(),
        'version_count': design.test_suites.count(),
        'copy_steps_form': CopyTestStepsFromForm(exclude_design=design),
        'has_other_active_designs': Design.objects.filter(obsolete=False).exclude(pk=design.pk).exists(),
    }
    return render(request, 'testing/test_suite_current.html', ctx)


@staff_member_required
def test_suite_copy_steps_from(request, design_id):
    """Appends another Design's current Test Suite's steps (including their config) onto
    this Design's current Test Suite, at the end of its list."""
    design = get_object_or_404(Design, pk=design_id)
    suite = _get_or_create_current_suite(design)

    if request.method == 'POST':
        form = CopyTestStepsFromForm(request.POST, exclude_design=design)
        if form.is_valid():
            source_design = form.cleaned_data['source_design']
            source_suite = source_design.test_suites.first()
            source_steps = list(source_suite.steps.all()) if source_suite else []

            if not source_steps:
                messages.warning(request, f'{source_design} has no test steps to copy.')
            else:
                last_step = suite.steps.order_by('-order').first()
                next_order = (last_step.order + 1) if last_step else 1
                for offset, step in enumerate(source_steps):
                    TestStep.objects.create(
                        suite=suite,
                        order=next_order + offset,
                        step_type=step.step_type,
                        name=step.name,
                        hard_fail=step.hard_fail,
                        config=step.config,
                    )
                messages.success(request, f'Copied {len(source_steps)} step(s) from {source_design}.')
        else:
            messages.warning(request, 'Please select a design to copy from.')

    return redirect('testing:test_suite_current', design_id=design.pk)


@staff_member_required
def test_suite_save_new_version(request, design_id):
    """Freezes the current version's steps as a historical record and starts the next version
    as an editable copy (see TestSuite's docstring)."""
    design = get_object_or_404(Design, pk=design_id)
    current = _get_or_create_current_suite(design)

    if request.method == 'POST':
        form = TestSuiteSaveNewVersionForm(request.POST)
        if form.is_valid():
            current.notes = form.cleaned_data['notes']
            current.save(update_fields=['notes'])

            new_suite = TestSuite.objects.create(design=design, version=current.version + 1)
            for step in current.steps.all():
                TestStep.objects.create(
                    suite=new_suite,
                    order=step.order,
                    step_type=step.step_type,
                    name=step.name,
                    hard_fail=step.hard_fail,
                    config=step.config,
                )
            messages.success(request, f'Version {current.version} saved. Now editing version {new_suite.version}.')
            return redirect('testing:test_suite_current', design_id=design.pk)
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = TestSuiteSaveNewVersionForm()

    return render(request, 'testing/test_suite_save_new_version.html', {'design': design, 'suite': current, 'form': form})


@staff_member_required
def test_suite_version_list(request, design_id):
    design = get_object_or_404(Design, pk=design_id)
    suites = design.test_suites.prefetch_related('steps')
    current = suites.first()

    return render(request, 'testing/test_suite_version_list.html', {
        'design': design, 'suites': suites, 'current': current,
    })


@staff_member_required
def test_suite_version_detail(request, design_id, version):
    design = get_object_or_404(Design, pk=design_id)
    suite = get_object_or_404(design.test_suites, version=version)

    return render(request, 'testing/test_suite_version_detail.html', {
        'design': design,
        'suite': suite,
        'steps': suite.steps.all(),
        'is_current': _is_current_suite(suite),
    })


@staff_member_required
def test_step_add(request, design_id):
    design = get_object_or_404(Design, pk=design_id)
    suite = _get_or_create_current_suite(design)

    if request.method == 'POST':
        form = TestStepTypeAddForm(request.POST)
        if form.is_valid():
            step_type = form.cleaned_data['step_type']
            last_step = suite.steps.order_by('-order').first()
            next_order = (last_step.order + 1) if last_step else 1

            step = TestStep.objects.create(
                suite=suite,
                order=next_order,
                step_type=step_type,
                name=dict(TestStep.STEP_TYPE_CHOICES).get(step_type, step_type),
                config={'schema_version': TestStep.CONFIG_SCHEMA_VERSION},
            )
            messages.success(request, 'Step added - fill in its configuration below.')
            return redirect('testing:test_step_edit', step_id=step.pk)
        else:
            messages.warning(request, 'Please select a step type to add.')

    return redirect('testing:test_suite_current', design_id=design.pk)


@staff_member_required
def test_step_edit(request, step_id):
    step = get_object_or_404(TestStep.objects.select_related('suite__design'), pk=step_id)

    if not _is_current_suite(step.suite):
        messages.warning(request, 'This step belongs to a historical version and can no longer be edited.')
        return redirect('testing:test_suite_version_detail', design_id=step.suite.design_id, version=step.suite.version)

    if request.method == 'POST':
        form = TestStepForm(request.POST, instance=step)
        if form.is_valid():
            form.save()
            messages.success(request, 'Step updated.')
            return redirect(reverse('testing:test_suite_current', args=[step.suite.design_id]) + '#test-steps')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = TestStepForm(instance=step)

    return render(request, 'testing/test_step_edit.html', {'form': form, 'step': step})


@staff_member_required
def test_step_delete(request, step_id):
    step = get_object_or_404(TestStep.objects.select_related('suite__design'), pk=step_id)

    if not _is_current_suite(step.suite):
        messages.warning(request, 'This step belongs to a historical version and can no longer be deleted.')
        return redirect('testing:test_suite_version_detail', design_id=step.suite.design_id, version=step.suite.version)

    design_id = step.suite.design_id

    if request.method == 'POST':
        step.delete()
        messages.success(request, 'Step removed.')
        return redirect('testing:test_suite_current', design_id=design_id)

    return render(request, 'testing/test_step_delete.html', {'step': step})


@staff_member_required
def test_step_reorder(request, design_id):
    design = get_object_or_404(Design, pk=design_id)
    suite = _get_or_create_current_suite(design)

    if request.method == 'POST':
        data = json.loads(request.body)
        steps_by_id = {step.pk: step for step in suite.steps.all()}

        for index, step_id in enumerate(data.get('order', []), start=1):
            step = steps_by_id.get(int(step_id))
            if step and step.order != index:
                step.order = index
                step.save(update_fields=['order'])

    return JsonResponse({'status': 'ok'})

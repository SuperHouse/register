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


def _fork_draft(design, saved_suite):
    """Creates a new draft version for `design`, copying `saved_suite`'s steps (if given - None
    for a design with no Test Suite at all yet). Returns (draft, old_pk_to_new_step) so a caller
    holding step pks from *before* the fork (e.g. a reorder payload built from the page as it was
    rendered, before this request forked it) can translate them to their counterparts in the new
    draft - see `_ensure_editable_step` and `test_step_reorder`."""
    draft = TestSuite.objects.create(
        design=design, version=(saved_suite.version + 1 if saved_suite else 1), status=TestSuite.DRAFT,
    )
    old_pk_to_new = {}
    if saved_suite is not None:
        for step in saved_suite.steps.all():
            new_step = TestStep.objects.create(
                suite=draft, order=step.order, step_type=step.step_type,
                name=step.name, hard_fail=step.hard_fail, config=step.config,
            )
            old_pk_to_new[step.pk] = new_step
    return draft, old_pk_to_new


def _get_or_create_draft_suite(design):
    """Every Design has at most one *draft* Test Suite at a time - the one steps are actually
    added to/edited on (issue #110). If the highest version is already a draft, it's reused
    directly; otherwise (it's SAVED, or there's no Test Suite yet) a new draft is forked from
    it, so an already-saved version's content is never mutated in place."""
    current = design.test_suites.first()  # TestSuite.Meta.ordering = ['design', '-version']
    if current is not None and current.status == TestSuite.DRAFT:
        return current
    draft, _old_pk_to_new = _fork_draft(design, current)
    return draft


def _is_current_suite(suite):
    """Whether `suite` is the single highest-version row for its design - i.e. whether it's
    reachable/actionable from the Design detail page at all (as the draft being edited, or as
    the current saved version about to be forked into a draft on the next edit), as opposed to
    a fully superseded historical version, which is permanently locked."""
    return suite.design.test_suites.first().pk == suite.pk


def _ensure_editable_step(step):
    """`step` must already have passed `_is_current_suite(step.suite)`. If its suite is still
    just SAVED (nothing's changed since the last save), forks a new draft from it and returns
    this step's counterpart there instead, so the SAVED row itself is never mutated (issue
    #110) - the caller should apply its edit/delete to the returned step, not `step`."""
    if step.suite.status == TestSuite.DRAFT:
        return step
    _draft, old_pk_to_new = _fork_draft(step.suite.design, step.suite)
    return old_pk_to_new[step.pk]


@staff_member_required
def test_suite_copy_steps_from(request, design_id):
    """Appends another Design's current (latest saved) Test Suite's steps onto this Design's
    draft, at the end of its list. Copies from the source's last SAVED version specifically,
    not any in-progress draft it might have, so an unfinished edit on the source can't leak in
    via a copy."""
    design = get_object_or_404(Design, pk=design_id)

    if request.method == 'POST':
        form = CopyTestStepsFromForm(request.POST, exclude_design=design)
        if form.is_valid():
            source_design = form.cleaned_data['source_design']
            source_suite = source_design.test_suites.filter(status=TestSuite.SAVED).first()
            source_steps = list(source_suite.steps.all()) if source_suite else []

            if not source_steps:
                messages.warning(request, f'{source_design} has no saved test steps to copy.')
            else:
                suite = _get_or_create_draft_suite(design)
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

    return redirect(reverse('design_detail', args=[design.pk]) + '#test-suite')


@staff_member_required
def test_suite_save_new_version(request, design_id):
    """Marks the design's current draft SAVED (immutable) in place (issue #110) - see
    TestSuite's docstring. No new row is created here; the next edit made after this will
    lazily fork one from it via `_get_or_create_draft_suite`/`_ensure_editable_step`."""
    design = get_object_or_404(Design, pk=design_id)
    draft = design.test_suites.first()

    if draft is None or draft.status != TestSuite.DRAFT:
        messages.info(request, 'There are no unsaved changes to save.')
        return redirect(reverse('design_detail', args=[design.pk]) + '#test-suite')

    if request.method == 'POST':
        form = TestSuiteSaveNewVersionForm(request.POST)
        if form.is_valid():
            draft.notes = form.cleaned_data['notes']
            draft.status = TestSuite.SAVED
            draft.save(update_fields=['notes', 'status'])
            messages.success(request, f'Version {draft.version} saved.')
            return redirect(reverse('design_detail', args=[design.pk]) + '#test-suite')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = TestSuiteSaveNewVersionForm()

    return render(request, 'testing/test_suite_save_new_version.html', {'design': design, 'suite': draft, 'form': form})


@staff_member_required
def test_suite_discard_draft(request, design_id):
    """Deletes the design's current draft outright, discarding whatever's changed since the
    last saved version (issue #110's "operator could choose to discard the draft, or save it
    as a new version")."""
    design = get_object_or_404(Design, pk=design_id)
    draft = design.test_suites.first()

    if draft is None or draft.status != TestSuite.DRAFT:
        messages.info(request, 'There is no draft to discard.')
        return redirect(reverse('design_detail', args=[design.pk]) + '#test-suite')

    if request.method == 'POST':
        version = draft.version
        draft.delete()
        messages.success(request, f'Draft version {version} discarded.')
        return redirect(reverse('design_detail', args=[design.pk]) + '#test-suite')

    return render(request, 'testing/test_suite_discard_draft.html', {'design': design, 'suite': draft})


@staff_member_required
def test_suite_version_list(request, design_id):
    design = get_object_or_404(Design, pk=design_id)
    suites = design.test_suites.prefetch_related('steps')
    highest = suites.first()  # the draft if one exists, else the current saved version
    current = suites.filter(status=TestSuite.SAVED).first()  # may be None - never saved yet

    return render(request, 'testing/test_suite_version_list.html', {
        'design': design, 'suites': suites, 'highest': highest, 'current': current,
    })


@staff_member_required
def test_suite_version_detail(request, design_id, version):
    design = get_object_or_404(Design, pk=design_id)
    suite = get_object_or_404(design.test_suites, version=version)
    highest = design.test_suites.first()
    latest_saved = design.test_suites.filter(status=TestSuite.SAVED).first()

    return render(request, 'testing/test_suite_version_detail.html', {
        'design': design,
        'suite': suite,
        'steps': suite.steps.all(),
        # Whether this suite is the design's single actionable "edit slot" right now (the
        # draft, or - if there's no draft - the latest saved version) - distinct from whether
        # it's the *latest saved* version, since those can diverge once a newer draft exists
        # on top of an already-saved suite (issue #110): that suite is still "Current" for
        # anyone fetching a version, but is no longer where further edits land.
        'is_highest': highest is not None and highest.pk == suite.pk,
        'is_current_saved': latest_saved is not None and latest_saved.pk == suite.pk,
        'highest': highest,
    })


@staff_member_required
def test_step_add(request, design_id):
    design = get_object_or_404(Design, pk=design_id)

    if request.method == 'POST':
        form = TestStepTypeAddForm(request.POST)
        if form.is_valid():
            step_type = form.cleaned_data['step_type']
            suite = _get_or_create_draft_suite(design)
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

    return redirect(reverse('design_detail', args=[design.pk]) + '#test-suite')


@staff_member_required
def test_step_edit(request, step_id):
    step = get_object_or_404(TestStep.objects.select_related('suite__design'), pk=step_id)

    if not _is_current_suite(step.suite):
        messages.warning(request, 'This step belongs to a historical version and can no longer be edited.')
        return redirect('testing:test_suite_version_detail', design_id=step.suite.design_id, version=step.suite.version)

    if request.method == 'POST':
        form = TestStepForm(request.POST, instance=step)
        if form.is_valid():
            # Validate against the original step first (harmless even when it's about to be
            # superseded by a fork); only apply the change to whichever instance is actually
            # editable, so a rejected submission never forks a version for nothing.
            target = _ensure_editable_step(step)
            target.step_type = form.cleaned_data['step_type']
            target.name = form.cleaned_data['name']
            target.hard_fail = form.cleaned_data['hard_fail']
            config = dict(form.cleaned_data.get('config', {}))
            config['schema_version'] = TestStep.CONFIG_SCHEMA_VERSION
            target.config = config
            target.save()
            messages.success(request, 'Step updated.')
            return redirect(reverse('design_detail', args=[target.suite.design_id]) + '#test-suite')
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
        target = _ensure_editable_step(step)
        target.delete()
        messages.success(request, 'Step removed.')
        return redirect(reverse('design_detail', args=[design_id]) + '#test-suite')

    return render(request, 'testing/test_step_delete.html', {'step': step})


@staff_member_required
def test_step_reorder(request, design_id):
    design = get_object_or_404(Design, pk=design_id)

    if request.method == 'POST':
        current = design.test_suites.first()
        data = json.loads(request.body)
        requested_pks = [int(pk) for pk in data.get('order', [])]

        if current is not None and current.status == TestSuite.DRAFT:
            suite = current
            ordered_pks = requested_pks
        else:
            # The pks in the request came from the page as it was rendered, before this fork -
            # translate them to their counterparts in the new draft (see _fork_draft).
            suite, old_pk_to_new = _fork_draft(design, current)
            ordered_pks = [old_pk_to_new[pk].pk for pk in requested_pks if pk in old_pk_to_new]

        steps_by_id = {step.pk: step for step in suite.steps.all()}
        for index, step_pk in enumerate(ordered_pks, start=1):
            step = steps_by_id.get(step_pk)
            if step and step.order != index:
                step.order = index
                step.save(update_fields=['order'])

    return JsonResponse({'status': 'ok'})

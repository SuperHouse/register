# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import io
import json
import zipfile

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import ProtectedError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify

from device.models import Design
from .forms import (
    CompatibleDesignAddForm, CopyTestStepsFromForm, ManualCheckForm, TesterForm, TestModuleForm,
    TestModuleTypeForm, TestStepForm, TestStepTypeAddForm, TestSuiteSaveNewVersionForm,
)
from .models import ManualCheck, Tester, TestModule, TestModuleType, TestStep, TestSuite


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
    """Creates a new draft version for `design`, copying `saved_suite`'s steps and manual
    checks (both lists are versioned together - issue #112; `saved_suite` is None for a design
    with no Test Suite at all yet). Returns (draft, step_pk_map, manual_check_pk_map) so a
    caller holding pks from *before* the fork (e.g. a reorder payload built from the page as it
    was rendered, before this request forked it) can translate them to their counterparts in
    the new draft - see `_ensure_editable_step`/`_ensure_editable_manual_check` and the
    `*_reorder` views."""
    draft = TestSuite.objects.create(
        design=design, version=(saved_suite.version + 1 if saved_suite else 1), status=TestSuite.DRAFT,
    )
    step_pk_map = {}
    manual_check_pk_map = {}
    if saved_suite is not None:
        for step in saved_suite.steps.all():
            new_step = TestStep.objects.create(
                suite=draft, order=step.order, step_type=step.step_type,
                name=step.name, abort_on_fail=step.abort_on_fail, config=step.config,
            )
            step_pk_map[step.pk] = new_step
        for check in saved_suite.manual_checks.all():
            new_check = ManualCheck.objects.create(suite=draft, order=check.order, text=check.text)
            manual_check_pk_map[check.pk] = new_check
    return draft, step_pk_map, manual_check_pk_map


def _get_or_create_draft_suite(design):
    """Every Design has at most one *draft* Test Suite at a time - the one steps/manual checks
    are actually added to/edited on (issue #110). If the highest version is already a draft,
    it's reused directly; otherwise (it's SAVED, or there's no Test Suite yet) a new draft is
    forked from it, so an already-saved version's content is never mutated in place."""
    current = design.test_suites.first()  # TestSuite.Meta.ordering = ['design', '-version']
    if current is not None and current.status == TestSuite.DRAFT:
        return current
    draft, _step_pk_map, _manual_check_pk_map = _fork_draft(design, current)
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
    _draft, step_pk_map, _manual_check_pk_map = _fork_draft(step.suite.design, step.suite)
    return step_pk_map[step.pk]


def _ensure_editable_manual_check(check):
    """Mirrors `_ensure_editable_step` for ManualCheck (issue #112) - see its docstring."""
    if check.suite.status == TestSuite.DRAFT:
        return check
    _draft, _step_pk_map, manual_check_pk_map = _fork_draft(check.suite.design, check.suite)
    return manual_check_pk_map[check.pk]


@staff_member_required
def test_suite_copy_steps_from(request, design_id):
    """Appends another Design's current (latest saved) Test Suite's steps and manual checks
    (issue #112) onto this Design's draft, at the end of each respective list. Copies from the
    source's last SAVED version specifically, not any in-progress draft it might have, so an
    unfinished edit on the source can't leak in via a copy."""
    design = get_object_or_404(Design, pk=design_id)

    if request.method == 'POST':
        form = CopyTestStepsFromForm(request.POST, exclude_design=design)
        if form.is_valid():
            source_design = form.cleaned_data['source_design']
            source_suite = source_design.test_suites.filter(status=TestSuite.SAVED).first()
            source_steps = list(source_suite.steps.all()) if source_suite else []
            source_checks = list(source_suite.manual_checks.all()) if source_suite else []

            if not source_steps and not source_checks:
                messages.warning(request, f'{source_design} has no saved test steps or manual checks to copy.')
            else:
                suite = _get_or_create_draft_suite(design)
                if source_steps:
                    last_step = suite.steps.order_by('-order').first()
                    next_order = (last_step.order + 1) if last_step else 1
                    for offset, step in enumerate(source_steps):
                        TestStep.objects.create(
                            suite=suite,
                            order=next_order + offset,
                            step_type=step.step_type,
                            name=step.name,
                            abort_on_fail=step.abort_on_fail,
                            config=step.config,
                        )
                if source_checks:
                    last_check = suite.manual_checks.order_by('-order').first()
                    next_order = (last_check.order + 1) if last_check else 1
                    for offset, check in enumerate(source_checks):
                        ManualCheck.objects.create(suite=suite, order=next_order + offset, text=check.text)
                messages.success(
                    request,
                    f'Copied {len(source_steps)} step(s) and {len(source_checks)} manual check(s) from {source_design}.',
                )
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
    suites = design.test_suites.prefetch_related('steps', 'manual_checks')
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
        'manual_checks': suite.manual_checks.all(),
        # Whether this suite is the design's single actionable "edit slot" right now (the
        # draft, or - if there's no draft - the latest saved version) - distinct from whether
        # it's the *latest saved* version, since those can diverge once a newer draft exists
        # on top of an already-saved suite (issue #110): that suite is still "Current" for
        # anyone fetching a version, but is no longer where further edits land.
        'is_highest': highest is not None and highest.pk == suite.pk,
        'is_current_saved': latest_saved is not None and latest_saved.pk == suite.pk,
        'highest': highest,
    })


# Version of the *export envelope* itself (the overall JSON shape returned by
# _serialize_test_suite - top-level keys, nesting, field names) - distinct from
# TestStep.CONFIG_SCHEMA_VERSION, which versions the shape of one step's own `config` blob and
# is carried through unchanged inside each step's `config_schema_version` below. Bump this if
# the envelope shape itself changes (e.g. a top-level key is renamed or restructured); bumping
# TestStep.CONFIG_SCHEMA_VERSION instead is what's needed when a step type's config fields
# change.
TEST_SUITE_EXPORT_SCHEMA_VERSION = 1


def _serialize_test_suite(suite):
    """Flat, external-consumer-friendly representation of a TestSuite (issue #114) - Test Steps
    and Manual Checks together, since they're versioned as one unit (see TestSuite's
    docstring). Intended to double as the shape a future Testomatic tester API endpoint
    returns (issue #101), so this is the single place that shape is defined."""
    return {
        'export_schema_version': TEST_SUITE_EXPORT_SCHEMA_VERSION,
        'design': {
            'id': suite.design.pk,
            'sku': suite.design.sku,
            'name': suite.design.name,
            'hw_version': suite.design.hw_version,
        },
        'test_suite': {
            'id': suite.pk,
            'version': suite.version,
            'status': suite.status,
            'notes': suite.notes,
            'created_dt': suite.created_dt.isoformat(),
        },
        'test_steps': [
            {
                'order': step.order,
                'step_type': step.step_type,
                'name': step.name,
                'abort_on_fail': step.abort_on_fail,
                # Pulled out alongside config rather than left for a consumer to dig out of
                # the nested blob - step.config already carries this same value under its own
                # 'schema_version' key (stamped by TestStepForm.save(), see TestStep.CONFIG_
                # SCHEMA_VERSION), so this is just a more discoverable copy of it, not a
                # separate value.
                'config_schema_version': step.config.get('schema_version'),
                'config': step.config,
            }
            for step in suite.steps.all()
        ],
        'manual_checks': [
            {'order': check.order, 'text': check.text}
            for check in suite.manual_checks.all()
        ],
    }


def build_test_suite_package_response(suite):
    """Builds the Test Suite Package (issue #114) HttpResponse for one specific TestSuite: a ZIP
    archive containing one top-level folder (named the same as the archive, minus its extension)
    holding a single test-suite-definition.json file covering both Test Steps and Manual Checks.
    Wrapping everything in a same-named folder means extracting the archive - dragging it out of
    a Downloads folder, say - can never scatter its contents loose into whatever directory it
    lands in; it always stays self-contained. The package is the transport format an external
    consumer (e.g. a Testomatic tester, or the API endpoint in testing.api - issue #116) reads;
    test-suite-definition.json's own shape is what _serialize_test_suite() defines above. The
    archive also has room for other files a step might reference by name (e.g. UPLOAD_FIRMWARE's
    firmware_file), stored in that same folder - none are attached yet, since associating
    firmware files with a Test Suite isn't designed yet.

    Shared by test_suite_download (the UI's "Download" link, which always resolves to whatever
    the design's Test Suite tab is currently showing) and testing.api's download endpoint (which
    addresses a specific suite - any version - directly by its own pk), so the archive's shape
    only exists in one place."""
    design = suite.design
    data = _serialize_test_suite(suite)
    package_name = f'{slugify(design.sku)}-hw{slugify(design.hw_version)}-test-suite-v{suite.version}'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f'{package_name}/test-suite-definition.json', json.dumps(data, indent=2))

    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{package_name}.zip"'
    return response


@staff_member_required
def test_suite_download(request, design_id):
    """Downloads the design's current Test Suite (the draft being edited, or the latest saved
    version if there's no draft - i.e. whatever the Test Suite tab is showing) as a Test Suite
    Package - see build_test_suite_package_response() above for the archive's shape."""
    design = get_object_or_404(Design, pk=design_id)
    suite = design.test_suites.first()  # TestSuite.Meta.ordering = ['design', '-version']

    if suite is None:
        messages.info(request, 'There is no Test Suite to download yet.')
        return redirect(reverse('design_detail', args=[design.pk]) + '#test-suite')

    return build_test_suite_package_response(suite)


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
            target.abort_on_fail = form.cleaned_data['abort_on_fail']
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
            suite, step_pk_map, _manual_check_pk_map = _fork_draft(design, current)
            ordered_pks = [step_pk_map[pk].pk for pk in requested_pks if pk in step_pk_map]

        steps_by_id = {step.pk: step for step in suite.steps.all()}
        for index, step_pk in enumerate(ordered_pks, start=1):
            step = steps_by_id.get(step_pk)
            if step and step.order != index:
                step.order = index
                step.save(update_fields=['order'])

    return JsonResponse({'status': 'ok'})


@staff_member_required
def manual_check_add(request, design_id):
    """Appends a new ManualCheck to the design's draft (issue #112), forking one first if
    needed - the text is taken directly from the inline "Add" row on the Design detail page,
    unlike test_step_add, which only picks a type there and fills in the rest on a follow-up
    edit page; a ManualCheck has nothing else to configure, so there's no second step."""
    design = get_object_or_404(Design, pk=design_id)

    if request.method == 'POST':
        form = ManualCheckForm(request.POST)
        if form.is_valid():
            suite = _get_or_create_draft_suite(design)
            last_check = suite.manual_checks.order_by('-order').first()
            next_order = (last_check.order + 1) if last_check else 1
            ManualCheck.objects.create(suite=suite, order=next_order, text=form.cleaned_data['text'])
            messages.success(request, 'Manual check added.')
        else:
            messages.warning(request, 'Please enter some text for the manual check.')

    return redirect(reverse('design_detail', args=[design.pk]) + '#test-suite')


@staff_member_required
def manual_check_edit(request, check_id):
    check = get_object_or_404(ManualCheck.objects.select_related('suite__design'), pk=check_id)

    if not _is_current_suite(check.suite):
        messages.warning(request, 'This manual check belongs to a historical version and can no longer be edited.')
        return redirect('testing:test_suite_version_detail', design_id=check.suite.design_id, version=check.suite.version)

    if request.method == 'POST':
        form = ManualCheckForm(request.POST, instance=check)
        if form.is_valid():
            # Validate against the original check first (harmless even when it's about to be
            # superseded by a fork); only apply the change to whichever instance is actually
            # editable, so a rejected submission never forks a version for nothing.
            target = _ensure_editable_manual_check(check)
            target.text = form.cleaned_data['text']
            target.save()
            messages.success(request, 'Manual check updated.')
            return redirect(reverse('design_detail', args=[target.suite.design_id]) + '#test-suite')
        else:
            messages.warning(request, 'Some field values have errors. Please review, and amend as required.')
    else:
        form = ManualCheckForm(instance=check)

    return render(request, 'testing/manual_check_edit.html', {'form': form, 'check': check})


@staff_member_required
def manual_check_delete(request, check_id):
    check = get_object_or_404(ManualCheck.objects.select_related('suite__design'), pk=check_id)

    if not _is_current_suite(check.suite):
        messages.warning(request, 'This manual check belongs to a historical version and can no longer be deleted.')
        return redirect('testing:test_suite_version_detail', design_id=check.suite.design_id, version=check.suite.version)

    design_id = check.suite.design_id

    if request.method == 'POST':
        target = _ensure_editable_manual_check(check)
        target.delete()
        messages.success(request, 'Manual check removed.')
        return redirect(reverse('design_detail', args=[design_id]) + '#test-suite')

    return render(request, 'testing/manual_check_delete.html', {'check': check})


@staff_member_required
def manual_check_reorder(request, design_id):
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
            suite, _step_pk_map, manual_check_pk_map = _fork_draft(design, current)
            ordered_pks = [manual_check_pk_map[pk].pk for pk in requested_pks if pk in manual_check_pk_map]

        checks_by_id = {check.pk: check for check in suite.manual_checks.all()}
        for index, check_pk in enumerate(ordered_pks, start=1):
            check = checks_by_id.get(check_pk)
            if check and check.order != index:
                check.order = index
                check.save(update_fields=['order'])

    return JsonResponse({'status': 'ok'})

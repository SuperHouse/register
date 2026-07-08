# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from device.models import Design
from .forms import CompatibleDesignAddForm, TesterForm, TestModuleForm, TestModuleTypeForm
from .models import Tester, TestModule, TestModuleType


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

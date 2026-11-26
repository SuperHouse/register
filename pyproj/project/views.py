# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
"""Staff pages for Projects (register#159). Client access comes with register#160."""
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from crm.models import Org

from .forms import ProjectDesignLinkForm, ProjectForm
from .models import Project


@staff_member_required
def project_list(request):
    projects = Project.objects.select_related('org').annotate(design_count=Count('designs'))

    q = request.GET.get('q', '').strip()
    org_id = request.GET.get('org', '')
    phase = request.GET.get('phase', '')
    # Open projects (active or on hold) unless a status is chosen; "all" shows every status.
    status = request.GET.get('status', 'open')

    if q:
        projects = projects.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(description__icontains=q))
    if org_id.isdigit():
        projects = projects.filter(org_id=int(org_id))
    if phase in dict(Project.PHASE_CHOICES):
        projects = projects.filter(phase=phase)
    if status == 'open':
        projects = projects.filter(status__in=[Project.ACTIVE, Project.ON_HOLD])
    elif status in dict(Project.STATUS_CHOICES):
        projects = projects.filter(status=status)

    ctx = {
        'projects': projects.order_by('org__company_name', '-created_dt'),
        'orgs': Org.objects.filter(projects__isnull=False).distinct().order_by('company_name'),
        'phase_choices': Project.PHASE_CHOICES,
        'status_choices': Project.STATUS_CHOICES,
        'q': q,
        'selected_org': org_id,
        'selected_phase': phase,
        'selected_status': status,
    }
    return render(request, 'project/project_list.html', ctx)


@staff_member_required
def project_add(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save()
            messages.success(request, f'Project {project.code} added.')
            return redirect('project:project_detail', project_id=project.pk)
        messages.warning(request, 'Please correct the errors below.')
    else:
        initial = {}
        org_id = request.GET.get('org', '')
        if org_id.isdigit():
            initial['org'] = int(org_id)
        form = ProjectForm(initial=initial)

    return render(request, 'project/project_edit.html', {'form': form})


@staff_member_required
def project_edit(request, project_id):
    project = get_object_or_404(Project, pk=project_id)

    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, 'Project updated.')
            return redirect('project:project_detail', project_id=project.pk)
        messages.warning(request, 'Please correct the errors below.')
    else:
        form = ProjectForm(instance=project)

    return render(request, 'project/project_edit.html', {'form': form, 'project': project})


@staff_member_required
def project_detail(request, project_id):
    project = get_object_or_404(Project.objects.select_related('org'), pk=project_id)
    ctx = {
        'project': project,
        'designs': project.designs.order_by('sku', 'hw_version'),
        'link_form': ProjectDesignLinkForm(project),
    }
    return render(request, 'project/project_detail.html', ctx)


@staff_member_required
@require_POST
def project_design_link(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    form = ProjectDesignLinkForm(project, request.POST)
    if form.is_valid():
        design = form.cleaned_data['design']
        project.designs.add(design)
        messages.success(request, f'Linked {design}.')
    else:
        messages.warning(request, 'Choose one of this organisation’s designs to link.')
    return redirect('project:project_detail', project_id=project.pk)


@staff_member_required
@require_POST
def project_design_unlink(request, project_id, design_id):
    project = get_object_or_404(Project, pk=project_id)
    design = get_object_or_404(project.designs, pk=design_id)
    project.designs.remove(design)
    messages.success(request, f'Unlinked {design}.')
    return redirect('project:project_detail', project_id=project.pk)

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
"""Project pages (register#159, #160).

Staff users see every project and can add, edit and link designs. A customer user can view the
list and the detail page of their own orgs' projects only, read-only.
"""
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from erp.models import Batch

from .forms import ProjectDesignLinkForm, ProjectForm, ProjectLogEntryForm
from .models import Project, ProjectLogEntry


def _projects_for_user(user):
    """Every project for staff; otherwise only projects of the user's own orgs."""
    if user.is_staff:
        return Project.objects.all()
    return Project.objects.filter(org__users=user).distinct()


def project_list(request):
    visible = _projects_for_user(request.user)
    projects = visible.select_related('org').annotate(design_count=Count('designs', distinct=True))

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
        # Only orgs that have a project the user can see; hidden when there is just one.
        'orgs': sorted({p.org for p in visible.select_related('org')}, key=lambda org: org.company_name),
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


def project_detail(request, project_id):
    # Another org's project is a 404 for a customer user, so its existence is not confirmed.
    project = get_object_or_404(_projects_for_user(request.user).select_related('org'), pk=project_id)
    designs = project.designs.order_by('sku', 'hw_version')
    # Prototype (and later) builds: every batch of the linked designs. A design shared with
    # another project shows its batches on both (register#160 chose not to add Batch.project yet).
    batches = (
        Batch.objects.filter(design__in=designs)
        .select_related('design')
        .prefetch_related('production_stages')
        .order_by('-created_dt')
    )
    # Log entries (register#161). visible_to() hides internal entries from client users, and
    # every count below is taken from it, so a count cannot reveal an internal entry either.
    log_entries = ProjectLogEntry.visible_to(request.user, project).select_related('created_by_user')
    decisions = log_entries.filter(kind=ProjectLogEntry.DECISION)
    log_view = 'decisions' if request.GET.get('log') == 'decisions' else 'all'
    ctx = {
        'project': project,
        'designs': designs,
        'batches': batches,
        'link_form': ProjectDesignLinkForm(project) if request.user.is_staff else None,
        'log_view': log_view,
        'log_entries': decisions if log_view == 'decisions' else log_entries,
        'log_entry_count': log_entries.count(),
        'decision_count': decisions.count(),
        'log_form': ProjectLogEntryForm() if request.user.is_staff else None,
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
        messages.warning(request, 'Choose one of this client’s designs to link.')
    return redirect('project:project_detail', project_id=project.pk)


@staff_member_required
@require_POST
def project_design_unlink(request, project_id, design_id):
    project = get_object_or_404(Project, pk=project_id)
    design = get_object_or_404(project.designs, pk=design_id)
    project.designs.remove(design)
    messages.success(request, f'Unlinked {design}.')
    return redirect('project:project_detail', project_id=project.pk)


def _log_redirect(entry_or_project):
    project = getattr(entry_or_project, 'project', entry_or_project)
    return redirect(reverse('project:project_detail', args=[project.pk]) + '#log')


@staff_member_required
@require_POST
def project_log_add(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    form = ProjectLogEntryForm(request.POST)
    if form.is_valid():
        entry = form.save(commit=False)
        entry.project = project
        entry.set_creator(user=request.user)
        entry.save()
        messages.success(request, f'{entry.get_kind_display()} added to the log.')
    else:
        errors = '; '.join(f'{form.fields[f].label}: {" ".join(e)}' for f, e in form.errors.items())
        messages.warning(request, f'The log entry was not added. {errors}')
    return _log_redirect(project)


@staff_member_required
def project_log_edit(request, entry_id):
    entry = get_object_or_404(ProjectLogEntry.objects.select_related('project'), pk=entry_id)
    if request.method == 'POST':
        form = ProjectLogEntryForm(request.POST, instance=entry)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.updated_dt = timezone.now()
            entry.save()
            messages.success(request, 'Log entry updated.')
            return _log_redirect(entry)
        messages.warning(request, 'Please correct the errors below.')
    else:
        form = ProjectLogEntryForm(instance=entry)
    return render(request, 'project/project_log_edit.html', {'form': form, 'entry': entry, 'project': entry.project})


@staff_member_required
@require_POST
def project_log_delete(request, entry_id):
    entry = get_object_or_404(ProjectLogEntry.objects.select_related('project'), pk=entry_id)
    entry.delete()
    messages.success(request, 'Log entry deleted.')
    return _log_redirect(entry)

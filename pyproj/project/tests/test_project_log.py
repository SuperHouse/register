# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
"""register#161: project log entries, internal by default, with a Decisions view."""
import datetime
import re

import pytest
from django.urls import reverse
from django.utils import timezone

from crm.models import Org
from device.models import Design
from project.models import Project, ProjectLogEntry
from project.templatetags.project_tags import markdown

INTERNAL_MARKER = 'INTERNAL-ONLY-MARKER'


@pytest.fixture
def data(django_user_model):
    org = Org.objects.create(company_name='Log Client')
    customer = django_user_model.objects.create_user(email='logcustomer@example.com', password='x')
    org.users.add(customer)
    staff = django_user_model.objects.create_user(email='logstaff@example.com', password='x',
                                                  is_staff=True, full_name='Staff Person')
    design = Design.objects.create(client=org, sku='LOG1', name='Log Board', hw_version='1.0')
    project = Project.objects.create(org=org, name='Logged Project')
    project.designs.add(design)
    return {'org': org, 'customer': customer, 'staff': staff, 'design': design, 'project': project}


def _entry(project, body, kind=ProjectLogEntry.NOTE, client_visible=False, **kwargs):
    return ProjectLogEntry.objects.create(project=project, body=body, kind=kind,
                                          client_visible=client_visible, **kwargs)


def _detail(client, project, **params):
    return client.get(reverse('project:project_detail', args=[project.pk]), params).content.decode()


# --- Model ---

@pytest.mark.django_db
def test_entry_is_internal_by_default(data):
    entry = ProjectLogEntry.objects.create(project=data['project'], body='x')
    assert entry.client_visible is False
    assert entry.kind == ProjectLogEntry.NOTE
    assert entry.date == timezone.localdate()


@pytest.mark.django_db
def test_visible_to(data):
    shown = _entry(data['project'], 'shown', client_visible=True)
    hidden = _entry(data['project'], 'hidden')
    assert set(ProjectLogEntry.visible_to(data['staff'], data['project'])) == {shown, hidden}
    assert list(ProjectLogEntry.visible_to(data['customer'], data['project'])) == [shown]
    assert list(ProjectLogEntry.visible_to(data['customer'])) == [shown]


@pytest.mark.django_db
def test_entries_newest_date_first(data):
    old = _entry(data['project'], 'old', date=datetime.date(2026, 1, 1))
    new = _entry(data['project'], 'new', date=datetime.date(2026, 6, 1))
    assert list(data['project'].log_entries.all()) == [new, old]


# --- Markdown ---

def test_markdown_renders_basic_formatting():
    html = markdown('**bold** and *italic*\n\n- one\n- two')
    assert '<strong>bold</strong>' in html
    assert '<em>italic</em>' in html
    assert '<li>one</li>' in html


def test_markdown_escapes_raw_html_and_script_links():
    html = markdown('<script>alert(1)</script> <img src=x onerror=alert(1)> [x](javascript:alert(1))')
    assert '<script>' not in html
    assert '<img' not in html
    assert 'href="javascript:' not in html


# --- Staff add, edit, delete ---

@pytest.mark.django_db
def test_staff_can_add_entry(client, data):
    client.force_login(data['staff'])
    response = client.post(reverse('project:project_log_add', args=[data['project'].pk]), {
        'date': '2026-11-20', 'kind': ProjectLogEntry.DECISION, 'body': 'Use the **STM32**.',
    })
    assert response.status_code == 302
    assert response.url.endswith('#log')
    entry = data['project'].log_entries.get()
    assert entry.kind == ProjectLogEntry.DECISION
    assert entry.client_visible is False  # unticked checkbox
    assert entry.created_by_user == data['staff']
    assert '<strong>STM32</strong>' in _detail(client, data['project'])


@pytest.mark.django_db
def test_add_without_body_is_rejected(client, data):
    client.force_login(data['staff'])
    client.post(reverse('project:project_log_add', args=[data['project'].pk]),
                {'date': '2026-11-20', 'kind': ProjectLogEntry.NOTE, 'body': ''})
    assert not data['project'].log_entries.exists()


@pytest.mark.django_db
def test_staff_can_edit_entry(client, data):
    entry = _entry(data['project'], 'before')
    client.force_login(data['staff'])
    assert client.get(reverse('project:project_log_edit', args=[entry.pk])).status_code == 200
    response = client.post(reverse('project:project_log_edit', args=[entry.pk]), {
        'date': '2026-11-21', 'kind': ProjectLogEntry.MEETING, 'body': 'after', 'client_visible': 'on',
    })
    assert response.status_code == 302
    entry.refresh_from_db()
    assert (entry.body, entry.kind, entry.client_visible) == ('after', ProjectLogEntry.MEETING, True)
    assert entry.updated_dt is not None
    assert entry.created_by_user is None  # editing does not change who added it


@pytest.mark.django_db
def test_staff_can_delete_entry(client, data):
    entry = _entry(data['project'], 'doomed')
    client.force_login(data['staff'])
    assert client.get(reverse('project:project_log_delete', args=[entry.pk])).status_code == 405
    client.post(reverse('project:project_log_delete', args=[entry.pk]))
    assert not ProjectLogEntry.objects.filter(pk=entry.pk).exists()


@pytest.mark.django_db
def test_customer_cannot_add_edit_or_delete(client, data):
    entry = _entry(data['project'], 'shared', client_visible=True)
    client.force_login(data['customer'])
    client.post(reverse('project:project_log_add', args=[data['project'].pk]),
                {'date': '2026-11-20', 'kind': ProjectLogEntry.NOTE, 'body': 'from client'})
    client.post(reverse('project:project_log_edit', args=[entry.pk]),
                {'date': '2026-11-20', 'kind': ProjectLogEntry.NOTE, 'body': 'changed'})
    client.post(reverse('project:project_log_delete', args=[entry.pk]))
    entry.refresh_from_db()
    assert entry.body == 'shared'
    assert data['project'].log_entries.count() == 1


@pytest.mark.django_db
def test_customer_page_has_no_log_controls(client, data):
    entry = _entry(data['project'], 'shared', client_visible=True)
    client.force_login(data['customer'])
    content = _detail(client, data['project'])
    assert 'shared' in content
    assert reverse('project:project_log_add', args=[data['project'].pk]) not in content
    assert reverse('project:project_log_edit', args=[entry.pk]) not in content
    assert 'Staff Person' not in content


# --- Decisions view ---

@pytest.mark.django_db
def test_decisions_view_shows_only_decisions(client, data):
    _entry(data['project'], 'a plain note')
    _entry(data['project'], 'we chose USB-C', kind=ProjectLogEntry.DECISION)
    client.force_login(data['staff'])
    content = _detail(client, data['project'], log='decisions')
    assert 'we chose USB-C' in content
    assert 'a plain note' not in content
    assert 'a plain note' in _detail(client, data['project'])


# --- Internal entries never reach a client user ---

def _counts(content):
    """The two counts shown on the log tabs: (all entries, decisions)."""
    return tuple(int(n) for n in re.findall(r'(?:All entries|Decisions) <span class="badge[^"]*">(\d+)</span>', content))


@pytest.mark.django_db
def test_internal_entries_and_counts_hidden_from_customer(client, data):
    _entry(data['project'], 'visible note', client_visible=True)
    _entry(data['project'], 'visible decision', kind=ProjectLogEntry.DECISION, client_visible=True)
    _entry(data['project'], f'{INTERNAL_MARKER} note')
    _entry(data['project'], f'{INTERNAL_MARKER} decision', kind=ProjectLogEntry.DECISION)

    client.force_login(data['staff'])
    assert _counts(_detail(client, data['project'])) == (4, 2)

    client.force_login(data['customer'])
    for params in ({}, {'log': 'decisions'}):
        content = _detail(client, data['project'], **params)
        assert INTERNAL_MARKER not in content
        assert _counts(content) == (2, 1)


@pytest.mark.django_db
def test_internal_entries_absent_from_every_customer_page(client, data):
    """Sweep every page a customer can reach that shows project data. A page added later that
    shows log entries should be added to this list."""
    _entry(data['project'], f'{INTERNAL_MARKER} body', kind=ProjectLogEntry.DECISION)
    client.force_login(data['customer'])
    urls = [
        reverse('dashboard'),
        reverse('project:project_list'),
        reverse('project:project_list') + '?status=all',
        reverse('project:project_detail', args=[data['project'].pk]),
        reverse('project:project_detail', args=[data['project'].pk]) + '?log=decisions',
        reverse('design_detail', args=[data['design'].pk]),
        '/api/v1/dashboard-stats/',
    ]
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, url
        assert INTERNAL_MARKER not in response.content.decode(), url

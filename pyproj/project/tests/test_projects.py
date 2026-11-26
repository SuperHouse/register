# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
"""register#159: Project model and staff pages."""
import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from crm.models import Org
from device.models import Design
from project.forms import ProjectForm
from project.models import Project


@pytest.fixture
def data(django_user_model):
    org1 = Org.objects.create(company_name='Project Org One', is_client=True)
    org2 = Org.objects.create(company_name='Project Org Two', is_client=True)
    customer = django_user_model.objects.create_user(email='customer@example.com', password='x')
    org1.users.add(customer)
    staff = django_user_model.objects.create_user(email='staff@example.com', password='x', is_staff=True)
    design1 = Design.objects.create(client=org1, sku='PO1', name='Org One Board', hw_version='1.0')
    design1b = Design.objects.create(client=org1, sku='PO1', name='Org One Board', hw_version='2.0')
    design2 = Design.objects.create(client=org2, sku='PO2', name='Org Two Board', hw_version='1.0')
    return {
        'org1': org1, 'org2': org2, 'customer': customer, 'staff': staff,
        'design1': design1, 'design1b': design1b, 'design2': design2,
    }


# --- Model ---

@pytest.mark.django_db
def test_code_is_assigned_per_year(data):
    year = timezone.localtime().year
    p1 = Project.objects.create(org=data['org1'], name='First')
    p2 = Project.objects.create(org=data['org1'], name='Second')
    assert p1.code == f'P-{year}-001'
    assert p2.code == f'P-{year}-002'


@pytest.mark.django_db
def test_code_numbering_restarts_each_year(data):
    last_year = timezone.now() - datetime.timedelta(days=400)
    old = Project.objects.create(org=data['org1'], name='Old', created_dt=last_year)
    new = Project.objects.create(org=data['org1'], name='New')
    assert old.code == f'P-{timezone.localtime(last_year).year}-001'
    assert new.code == f'P-{timezone.localtime().year}-001'


@pytest.mark.django_db
def test_code_does_not_change_on_save(data):
    project = Project.objects.create(org=data['org1'], name='Stable')
    code = project.code
    project.name = 'Renamed'
    project.save()
    project.refresh_from_db()
    assert project.code == code


@pytest.mark.django_db
def test_code_skips_numbers_already_used(data):
    year = timezone.localtime().year
    p1 = Project.objects.create(org=data['org1'], name='One')
    Project.objects.filter(pk=p1.pk).update(code=f'P-{year}-007')
    p2 = Project.objects.create(org=data['org1'], name='Two')
    assert p2.code == f'P-{year}-008'


@pytest.mark.django_db
def test_defaults_and_design_links_both_ways(data):
    project = Project.objects.create(org=data['org1'], name='Defaults')
    assert project.phase == Project.ENQUIRY
    assert project.status == Project.ACTIVE
    other = Project.objects.create(org=data['org1'], name='Follow-on')
    project.designs.add(data['design1'])
    other.designs.add(data['design1'])
    assert set(data['design1'].projects.all()) == {project, other}


# --- Form ---

@pytest.mark.django_db
def test_form_rejects_target_before_start(data):
    form = ProjectForm(data={
        'org': data['org1'].pk, 'name': 'Dates', 'phase': Project.ENQUIRY, 'status': Project.ACTIVE,
        'start_date': '2026-12-01', 'target_date': '2026-11-01',
    })
    assert not form.is_valid()
    assert 'target_date' in form.errors


@pytest.mark.django_db
def test_form_offers_only_client_orgs(data):
    supplier = Org.objects.create(company_name='Just A Supplier', is_client=False, is_supplier=True)
    form = ProjectForm()
    assert supplier not in form.fields['org'].queryset
    assert data['org1'] in form.fields['org'].queryset


@pytest.mark.django_db
def test_form_blocks_org_change_while_designs_linked(data):
    project = Project.objects.create(org=data['org1'], name='Move me')
    project.designs.add(data['design1'])
    form = ProjectForm(instance=project, data={
        'org': data['org2'].pk, 'name': 'Move me', 'phase': Project.ENQUIRY, 'status': Project.ACTIVE,
    })
    assert not form.is_valid()
    assert 'org' in form.errors


# --- Staff pages ---

@pytest.mark.django_db
def test_staff_can_add_project(client, data):
    client.force_login(data['staff'])
    response = client.post(reverse('project:project_add'), {
        'org': data['org1'].pk, 'name': 'New Widget', 'description': 'R&D for a widget',
        'phase': Project.DESIGN, 'status': Project.ACTIVE, 'start_date': '2026-11-01', 'target_date': '',
    })
    project = Project.objects.get(name='New Widget')
    assert response.status_code == 302
    assert response.url == reverse('project:project_detail', args=[project.pk])
    assert project.phase == Project.DESIGN
    assert project.start_date == datetime.date(2026, 11, 1)
    assert project.target_date is None


@pytest.mark.django_db
def test_staff_can_edit_project(client, data):
    project = Project.objects.create(org=data['org1'], name='Before')
    client.force_login(data['staff'])
    response = client.post(reverse('project:project_edit', args=[project.pk]), {
        'org': data['org1'].pk, 'name': 'After', 'phase': Project.PROTOTYPING, 'status': Project.ON_HOLD,
    })
    assert response.status_code == 302
    project.refresh_from_db()
    assert (project.name, project.phase, project.status) == ('After', Project.PROTOTYPING, Project.ON_HOLD)


@pytest.mark.django_db
def test_list_filters(client, data):
    Project.objects.create(org=data['org1'], name='Alpha Active', phase=Project.DESIGN)
    Project.objects.create(org=data['org1'], name='Bravo Paused', phase=Project.PROTOTYPING, status=Project.ON_HOLD)
    Project.objects.create(org=data['org2'], name='Charlie Closed', status=Project.CLOSED)
    client.force_login(data['staff'])
    url = reverse('project:project_list')

    content = client.get(url).content.decode()
    assert 'Alpha Active' in content and 'Bravo Paused' in content
    assert 'Charlie Closed' not in content  # open projects by default

    content = client.get(url, {'status': 'all'}).content.decode()
    assert 'Charlie Closed' in content

    content = client.get(url, {'status': 'all', 'org': data['org2'].pk}).content.decode()
    assert 'Charlie Closed' in content and 'Alpha Active' not in content

    content = client.get(url, {'phase': Project.PROTOTYPING}).content.decode()
    assert 'Bravo Paused' in content and 'Alpha Active' not in content

    content = client.get(url, {'q': 'alpha'}).content.decode()
    assert 'Alpha Active' in content and 'Bravo Paused' not in content


@pytest.mark.django_db
def test_detail_page_shows_project_and_designs(client, data):
    project = Project.objects.create(org=data['org1'], name='Shown')
    project.designs.add(data['design1'])
    client.force_login(data['staff'])
    content = client.get(reverse('project:project_detail', args=[project.pk])).content.decode()
    assert project.code in content
    assert reverse('design_detail', args=[data['design1'].pk]) in content


@pytest.mark.django_db
def test_link_and_unlink_design(client, data):
    project = Project.objects.create(org=data['org1'], name='Links')
    client.force_login(data['staff'])
    client.post(reverse('project:project_design_link', args=[project.pk]), {'design': data['design1b'].pk})
    assert list(project.designs.all()) == [data['design1b']]
    client.post(reverse('project:project_design_unlink', args=[project.pk, data['design1b'].pk]))
    assert not project.designs.exists()
    assert Design.objects.filter(pk=data['design1b'].pk).exists()


@pytest.mark.django_db
def test_cannot_link_another_orgs_design(client, data):
    project = Project.objects.create(org=data['org1'], name='No cross-org')
    client.force_login(data['staff'])
    client.post(reverse('project:project_design_link', args=[project.pk]), {'design': data['design2'].pk})
    assert not project.designs.exists()


@pytest.mark.django_db
def test_link_requires_post(client, data):
    project = Project.objects.create(org=data['org1'], name='Get')
    client.force_login(data['staff'])
    response = client.get(reverse('project:project_design_link', args=[project.pk]))
    assert response.status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize('name, kwargs', [
    ('project:project_add', {}),
    ('project:project_edit', {'project_id': 'PK'}),
])
def test_customer_cannot_use_staff_pages(client, data, name, kwargs):
    project = Project.objects.create(org=data['org1'], name='Their own project')
    kwargs = {k: project.pk if v == 'PK' else v for k, v in kwargs.items()}
    client.force_login(data['customer'])
    response = client.get(reverse(name, kwargs=kwargs))
    assert response.status_code == 302
    assert 'Their own project' not in response.content.decode()

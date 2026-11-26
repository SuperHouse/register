# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
"""register#160: customer users see their own orgs' projects, read-only."""
import pytest
from django.urls import reverse

from crm.models import BrandedHost, Org
from device.models import Design
from erp.models import Batch
from project.models import Project


@pytest.fixture
def data(django_user_model):
    org1 = Org.objects.create(company_name='Client One')
    org2 = Org.objects.create(company_name='Client Two')
    user1 = django_user_model.objects.create_user(email='one@example.com', password='x')
    org1.users.add(user1)
    staff = django_user_model.objects.create_user(email='staff@example.com', password='x', is_staff=True)
    design1 = Design.objects.create(client=org1, sku='C1', name='One Board', hw_version='1.0')
    design2 = Design.objects.create(client=org2, sku='C2', name='Two Board', hw_version='1.0')
    project1 = Project.objects.create(org=org1, name='Widget R&D', phase=Project.PROTOTYPING)
    project1.designs.add(design1)
    project2 = Project.objects.create(org=org2, name='Secret Gadget')
    project2.designs.add(design2)
    return {
        'org1': org1, 'org2': org2, 'user1': user1, 'staff': staff,
        'design1': design1, 'design2': design2, 'project1': project1, 'project2': project2,
    }


@pytest.mark.django_db
def test_sidebar_shows_projects_to_customers(client, data):
    client.force_login(data['user1'])
    content = client.get(reverse('dashboard')).content.decode()
    assert reverse('project:project_list') in content


@pytest.mark.django_db
def test_customer_list_shows_only_own_projects(client, data):
    client.force_login(data['user1'])
    response = client.get(reverse('project:project_list'))
    content = response.content.decode()
    assert response.status_code == 200
    assert 'Widget R&amp;D' in content
    assert data['project1'].code in content
    assert 'Secret Gadget' not in content
    # No Add button, and no org filter or column for a single-org user.
    assert reverse('project:project_add') not in content
    assert 'All organisations' not in content


@pytest.mark.django_db
def test_customer_list_ignores_another_orgs_filter(client, data):
    client.force_login(data['user1'])
    content = client.get(reverse('project:project_list'), {'org': data['org2'].pk}).content.decode()
    assert 'Secret Gadget' not in content


@pytest.mark.django_db
def test_customer_in_two_orgs_gets_org_filter(client, data):
    data['org2'].users.add(data['user1'])
    client.force_login(data['user1'])
    content = client.get(reverse('project:project_list')).content.decode()
    assert 'Secret Gadget' in content
    assert 'All organisations' in content


@pytest.mark.django_db
def test_customer_sees_own_project_page_read_only(client, data):
    client.force_login(data['user1'])
    project = data['project1']
    response = client.get(reverse('project:project_detail', args=[project.pk]))
    content = response.content.decode()
    assert response.status_code == 200
    assert project.code in content
    assert 'Prototyping' in content
    assert reverse('design_detail', args=[data['design1'].pk]) in content
    assert reverse('project:project_edit', args=[project.pk]) not in content
    assert reverse('project:project_design_link', args=[project.pk]) not in content
    assert reverse('project:project_design_unlink', args=[project.pk, data['design1'].pk]) not in content
    assert reverse('organisation_detail', args=[data['org1'].pk]) not in content


@pytest.mark.django_db
def test_customer_gets_404_for_another_orgs_project(client, data):
    client.force_login(data['user1'])
    response = client.get(reverse('project:project_detail', args=[data['project2'].pk]))
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize('name', ['project:project_design_link', 'project:project_design_unlink'])
def test_customer_cannot_link_or_unlink(client, data, name):
    project = data['project1']
    args = [project.pk] if name.endswith('_link') else [project.pk, data['design1'].pk]
    client.force_login(data['user1'])
    response = client.post(reverse(name, args=args), {'design': data['design1'].pk})
    assert response.status_code == 302
    assert list(project.designs.all()) == [data['design1']]


@pytest.mark.django_db
def test_project_page_lists_batches_of_linked_designs(client, data):
    Batch.objects.create(design=data['design1'], quantity=5, po='PO-PROTO-1')
    Batch.objects.create(design=data['design2'], quantity=9, po='PO-OTHER')
    client.force_login(data['user1'])
    content = client.get(reverse('project:project_detail', args=[data['project1'].pk])).content.decode()
    assert 'PO-PROTO-1' in content
    assert 'PO-OTHER' not in content


@pytest.mark.django_db
def test_shared_design_batches_show_on_both_projects(client, data):
    follow_on = Project.objects.create(org=data['org1'], name='Widget v2')
    follow_on.designs.add(data['design1'])
    Batch.objects.create(design=data['design1'], quantity=3, po='PO-SHARED')
    client.force_login(data['user1'])
    for project in (data['project1'], follow_on):
        content = client.get(reverse('project:project_detail', args=[project.pk])).content.decode()
        assert 'PO-SHARED' in content


@pytest.mark.django_db
def test_design_page_lists_own_projects_for_customer(client, data):
    # A project of another org linked through the admin must not show.
    data['project2'].designs.add(data['design1'])
    client.force_login(data['user1'])
    content = client.get(reverse('design_detail', args=[data['design1'].pk])).content.decode()
    assert 'Widget R&amp;D' in content
    assert 'Secret Gadget' not in content


@pytest.mark.django_db
def test_design_page_has_no_projects_line_for_customer_without_projects(client, data):
    design = Design.objects.create(client=data['org1'], sku='C1X', name='Loose Board', hw_version='1.0')
    client.force_login(data['user1'])
    content = client.get(reverse('design_detail', args=[design.pk])).content.decode()
    assert 'id="design-projects"' not in content


@pytest.mark.django_db
def test_design_page_projects_line_for_staff(client, data):
    client.force_login(data['staff'])
    content = client.get(reverse('design_detail', args=[data['design1'].pk])).content.decode()
    assert 'Widget R&amp;D' in content


@pytest.mark.django_db
def test_branded_host_does_not_change_scoping(client, data, settings):
    settings.ALLOWED_HOSTS = ['serials.example.com', 'testserver']
    BrandedHost.objects.create(hostname='serials.example.com', org=data['org2'], logo='branding/x.png')
    client.force_login(data['user1'])
    content = client.get(reverse('project:project_list'), HTTP_HOST='serials.example.com').content.decode()
    assert 'Widget R&amp;D' in content
    assert 'Secret Gadget' not in content
    response = client.get(reverse('project:project_detail', args=[data['project2'].pk]), HTTP_HOST='serials.example.com')
    assert response.status_code == 404

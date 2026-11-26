# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
"""Org.is_client ("Client"): editable on the Organisation edit page, and an org that is not a
client is left out of selection lists while its data stays."""
import pytest
from django.urls import reverse

from crm.forms import UserForm
from crm.models import Org
from device.forms import DesignAddForm
from device.models import Design
from project.forms import ProjectForm
from project.models import Project


@pytest.fixture
def orgs(django_user_model):
    current = Org.objects.create(company_name='Current Co')
    former = Org.objects.create(company_name='Former Co', is_client=False)
    staff = django_user_model.objects.create_user(email='staff@example.com', password='x', is_staff=True)
    return {'current': current, 'former': former, 'staff': staff}


@pytest.mark.django_db
def test_new_org_is_a_client_by_default():
    assert Org.objects.create(company_name='New Co').is_client


@pytest.mark.django_db
def test_edit_page_can_untick_and_retick_current_client(client, orgs):
    org = orgs['current']
    client.force_login(orgs['staff'])
    url = reverse('organisation_edit', args=[org.pk])
    assert 'do client work for' in client.get(url).content.decode()

    client.post(url, {'company_name': org.company_name})  # unticked: not sent
    org.refresh_from_db()
    assert not org.is_client

    client.post(url, {'company_name': org.company_name, 'is_client': 'on'})
    org.refresh_from_db()
    assert org.is_client


@pytest.mark.django_db
def test_org_list_badges_clients(client, orgs):
    client.force_login(orgs['staff'])
    content = client.get(reverse('organisation_list')).content.decode()
    assert 'Former Co' in content
    assert content.count('>Client</span>') == 1
    assert 'Former client' not in content


@pytest.mark.django_db
def test_org_can_be_saved_with_no_users(client, orgs):
    org = orgs['current']
    client.force_login(orgs['staff'])
    response = client.post(reverse('organisation_edit', args=[org.pk]),
                           {'company_name': 'Renamed Co', 'is_client': 'on'})
    assert response.status_code == 302
    org.refresh_from_db()
    assert org.company_name == 'Renamed Co'
    assert not org.users.exists()


@pytest.mark.django_db
def test_dashboard_client_count_includes_only_clients(client, orgs, django_user_model):
    client.force_login(orgs['staff'])
    assert client.get(reverse('dashboard')).context['client_count'] == 1
    assert client.get('/api/v1/dashboard-stats/').json()['client_count'] == 1


@pytest.mark.django_db
def test_dashboard_non_client_org_still_scopes_customer_data(client, orgs, django_user_model):
    """A member of a non-client org still sees that org's boards counted; only client_count drops it."""
    user = django_user_model.objects.create_user(email='member@example.com', password='x')
    orgs['former'].users.add(user)
    Design.objects.create(client=orgs['former'], sku='OLD', name='Old Board', hw_version='1.0')
    Design.objects.create(client=orgs['current'], sku='NEW', name='New Board', hw_version='1.0')
    client.force_login(user)
    context = client.get(reverse('dashboard')).context
    assert context['client_count'] == 0
    assert context['design_count'] == 1


@pytest.mark.django_db
def test_design_add_form_leaves_out_former_clients(orgs):
    queryset = DesignAddForm().fields['client'].queryset
    assert orgs['current'] in queryset
    assert orgs['former'] not in queryset


@pytest.mark.django_db
def test_project_form_leaves_out_former_clients_except_current_org(orgs):
    assert orgs['former'] not in ProjectForm().fields['org'].queryset
    project = Project.objects.create(org=orgs['former'], name='Old job')
    assert orgs['former'] in ProjectForm(instance=project).fields['org'].queryset


@pytest.mark.django_db
def test_user_form_keeps_existing_former_client_membership(django_user_model, orgs):
    user = django_user_model.objects.create_user(email='member@example.com', password='x')
    assert orgs['former'] not in UserForm().fields['orgs'].queryset

    orgs['former'].users.add(user)
    form = UserForm(instance=user)
    assert orgs['former'] in form.fields['orgs'].queryset

    # Saving the user with the membership still selected keeps it.
    form = UserForm(instance=user, data={
        'email': user.email, 'full_name': 'Member', 'preferred_name': '', 'is_active': 'on',
        'orgs': [orgs['former'].pk, orgs['current'].pk],
    })
    assert form.is_valid(), form.errors
    form.save()
    assert set(user.org_set.all()) == {orgs['former'], orgs['current']}


@pytest.mark.django_db
def test_former_client_keeps_its_data(client, orgs):
    design = Design.objects.create(client=orgs['former'], sku='OLD', name='Old Board', hw_version='1.0')
    client.force_login(orgs['staff'])
    assert client.get(reverse('design_detail', args=[design.pk])).status_code == 200
    assert 'Old Board' in client.get(reverse('organisation_detail', args=[orgs['former'].pk])).content.decode()

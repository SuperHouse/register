# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.urls import reverse
import pytest

from crm.models import Org
from device.models import Design


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)


@pytest.fixture
def orgs():
    beta = Org.objects.create(company_name='Beta Org')
    alpha = Org.objects.create(company_name='Alpha Org')
    Design.objects.create(client=beta, sku='B1', name='Beta Board', hw_version='1')
    Design.objects.create(client=alpha, sku='A2', name='Alpha Old', hw_version='1', obsolete=True)
    Design.objects.create(client=alpha, sku='A3', name='Alpha New', hw_version='1')
    return alpha, beta


def _groups(response):
    return [(g['org'].company_name, [d.sku for d in g['designs']], g['is_expanded'])
            for g in response.context['org_groups']]


@pytest.mark.django_db
def test_designs_grouped_by_org_collapsed_by_default(client, staff_user, orgs):
    client.force_login(staff_user)
    response = client.get(reverse('design_list'))

    # Orgs alphabetical; obsolete designs last within their org.
    assert _groups(response) == [
        ('Alpha Org', ['A3', 'A2'], False),
        ('Beta Org', ['B1'], False),
    ]
    content = response.content.decode()
    assert '<th>Organisation</th>' not in content
    assert 'Alpha Org (2)' in content


@pytest.mark.django_db
def test_toggle_persists_expanded_org(client, staff_user, orgs):
    alpha, beta = orgs
    client.force_login(staff_user)

    client.post(reverse('design_org_toggle_collapse'), {'category': str(beta.pk), 'expanded': 'true'})
    assert [g[2] for g in _groups(client.get(reverse('design_list')))] == [False, True]

    client.post(reverse('design_org_toggle_collapse'), {'category': str(beta.pk), 'expanded': 'false'})
    assert [g[2] for g in _groups(client.get(reverse('design_list')))] == [False, False]


@pytest.mark.django_db
def test_filter_expands_matching_groups_without_persisting(client, staff_user, orgs):
    client.force_login(staff_user)

    response = client.get(reverse('design_list'), {'q': 'Board'})
    assert _groups(response) == [('Beta Org', ['B1'], True)]

    assert [g[2] for g in _groups(client.get(reverse('design_list')))] == [False, False]


@pytest.mark.django_db
def test_single_org_non_staff_user_sees_group_expanded(client, django_user_model, orgs):
    alpha, beta = orgs
    user = django_user_model.objects.create_user(email='client@example.com', password='clienty')
    alpha.users.add(user)

    client.force_login(user)
    response = client.get(reverse('design_list'))

    assert _groups(response) == [('Alpha Org', ['A3', 'A2'], True)]

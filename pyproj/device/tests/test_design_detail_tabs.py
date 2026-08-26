# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
"""Issue #102: the Design detail page is split into Details/Bill of Materials/Test Suite/
Boards tabs, with the Test Suite tab replacing the old standalone testing:test_suite_current
page. See testing/tests/test_test_suites_views.py for the Test Suite tab's own POST actions
(add/edit/delete/reorder a step, save a new version, copy from another design) - these tests
cover the Design detail page's tab structure and staff/non-staff visibility only."""
import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from crm.models import Org
from device.models import Design, DesignAsset
from testing.models import TestStep, TestSuite


@pytest.fixture
def design():
    org = Org.objects.create(company_name='Tabs Test Org')
    return Design.objects.create(client=org, sku='TABS1', name='Tabs Test Design', hw_version='1.0')


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(email='tabs-staff@example.com', password='staffy', is_staff=True)


@pytest.fixture
def plain_user(django_user_model, design):
    user = django_user_model.objects.create_user(email='tabs-plain@example.com', password='plainy')
    design.client.users.add(user)
    return user


@pytest.mark.django_db
def test_staff_sees_all_four_tabs(client, staff_user, design):
    client.force_login(staff_user)
    content = client.get(reverse('design_detail', args=[design.pk])).content.decode()

    assert '>Details<' in content
    assert '>Bill of Materials<' in content
    assert '>Test Suite<' in content
    assert '>Boards<' in content


@pytest.mark.django_db
def test_details_tab_is_active_by_default(client, staff_user, design):
    client.force_login(staff_user)
    content = client.get(reverse('design_detail', args=[design.pk])).content.decode()

    details_link_tag = content.split('id="tab-details"')[0].rsplit('<a', 1)[1]
    assert 'active' in details_link_tag
    details_pane_open_tag = content.split('id="pane-details"')[0].rsplit('<div', 1)[1]
    assert 'active' in details_pane_open_tag


@pytest.mark.django_db
def test_non_staff_without_firmware_asset_sees_only_details_and_boards(client, plain_user, design):
    client.force_login(plain_user)
    content = client.get(reverse('design_detail', args=[design.pk])).content.decode()

    assert '>Details<' in content
    assert '>Boards<' in content
    assert '>Bill of Materials<' not in content
    assert '>Test Suite<' not in content


@pytest.mark.django_db
def test_non_staff_with_firmware_asset_sees_test_suite_tab_but_not_step_management(client, plain_user, design):
    firmware = DesignAsset(design=design, name='fw', asset_type=DesignAsset.FIRMWARE)
    firmware.file.save('firmware.bin', ContentFile(b'binary'), save=True)

    client.force_login(plain_user)
    content = client.get(reverse('design_detail', args=[design.pk])).content.decode()

    assert '>Test Suite<' in content
    assert '>Bill of Materials<' not in content
    # The step-management UI (Add-step dropdown) is staff-only, even within a tab a
    # non-staff user can otherwise see because of the firmware attachment.
    assert 'id="id_step_type"' not in content


@pytest.mark.django_db
def test_test_suite_tab_shows_current_suite_steps(client, staff_user, design):
    suite = TestSuite.objects.create(design=design, version=1, status=TestSuite.DRAFT)
    TestStep.objects.create(suite=suite, step_type=TestStep.DELAY, name='Settle', config={'delay_ms': 250})

    client.force_login(staff_user)
    content = client.get(reverse('design_detail', args=[design.pk])).content.decode()

    assert 'Settle' in content
    assert 'Editing draft version 1' in content


@pytest.mark.django_db
def test_bill_of_materials_tab_hides_pcb_orders_heading_when_none(client, staff_user, design):
    client.force_login(staff_user)
    content = client.get(reverse('design_detail', args=[design.pk])).content.decode()
    assert '>PCB Orders<' not in content

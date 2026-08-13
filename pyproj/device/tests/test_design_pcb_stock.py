# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import pytest

from crm.models import Org
from device.models import Design


@pytest.fixture
def design():
    org = Org.objects.create(company_name='PCB Stock Test Org')
    return Design.objects.create(client=org, sku='PCB1', name='PCB Stock Test Design', hw_version='1.0')


# --- Design.save() PCB stock history logging (issue #100, mirroring Part.save()/issue #99) ---

@pytest.mark.django_db
def test_design_save_logs_history_on_creation():
    org = Org.objects.create(company_name='PCB Stock Creation Org')
    design = Design.objects.create(client=org, sku='PCB2', name='Fresh design', hw_version='1.0', pcb_stock=100)
    assert list(design.pcb_stock_history.values_list('stock', flat=True)) == [100]


@pytest.mark.django_db
def test_design_save_logs_history_when_pcb_stock_changes(design):
    design.pcb_stock = 100
    design.save(update_fields=['pcb_stock'])

    design.pcb_stock = 50
    design.save(update_fields=['pcb_stock'])

    assert list(design.pcb_stock_history.order_by('recorded_dt').values_list('stock', flat=True)) == [None, 100, 50]


@pytest.mark.django_db
def test_design_save_does_not_duplicate_history_on_unchanged_pcb_stock(design):
    design.pcb_stock = 100
    design.save(update_fields=['pcb_stock'])
    count_before = design.pcb_stock_history.count()

    design.pcb_stock = 100
    design.save(update_fields=['pcb_stock'])

    assert design.pcb_stock_history.count() == count_before


@pytest.mark.django_db
def test_design_save_self_heals_missing_history_on_unchanged_pcb_stock(design):
    design.pcb_stock = 100
    design.save(update_fields=['pcb_stock'])
    design.pcb_stock_history.all().delete()
    assert design.pcb_stock_history.count() == 0

    design.pcb_stock = 100  # unchanged - a naive "did it change" check alone wouldn't log this
    design.save(update_fields=['pcb_stock'])

    assert list(design.pcb_stock_history.values_list('stock', flat=True)) == [100]


@pytest.mark.django_db
def test_design_save_allows_negative_pcb_stock_history(design):
    design.pcb_stock = 3
    design.save(update_fields=['pcb_stock'])

    design.pcb_stock = -2
    design.save(update_fields=['pcb_stock'])

    assert list(design.pcb_stock_history.order_by('recorded_dt').values_list('stock', flat=True)) == [None, 3, -2]

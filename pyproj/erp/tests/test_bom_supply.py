"""Consigned (register#154) and Do Not Place (register#155) BOM entries: how they change
the Design detail page's BOM table and Build Costing, and the Batch page's Parts Required."""
from decimal import Decimal

from django.urls import reverse
import pytest

from crm.models import Org
from device.models import Design
from erp.models import (
    AssemblyCostSettings, Batch, DesignBomEntry, Part, PartPriceBreak, PartsCartLine, PartSource,
    PartSourceVariant,
)
from erp.views import JointTotals, build_costing_rows, compute_bom_pricing

NORMAL = DesignBomEntry.NORMAL
CONSIGNED = DesignBomEntry.CONSIGNED
DNP = DesignBomEntry.DNP


@pytest.fixture
def design():
    org = Org.objects.create(company_name='Supply Test Org')
    return Design.objects.create(client=org, sku='SUP1', name='Supply Test Design', hw_version='1.0')


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)


def priced_part(name, price, smt=0, pth=0, **kwargs):
    part = Part.objects.create(name=name, smt_joints=smt, pth_joints=pth, **kwargs)
    source = PartSource.objects.create(part=part, supplier_name='TestSupplier')
    variant = PartSourceVariant.objects.create(source=source, supplier_sku=f'{name}-SKU')
    PartPriceBreak.objects.create(variant=variant, quantity=1, price=Decimal(price))
    return part


@pytest.fixture
def rates():
    settings = AssemblyCostSettings.get_solo()
    settings.smt_joint_cost_cents = Decimal('1')
    settings.pth_joint_cost_cents = Decimal('10')
    settings.consigned_smt_joint_cost_cents = Decimal('2')
    settings.consigned_pth_joint_cost_cents = Decimal('20')
    settings.save()
    return settings


def consumables(rows):
    return dict(rows)['Production Consumables']


# --- Shared pricing helpers ---------------------------------------------------------------

@pytest.mark.django_db
def test_build_costing_production_consumables_uses_four_sums(design, rates):
    joints = JointTotals(smt=100, pth=10, consigned_smt=50, consigned_pth=5)
    rows, _ = build_costing_rows(design, Decimal('0'), joints, rates)
    # (100*1 + 10*10 + 50*2 + 5*20) cents = 400 cents
    assert consumables(rows) == Decimal('4')


@pytest.mark.django_db
def test_compute_bom_pricing_consigned_counts_only_add_joints():
    bought = priced_part('Bought', '1.00', smt=2, pth=1)
    supplied = priced_part('Supplied', '5.00', smt=8, pth=3)
    parts_by_id = {bought.pk: bought, supplied.pk: supplied}

    price_breaks, total, joints = compute_bom_pricing(
        parts_by_id, {bought.pk: 3}, {bought.pk: 3}, consigned_counts={supplied.pk: 2}
    )

    assert set(price_breaks) == {bought.pk}
    assert total == Decimal('3.00')
    assert joints == JointTotals(smt=6, pth=3, consigned_smt=16, consigned_pth=6)
    assert (joints.total_smt, joints.total_pth) == (22, 9)


# --- Design detail page -------------------------------------------------------------------

@pytest.mark.django_db
def test_design_detail_costs_only_normal_entries(client, staff_user, design, rates):
    bought = priced_part('Bought Part', '1.00', smt=2, pth=1)
    supplied = priced_part('Supplied Part', '5.00', smt=4)
    unplaced = priced_part('Unplaced Part', '7.00', smt=6, pth=2)
    DesignBomEntry.objects.create(design=design, part=bought, reference='R1')
    DesignBomEntry.objects.create(design=design, part=supplied, reference='U1', supply=CONSIGNED)
    DesignBomEntry.objects.create(design=design, part=unplaced, reference='R2', supply=DNP)

    client.force_login(staff_user)
    response = client.get(reverse('design_detail', args=[design.pk]))
    ctx = response.context

    assert ctx['bom_total_cost'] == Decimal('1.00')
    # Footer joint totals count bought + consigned, never DNP.
    assert ctx['bom_total_smt_joints'] == 6
    assert ctx['bom_total_pth_joints'] == 1
    rows = dict(ctx['build_costing_rows'])
    assert rows['BoM Cost'] == Decimal('1.00')
    # (2*1 + 1*10 + 4*2) cents
    assert rows['Production Consumables'] == Decimal('0.20')

    entries = {entry.reference: entry for entry in ctx['bom_entries']}
    assert entries['R1'].unit_price_break is not None
    assert entries['U1'].unit_price_break is None
    assert entries['R2'].unit_price_break is None

    content = response.content.decode()
    assert content.count('>Client</span>') == 1
    assert '$5' not in content
    assert '$7' not in content


@pytest.mark.django_db
def test_dnp_entry_does_not_warn_about_missing_joints(client, staff_user, design):
    part = Part.objects.create(name='No Joint Data')  # smt_joints / pth_joints both None
    DesignBomEntry.objects.create(design=design, part=part, reference='R1', supply=DNP)

    client.force_login(staff_user)
    content = client.get(reverse('design_detail', args=[design.pk])).content.decode()

    assert 'title="SMT Joints not set"' not in content
    assert 'title="PTH Joints not set"' not in content


@pytest.mark.django_db
def test_set_supply_endpoint(client, staff_user, design):
    part = Part.objects.create(name='Any Part')
    entry = DesignBomEntry.objects.create(design=design, part=part, reference='R1')
    url = reverse('erp:design_bom_entry_set_supply', args=[entry.pk])

    client.force_login(staff_user)
    for supply in [CONSIGNED, DNP, NORMAL]:
        response = client.post(url, {'supply': supply})
        assert response.json() == {'ok': True, 'supply': supply}
        entry.refresh_from_db()
        assert entry.supply == supply

    response = client.post(url, {'supply': 'BOGUS'})
    assert response.status_code == 400
    assert client.get(url).status_code == 405


@pytest.mark.django_db
def test_set_supply_endpoint_requires_staff(client, django_user_model, design):
    user = django_user_model.objects.create_user(email='user@example.com', password='usery')
    part = Part.objects.create(name='Any Part')
    entry = DesignBomEntry.objects.create(design=design, part=part, reference='R1')

    client.force_login(user)
    client.post(reverse('erp:design_bom_entry_set_supply', args=[entry.pk]), {'supply': DNP})

    entry.refresh_from_db()
    assert entry.supply == NORMAL


@pytest.mark.django_db
def test_entry_edit_page_sets_supply_and_add_row_defaults_to_normal(client, staff_user, design):
    part = Part.objects.create(name='Any Part')
    client.force_login(staff_user)

    client.post(reverse('erp:design_bom_entry_add', args=[design.pk]), {'reference': 'R1', 'part': part.pk})
    entry = DesignBomEntry.objects.get(design=design, reference='R1')
    assert entry.supply == NORMAL

    client.post(
        reverse('erp:design_bom_entry_edit', args=[entry.pk]),
        {'reference': 'R1', 'part': part.pk, 'supply': CONSIGNED},
    )
    entry.refresh_from_db()
    assert entry.supply == CONSIGNED


@pytest.mark.django_db
def test_assembly_cost_settings_page_saves_consigned_rates(client, staff_user):
    client.force_login(staff_user)
    client.post(reverse('erp:assembly_cost_settings_edit'), {
        'smt_joint_cost_cents': '0.5', 'pth_joint_cost_cents': '5',
        'consigned_smt_joint_cost_cents': '0.75', 'consigned_pth_joint_cost_cents': '6',
        'labour_rate': '0', 'kitting_margin_percent': '0',
        'conformal_coating_charge': '0', 'anti_shock_glue_charge': '0',
    })
    settings = AssemblyCostSettings.get_solo()
    assert settings.consigned_smt_joint_cost_cents == Decimal('0.75')
    assert settings.consigned_pth_joint_cost_cents == Decimal('6')


# --- Batch page ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_batch_parts_required_skips_dnp_and_labels_consigned(client, staff_user, design, rates):
    bought = priced_part('Bought Part', '1.00', smt=2, stock=0)
    supplied = priced_part('Supplied Part', '5.00', smt=4, stock=0)
    unplaced = priced_part('Unplaced Part', '7.00', smt=6, stock=0)
    DesignBomEntry.objects.create(design=design, part=bought, reference='R1')
    DesignBomEntry.objects.create(design=design, part=supplied, reference='U1', supply=CONSIGNED)
    DesignBomEntry.objects.create(design=design, part=unplaced, reference='R2', supply=DNP)
    batch = Batch.objects.create(design=design, quantity=10)

    client.force_login(staff_user)
    response = client.get(reverse('erp:batch_edit', args=[batch.pk]))

    rows = {row['part'].name: row for row in response.context['parts_required']}
    assert set(rows) == {'Bought Part', 'Supplied Part'}
    assert rows['Bought Part']['short'] is True
    assert rows['Supplied Part']['consigned'] is True
    assert rows['Supplied Part']['short'] is False
    assert rows['Supplied Part']['required'] == 10

    costing = dict(response.context['build_costing_rows'])
    assert costing['BoM Cost'] == Decimal('1.00')
    # (2*1 + 4*2) cents
    assert costing['Production Consumables'] == Decimal('0.10')

    content = response.content.decode()
    assert content.count('>Client</span>') == 1
    assert reverse('erp:parts_cart_add_from_batch', args=[batch.pk, supplied.pk]) not in content
    assert reverse('erp:parts_cart_add_from_batch', args=[batch.pk, bought.pk]) in content


@pytest.mark.django_db
def test_batch_part_placed_both_ways_gets_two_rows(client, staff_user, design):
    part = Part.objects.create(name='Mixed Part')
    DesignBomEntry.objects.create(design=design, part=part, reference='C1')
    DesignBomEntry.objects.create(design=design, part=part, reference='C2')
    DesignBomEntry.objects.create(design=design, part=part, reference='C3', supply=CONSIGNED)
    batch = Batch.objects.create(design=design, quantity=5)

    client.force_login(staff_user)
    rows = client.get(reverse('erp:batch_edit', args=[batch.pk])).context['parts_required']

    assert [(row['consigned'], row['required']) for row in rows] == [(False, 10), (True, 5)]

    # The cart button uses the bought quantity, not the consigned one.
    client.post(reverse('erp:parts_cart_add_from_batch', args=[batch.pk, part.pk]))
    assert PartsCartLine.objects.get(part=part, batch=batch).quantity == 10


@pytest.mark.django_db
def test_cart_add_refuses_consigned_only_part(client, staff_user, design):
    part = Part.objects.create(name='Supplied Part')
    DesignBomEntry.objects.create(design=design, part=part, reference='U1', supply=CONSIGNED)
    batch = Batch.objects.create(design=design, quantity=5)

    client.force_login(staff_user)
    client.post(reverse('erp:parts_cart_add_from_batch', args=[batch.pk, part.pk]))

    assert not PartsCartLine.objects.filter(part=part).exists()

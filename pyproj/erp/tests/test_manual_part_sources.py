# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
"""Manual part sources: suppliers with no API integration, maintained by hand (register#153)."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
import pytest

from erp.models import (
    Part, PartPriceBreak, PartPriceBreakHistory, PartSource, PartSourceVariant, api_supplier_key,
    api_supplier_variant_q,
)


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)


@pytest.fixture
def staff_client(client, staff_user):
    client.force_login(staff_user)
    return client


@pytest.fixture
def manual_variant():
    part = Part.objects.create(name='Header', value='1x4')
    source = PartSource.objects.create(part=part, supplier_name='Core Electronics', manufacturer_sku='HDR-4', stock=50)
    variant = PartSourceVariant.objects.create(
        source=source, supplier_sku='CE-123', url='https://example.com/old', moq=1,
    )
    PartPriceBreak.objects.create(variant=variant, quantity=1, price=Decimal('0.50'), currency='AUD')
    return variant


# --- api_supplier_key / api_supplier_variant_q ---

@pytest.mark.parametrize('name,expected', [
    ('LCSC', 'lcsc'),
    ('lcsc', 'lcsc'),
    ('DigiKey', 'digikey'),
    ('DigiKey AU', 'digikey'),
    ('Mouser', 'mouser'),
    ('Element14', 'element14'),
    ('Farnell UK', 'element14'),
    ('Newark', 'element14'),
    ('Core Electronics', None),
    ('JLCPCB', None),
    ('', None),
])
def test_api_supplier_key(name, expected):
    assert api_supplier_key(name) == expected


@pytest.mark.django_db
def test_api_supplier_variant_q_matches_api_supplier_key():
    part = Part.objects.create(name='P', value='1')
    names = ['LCSC', 'DigiKey AU', 'Mouser', 'Farnell', 'Newark', 'Element14', 'Core Electronics', 'Mouser Clone']
    for name in names:
        PartSourceVariant.objects.create(source=PartSource.objects.create(part=part, supplier_name=name))
    matched = set(
        PartSourceVariant.objects.filter(api_supplier_variant_q()).values_list('source__supplier_name', flat=True)
    )
    assert matched == {name for name in names if api_supplier_key(name)}


# --- staleness ---

@pytest.mark.django_db
def test_manual_source_is_never_stale():
    part = Part.objects.create(name='P', value='1')
    source = PartSource.objects.create(part=part, supplier_name='Core Electronics')
    PartSourceVariant.objects.create(source=source, supplier_sku='X', last_refreshed=None)
    PartSourceVariant.objects.create(source=source, supplier_sku='Y', last_refreshed=timezone.now() - timedelta(days=90))
    assert source.has_api is False
    assert source.has_stale_variant_data is False
    assert part.has_stale_source_data is False


# --- adding a source ---

@pytest.mark.django_db
def test_add_manual_source_with_price(staff_client):
    part = Part.objects.create(name='P', value='1')
    resp = staff_client.post(reverse('erp:part_source_add', args=[part.pk]), {
        'supplier_name': 'Core Electronics', 'supplier_sku': 'CE-1', 'url': 'https://example.com/p',
        'price': '1.25', 'currency': 'AUD', 'moq': '', 'stock': '10',
    })
    assert resp.status_code == 302
    variant = PartSourceVariant.objects.get(source__part=part)
    assert variant.url == 'https://example.com/p'
    assert variant.last_refreshed is not None
    assert [(b.quantity, b.price, b.currency) for b in variant.price_breaks.all()] == [(1, Decimal('1.25'), 'AUD')]
    assert part.cheapest_price_break_for_quantity(5).price == Decimal('1.25')


@pytest.mark.django_db
def test_add_source_without_price_creates_no_breaks(staff_client):
    part = Part.objects.create(name='P', value='1')
    staff_client.post(reverse('erp:part_source_add', args=[part.pk]), {
        'supplier_name': 'Core Electronics', 'supplier_sku': 'CE-1', 'currency': 'AUD',
    })
    variant = PartSourceVariant.objects.get(source__part=part)
    assert not variant.price_breaks.exists()


@pytest.mark.django_db
def test_add_api_source_is_left_for_scheduled_refresh(staff_client):
    part = Part.objects.create(name='P', value='1')
    staff_client.post(reverse('erp:part_source_add', args=[part.pk]), {
        'supplier_name': 'LCSC', 'supplier_sku': 'C123', 'currency': 'AUD',
    })
    assert PartSourceVariant.objects.get(source__part=part).last_refreshed is None


# --- editing a source ---

@pytest.mark.django_db
def test_part_edit_shows_edit_button_for_manual_source_only(staff_client, manual_variant):
    part = manual_variant.source.part
    api_source = PartSource.objects.create(part=part, supplier_name='LCSC')
    api_variant = PartSourceVariant.objects.create(source=api_source, supplier_sku='C1')
    content = staff_client.get(reverse('erp:part_edit', args=[part.pk])).content.decode()
    assert reverse('erp:part_source_variant_edit', args=[manual_variant.pk]) in content
    assert reverse('erp:part_source_variant_edit', args=[api_variant.pk]) not in content
    assert reverse('erp:part_source_refresh', args=[api_variant.pk]) in content
    assert reverse('erp:part_source_refresh', args=[manual_variant.pk]) not in content


@pytest.mark.django_db
def test_edit_page_shows_existing_values(staff_client, manual_variant):
    resp = staff_client.get(reverse('erp:part_source_variant_edit', args=[manual_variant.pk]))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert 'https://example.com/old' in content
    assert 'value="0.5"' in content
    assert '<option value="AUD" selected>' in content


@pytest.mark.django_db
def test_edit_saves_listing_variant_and_price_breaks(staff_client, manual_variant):
    url = reverse('erp:part_source_variant_edit', args=[manual_variant.pk])
    resp = staff_client.post(url, {
        'supplier_name': 'Core Electronics', 'manufacturer_sku': 'HDR-4B', 'stock': '75',
        'supplier_sku': 'CE-124', 'packaging': 'Bag', 'url': 'https://example.com/new', 'moq': '5',
        'currency': 'AUD',
        'break_quantity': ['10', '1', ''], 'break_price': ['0.40', '0.55', ''],
    })
    assert resp.status_code == 302
    manual_variant.refresh_from_db()
    listing = manual_variant.source
    assert (listing.manufacturer_sku, listing.stock) == ('HDR-4B', 75)
    assert (manual_variant.supplier_sku, manual_variant.packaging, manual_variant.url, manual_variant.moq) == (
        'CE-124', 'Bag', 'https://example.com/new', 5,
    )
    assert manual_variant.last_refreshed is not None
    assert [(b.quantity, b.price) for b in manual_variant.price_breaks.all()] == [
        (1, Decimal('0.55')), (10, Decimal('0.40')),
    ]
    # The changed ladder is recorded in price history, and the stock change in stock history.
    assert PartPriceBreakHistory.objects.filter(variant=manual_variant, quantity=10).exists()
    assert listing.stock_history.filter(stock=75).exists()


@pytest.mark.django_db
def test_edit_with_no_breaks_clears_price(staff_client, manual_variant):
    staff_client.post(reverse('erp:part_source_variant_edit', args=[manual_variant.pk]), {
        'supplier_name': 'Core Electronics', 'currency': 'AUD', 'break_quantity': [''], 'break_price': [''],
    })
    assert not manual_variant.price_breaks.exists()


@pytest.mark.django_db
@pytest.mark.parametrize('quantities,prices,message', [
    (['1'], [''], 'needs both a quantity and a price'),
    (['0'], ['1.00'], 'whole number of 1 or more'),
    (['1.5'], ['1.00'], 'whole number of 1 or more'),
    (['1'], ['abc'], 'must be a number'),
    (['1'], ['-1'], 'must be a number'),
    (['1'], ['0.1234567'], 'more than 6 decimal places'),
    (['5', '5'], ['1', '2'], 'more than one price break for quantity 5'),
])
def test_edit_rejects_bad_price_breaks(staff_client, manual_variant, quantities, prices, message):
    resp = staff_client.post(reverse('erp:part_source_variant_edit', args=[manual_variant.pk]), {
        'supplier_name': 'Core Electronics', 'currency': 'AUD',
        'break_quantity': quantities, 'break_price': prices,
    })
    assert resp.status_code == 200
    assert message in resp.content.decode()
    # Nothing changed.
    assert [(b.quantity, b.price) for b in manual_variant.price_breaks.all()] == [(1, Decimal('0.50'))]


@pytest.mark.django_db
def test_edit_refuses_api_source(staff_client):
    part = Part.objects.create(name='P', value='1')
    variant = PartSourceVariant.objects.create(
        source=PartSource.objects.create(part=part, supplier_name='DigiKey'), supplier_sku='DK1',
    )
    resp = staff_client.post(reverse('erp:part_source_variant_edit', args=[variant.pk]), {
        'supplier_name': 'DigiKey', 'supplier_sku': 'CHANGED', 'currency': 'AUD',
    })
    assert resp.status_code == 302
    variant.refresh_from_db()
    assert variant.supplier_sku == 'DK1'


@pytest.mark.django_db
def test_edit_requires_staff(client, django_user_model, manual_variant):
    user = django_user_model.objects.create_user(email='user@example.com', password='x')
    client.force_login(user)
    resp = client.get(reverse('erp:part_source_variant_edit', args=[manual_variant.pk]))
    assert resp.status_code == 302
    assert 'login' in resp.url


# --- scheduled refresh ---

@pytest.mark.django_db
def test_refresh_command_skips_manual_sources(manual_variant):
    out = StringIO()
    call_command('refresh_part_sources', '--dry-run', stdout=out)
    assert 'No part source variants to refresh.' in out.getvalue()

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from datetime import timedelta

from django.utils import timezone
import pytest

from erp.models import Part, PartSource, PartSourceVariant
from erp.views import _sync_digikey_sibling_variants


def _variation(pn, price=1.0, qty=1, moq=1, packaging='Cut Tape (CT)', marketplace=False):
    return {
        'DigiKeyProductNumber': pn,
        'PackageType': {'Name': packaging},
        'StandardPricing': [{'BreakQuantity': qty, 'UnitPrice': price, 'TotalPrice': price * qty}],
        'MinimumOrderQuantity': moq,
        'MarketPlace': marketplace,
    }


@pytest.fixture
def part():
    return Part.objects.create(name='Test Part', value='1K')


@pytest.fixture
def listing(part):
    return PartSource.objects.create(part=part, supplier_name='DigiKey', manufacturer_sku='ABC123')


@pytest.mark.django_db
def test_creates_missing_sibling_variants(listing):
    PartSourceVariant.objects.create(source=listing, supplier_sku='ABC123-CT-ND')
    variations = [
        _variation('ABC123-CT-ND', packaging='Cut Tape (CT)'),
        _variation('ABC123-TR-ND', packaging='Tape & Reel (TR)'),
    ]

    created, updated = _sync_digikey_sibling_variants(listing, variations, product_url='https://example.com/p')

    assert [v.supplier_sku for v in created] == ['ABC123-TR-ND']
    assert [v.supplier_sku for v in updated] == ['ABC123-CT-ND']
    new_variant = PartSourceVariant.objects.get(supplier_sku='ABC123-TR-ND')
    assert new_variant.packaging == 'Tape & Reel (TR)'
    assert new_variant.url == 'https://example.com/p'
    assert new_variant.moq == 1
    assert new_variant.last_refreshed is not None


@pytest.mark.django_db
def test_updates_existing_variant_price_breaks_moq_and_last_refreshed(listing):
    variant = PartSourceVariant.objects.create(
        source=listing, supplier_sku='ABC123-CT-ND', moq=1,
        last_refreshed=timezone.now() - timedelta(days=2),
    )
    variant.price_breaks.create(quantity=1, price='9.99', currency='USD')

    created, updated = _sync_digikey_sibling_variants(
        listing, [_variation('ABC123-CT-ND', price=0.5, qty=1, moq=2500)], product_url='https://example.com/p',
    )

    assert created == []
    assert [v.pk for v in updated] == [variant.pk]
    variant.refresh_from_db()
    assert variant.moq == 2500
    assert variant.last_refreshed > timezone.now() - timedelta(minutes=1)
    breaks = list(variant.price_breaks.values_list('quantity', 'price'))
    assert breaks == [(1, 0.5)]


@pytest.mark.django_db
def test_skips_creating_marketplace_only_variations(listing):
    created, updated = _sync_digikey_sibling_variants(
        listing, [_variation('ABC123-MP-ND', marketplace=True)], product_url='https://example.com/p',
    )

    assert created == []
    assert updated == []
    assert not PartSourceVariant.objects.filter(supplier_sku='ABC123-MP-ND').exists()


@pytest.mark.django_db
def test_updates_marketplace_variation_if_variant_already_exists(listing):
    variant = PartSourceVariant.objects.create(source=listing, supplier_sku='ABC123-MP-ND')

    created, updated = _sync_digikey_sibling_variants(
        listing, [_variation('ABC123-MP-ND', marketplace=True, moq=5)], product_url='https://example.com/p',
    )

    assert created == []
    assert [v.pk for v in updated] == [variant.pk]
    variant.refresh_from_db()
    assert variant.moq == 5


@pytest.mark.django_db
def test_ignores_variations_with_no_digikey_product_number(listing):
    created, updated = _sync_digikey_sibling_variants(
        listing, [{'DigiKeyProductNumber': '', 'PackageType': {}, 'StandardPricing': []}],
        product_url='https://example.com/p',
    )

    assert created == []
    assert updated == []
    assert not PartSourceVariant.objects.filter(source=listing).exists()

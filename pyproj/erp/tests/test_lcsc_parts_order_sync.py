# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from datetime import datetime, timezone as dt_timezone

import pytest
from django.utils import timezone
from lcsc_toolkit.orders.types import OrderDetail, OrderLineItem, OrderSummary

from erp.models import Part, PartSource, PartSourceVariant, PartsOrder, PartsOrderLine
from erp.views import (
    _map_lcsc_order_status,
    _match_or_create_part_for_lcsc_line,
    _parse_lcsc_dt,
    _parse_lcsc_order,
    _parse_lcsc_order_line,
    _upsert_parts_order,
)


def _order_summary(uuid='UUID-1', order_code='WM2607080353', web_order_status='Shipped',
                    currency_type='USD', create_time='2026-07-08 16:11:03'):
    return OrderSummary(
        uuid=uuid, order_code=order_code, web_order_status=web_order_status,
        payment_status='Paid', order_amount=10.0, currency_type=currency_type,
        create_time=create_time, tracking_code='', express_type='', raw={},
    )


def _order_line_item(uuid='LINE-UUID-1', product_code='C17179461', product_mpn='HY2005WV',
                      description='Connector', purchase_quantity=100, unit_price=0.50, real_price=0.45):
    return OrderLineItem(
        uuid=uuid, product_code=product_code, product_mpn=product_mpn, description=description,
        purchase_quantity=purchase_quantity, unit_price=unit_price, real_price=real_price,
        total_price=unit_price * purchase_quantity, real_total_amount=real_price * purchase_quantity,
        raw={},
    )


def _order_detail(uuid='UUID-1', order_code='WM2607080353', web_order_status='Shipped',
                   create_time='2026-07-08 16:11:03', line_items=None):
    return OrderDetail(
        uuid=uuid, order_code=order_code, web_order_status=web_order_status, create_time=create_time,
        tracking_code='', express_type='',
        line_items=line_items if line_items is not None else [_order_line_item()],
        raw={},
    )


# --- _parse_lcsc_dt ---

def test_parse_lcsc_dt_parses_space_separated_format():
    result = _parse_lcsc_dt('2026-07-08 16:11:03')
    assert result == datetime(2026, 7, 8, 16, 11, 3, tzinfo=dt_timezone.utc)


def test_parse_lcsc_dt_returns_none_for_missing():
    assert _parse_lcsc_dt(None) is None
    assert _parse_lcsc_dt('') is None


def test_parse_lcsc_dt_returns_none_for_unparseable():
    assert _parse_lcsc_dt('not-a-date') is None
    assert _parse_lcsc_dt('2026-07-08T16:11:03Z') is None  # ISO8601 - not LCSC's format


def test_parse_lcsc_dt_assumes_utc():
    # LCSC's createTime carries no timezone indicator at all - UTC is an explicit,
    # documented assumption (see the module comment above _parse_lcsc_dt in erp/views.py),
    # not a confirmed fact.
    result = _parse_lcsc_dt('2026-01-01 00:00:00')
    assert result.tzinfo == dt_timezone.utc


# --- _map_lcsc_order_status ---

@pytest.mark.parametrize('raw, expected', [
    ('Delivered', PartsOrderLine.RECEIVED),
    ('delivered', PartsOrderLine.RECEIVED),
    ('Shipped', PartsOrderLine.SHIPPED),
    ('Cancelled', PartsOrderLine.CANCELLED),
    ('Canceled', PartsOrderLine.CANCELLED),
    ('Processing', PartsOrderLine.OPEN),
    ('', PartsOrderLine.OPEN),
    (None, PartsOrderLine.OPEN),
    ('SomeUnknownStatus', PartsOrderLine.OPEN),
])
def test_map_lcsc_order_status(raw, expected):
    assert _map_lcsc_order_status(raw) == expected


# --- _parse_lcsc_order_line ---

def test_parse_lcsc_order_line_maps_fields():
    line_item = _order_line_item(product_code='C1', description='Desc', purchase_quantity=5, real_price=1.25)

    parsed = _parse_lcsc_order_line(line_item, order_status=PartsOrderLine.OPEN, currency='USD')

    assert parsed['supplier_sku'] == 'C1'
    assert parsed['supplier_line_number'] == line_item.uuid
    assert parsed['description'] == 'Desc'
    assert parsed['quantity'] == 5
    assert parsed['unit_price'] == 1.25
    assert parsed['currency'] == 'USD'
    assert parsed['status'] == PartsOrderLine.OPEN


def test_parse_lcsc_order_line_supplier_line_number_tracks_uuid_not_position():
    # The whole point of exposing uuid on OrderLineItem: unlike Mouser's synthetic
    # positional index, a line's identity survives being reordered between syncs.
    line_a = _order_line_item(uuid='LINE-A', product_code='SKU-A')
    line_b = _order_line_item(uuid='LINE-B', product_code='SKU-B')

    parsed_a = _parse_lcsc_order_line(line_a, order_status=PartsOrderLine.OPEN, currency='USD')
    parsed_b = _parse_lcsc_order_line(line_b, order_status=PartsOrderLine.OPEN, currency='USD')

    assert parsed_a['supplier_line_number'] == 'LINE-A'
    assert parsed_b['supplier_line_number'] == 'LINE-B'


def test_parse_lcsc_order_line_uses_real_price_not_pre_discount_unit_price():
    line_item = _order_line_item(unit_price=0.50, real_price=0.45)

    parsed = _parse_lcsc_order_line(line_item, order_status=PartsOrderLine.OPEN, currency='USD')

    assert parsed['unit_price'] == 0.45


# --- _parse_lcsc_order ---

def test_parse_lcsc_order_maps_top_level_fields():
    summary = _order_summary(currency_type='USD')
    detail = _order_detail(order_code='WM999', web_order_status='Shipped', create_time='2026-07-08 16:11:03')

    parsed = _parse_lcsc_order(summary, detail)

    assert parsed['supplier_order_number'] == 'WM999'
    assert parsed['supplier_order_url'] == detail.detail_url
    assert parsed['order_dt'] == datetime(2026, 7, 8, 16, 11, 3, tzinfo=dt_timezone.utc)
    assert parsed['expected_arrival_date'] is None
    assert parsed['status'] == 'Shipped'
    assert len(parsed['lines']) == 1


def test_parse_lcsc_order_currency_comes_from_summary_not_detail():
    # OrderDetail deliberately has no currency field of its own - see its docstring in
    # lcsc_toolkit.orders.types.
    summary = _order_summary(currency_type='AUD')
    detail = _order_detail()

    parsed = _parse_lcsc_order(summary, detail)

    assert parsed['lines'][0]['currency'] == 'AUD'


def test_parse_lcsc_order_handles_empty_line_items():
    parsed = _parse_lcsc_order(_order_summary(), _order_detail(line_items=[]))
    assert parsed['lines'] == []


def test_parse_lcsc_order_lines_inherit_mapped_order_status():
    detail = _order_detail(web_order_status='Delivered')

    parsed = _parse_lcsc_order(_order_summary(), detail)

    assert parsed['lines'][0]['status'] == PartsOrderLine.RECEIVED


# --- _match_or_create_part_for_lcsc_line ---

@pytest.mark.django_db
def test_match_or_create_part_matches_existing_variant():
    part = Part.objects.create(name='Existing Part')
    source = PartSource.objects.create(part=part, supplier_name='LCSC', manufacturer_sku='MFR1')
    variant = PartSourceVariant.objects.create(source=source, supplier_sku='C17179461')

    matched_part, matched_variant = _match_or_create_part_for_lcsc_line('C17179461', 'ignored')

    assert matched_part == part
    assert matched_variant == variant


@pytest.mark.django_db
def test_match_or_create_part_matches_case_insensitively():
    part = Part.objects.create(name='Existing Part')
    source = PartSource.objects.create(part=part, supplier_name='LCSC', manufacturer_sku='MFR1')
    PartSourceVariant.objects.create(source=source, supplier_sku='C99999')

    matched_part, matched_variant = _match_or_create_part_for_lcsc_line('c99999', 'ignored')

    assert matched_part == part


@pytest.mark.django_db
def test_match_or_create_part_creates_new_part_when_no_match():
    assert not PartSourceVariant.objects.filter(supplier_sku='C-NEW').exists()

    matched_part, matched_variant = _match_or_create_part_for_lcsc_line('C-NEW', 'A new widget')

    assert matched_part is not None
    assert matched_part.name == 'C-NEW'
    assert matched_part.description == 'A new widget'
    assert matched_variant.supplier_sku == 'C-NEW'
    assert matched_variant.source.supplier_name == 'LCSC'
    assert matched_variant.source.part == matched_part


@pytest.mark.django_db
def test_match_or_create_part_returns_none_for_blank_sku():
    matched_part, matched_variant = _match_or_create_part_for_lcsc_line('', 'desc')
    assert matched_part is None
    assert matched_variant is None


# --- _upsert_parts_order with the LCSC matcher ---

@pytest.mark.django_db
def test_upsert_parts_order_creates_lcsc_order_and_lines():
    parsed = _parse_lcsc_order(
        _order_summary(order_code='WM1'),
        _order_detail(order_code='WM1', line_items=[_order_line_item(product_code='C1', purchase_quantity=3)]),
    )

    parts_order = _upsert_parts_order(parsed, supplier_name='LCSC', part_matcher=_match_or_create_part_for_lcsc_line)

    assert parts_order.supplier_name == 'LCSC'
    assert parts_order.supplier_order_number == 'WM1'
    assert parts_order.lines.count() == 1
    assert parts_order.lines.first().supplier_sku == 'C1'
    assert parts_order.lines.first().quantity == 3
    assert parts_order.lines.first().part_source_variant.source.supplier_name == 'LCSC'


@pytest.mark.django_db
def test_upsert_parts_order_preserves_received_across_resync_even_if_lines_reorder():
    line = _order_line_item(uuid='LINE-A', product_code='C1', purchase_quantity=3)
    parsed = _parse_lcsc_order(_order_summary(order_code='WM2'), _order_detail(order_code='WM2', line_items=[line]))
    parts_order = _upsert_parts_order(parsed, supplier_name='LCSC', part_matcher=_match_or_create_part_for_lcsc_line)
    order_line = parts_order.lines.get()
    order_line.received = True
    order_line.received_dt = timezone.now()
    order_line.save(update_fields=['received', 'received_dt'])

    # Resync: same line uuid, but now listed alongside a second line and with a changed
    # quantity - should update the existing row in place (matched on uuid, not position),
    # so the manually-set received flag survives.
    resynced_line = _order_line_item(uuid='LINE-A', product_code='C1', purchase_quantity=5)
    other_line = _order_line_item(uuid='LINE-B', product_code='C2', purchase_quantity=1)
    resynced = _parse_lcsc_order(
        _order_summary(order_code='WM2'),
        _order_detail(order_code='WM2', line_items=[other_line, resynced_line]),
    )
    parts_order = _upsert_parts_order(resynced, supplier_name='LCSC', part_matcher=_match_or_create_part_for_lcsc_line)

    order_line.refresh_from_db()
    assert parts_order.lines.count() == 2
    assert order_line.received is True
    assert order_line.received_dt is not None
    assert order_line.quantity == 5


@pytest.mark.django_db
def test_upsert_parts_order_unique_together_keeps_lcsc_separate_from_other_suppliers():
    # Same supplier_order_number, different supplier_name - must not collide, since
    # unique_together is on the (supplier_name, supplier_order_number) pair.
    digikey_parsed = {
        'supplier_order_number': 'SHARED456', 'supplier_order_url': '', 'order_dt': None,
        'expected_arrival_date': None, 'status': '', 'lines': [],
    }
    lcsc_parsed = dict(digikey_parsed)

    _upsert_parts_order(digikey_parsed, supplier_name='DigiKey')
    _upsert_parts_order(lcsc_parsed, supplier_name='LCSC', part_matcher=_match_or_create_part_for_lcsc_line)

    assert PartsOrder.objects.filter(supplier_order_number='SHARED456').count() == 2

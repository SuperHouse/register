# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from datetime import datetime, timezone as dt_timezone

import pytest
from django.utils import timezone

from erp.models import Part, PartSource, PartSourceVariant, PartsOrder, PartsOrderLine
from erp.views import (
    _map_mouser_order_status,
    _match_or_create_part_for_mouser_line,
    _parse_mouser_dt,
    _parse_mouser_order,
    _parse_mouser_order_line,
    _upsert_parts_order,
)


def _raw_order_line(sku='593-CRCW060310K0FKEA', description='Resistor', qty=100, price=0.02,
                     activities=None):
    """Fixture using real Mouser Order History API field names, per the published swagger
    spec at https://api.mouser.com/api/docs/V1 (definitions.OrderLineItem/OrderLineProduct).
    """
    return {
        'Quantity': qty,
        'UnitPrice': price,
        'ProductInfo': {
            'MouserPartNumber': sku,
            'PartDescription': description,
        },
        'Activities': activities if activities is not None else [],
    }


def _raw_order_history_item(sales_order_number='12345678', date_created='2026-06-01T10:00:00Z',
                             status_display='Shipped'):
    """Fixture using real field names from OrderHistoryBaseObject (the orderhistory/
    ByDateRange list response) - no line items here, that's only in OrderDetail."""
    return {
        'DateCreated': date_created,
        'SalesOrderNumber': sales_order_number,
        'WebOrderNumber': '87654321',
        'PoNumber': '',
        'BuyerName': 'Test Buyer',
        'OrderStatusDisplay': status_display,
    }


def _raw_order_detail(status_name='Shipped', currency='USD', order_date='2026-06-01T10:00:00Z', lines=None):
    """Fixture using real field names from OrderDetail (the orderhistory/salesOrderNumber
    response)."""
    return {
        'OrderLines': lines if lines is not None else [_raw_order_line()],
        'SalesOrderId': '12345678',
        'WebOrderId': 87654321,
        'OrderStatus': 4,
        'OrderStatusName': status_name,
        'OrderDate': order_date,
        'CurrencyCode': currency,
        'BuyerName': 'Test Buyer',
    }


# --- _parse_mouser_dt ---

def test_parse_mouser_dt_parses_iso_with_z_suffix():
    result = _parse_mouser_dt('2026-06-01T10:00:00Z')
    assert result == datetime(2026, 6, 1, 10, 0, 0, tzinfo=dt_timezone.utc)


def test_parse_mouser_dt_returns_none_for_missing():
    assert _parse_mouser_dt(None) is None
    assert _parse_mouser_dt('') is None


def test_parse_mouser_dt_returns_none_for_unparseable():
    assert _parse_mouser_dt('not-a-date') is None


# --- _map_mouser_order_status ---

@pytest.mark.parametrize('raw, expected', [
    ('Shipped', PartsOrderLine.SHIPPED),
    ('shipped', PartsOrderLine.SHIPPED),
    ('Delivered', PartsOrderLine.SHIPPED),
    ('Order Complete', PartsOrderLine.SHIPPED),
    ('Cancelled', PartsOrderLine.CANCELLED),
    ('Canceled', PartsOrderLine.CANCELLED),
    ('Processing', PartsOrderLine.OPEN),
    ('Backordered', PartsOrderLine.OPEN),
    ('', PartsOrderLine.OPEN),
    (None, PartsOrderLine.OPEN),
    ('SomeUnknownStatus', PartsOrderLine.OPEN),
])
def test_map_mouser_order_status(raw, expected):
    assert _map_mouser_order_status(raw) == expected


# --- _parse_mouser_order_line ---

def test_parse_mouser_order_line_maps_fields():
    parsed = _parse_mouser_order_line(
        _raw_order_line(sku='SKU1', description='Desc', qty=5, price=1.25),
        line_index=2, order_currency='USD', fallback_status=PartsOrderLine.OPEN,
    )
    assert parsed['supplier_sku'] == 'SKU1'
    assert parsed['supplier_line_number'] == '2'
    assert parsed['description'] == 'Desc'
    assert parsed['quantity'] == 5
    assert parsed['unit_price'] == 1.25
    assert parsed['currency'] == 'USD'
    assert parsed['status'] == PartsOrderLine.OPEN


def test_parse_mouser_order_line_falls_back_to_usd_when_no_currency_given():
    parsed = _parse_mouser_order_line(_raw_order_line(), line_index=0, order_currency=None,
                                       fallback_status=PartsOrderLine.OPEN)
    assert parsed['currency'] == 'USD'


def test_parse_mouser_order_line_activities_override_fallback_status():
    parsed = _parse_mouser_order_line(
        _raw_order_line(activities=[{'InvoiceNumber': 1, 'Date': '2026-06-02T00:00:00Z'}]),
        line_index=0, order_currency='USD', fallback_status=PartsOrderLine.OPEN,
    )
    assert parsed['status'] == PartsOrderLine.SHIPPED


def test_parse_mouser_order_line_uses_fallback_status_when_no_activities():
    parsed = _parse_mouser_order_line(_raw_order_line(activities=[]), line_index=0,
                                       order_currency='USD', fallback_status=PartsOrderLine.CANCELLED)
    assert parsed['status'] == PartsOrderLine.CANCELLED


# --- _parse_mouser_order ---

def test_parse_mouser_order_maps_top_level_fields():
    parsed = _parse_mouser_order(
        _raw_order_history_item(sales_order_number='SO999', status_display='Shipped'),
        _raw_order_detail(),
    )
    assert parsed['supplier_order_number'] == 'SO999'
    assert parsed['supplier_order_url'] == ''
    assert parsed['expected_arrival_date'] is None
    assert parsed['order_dt'] == datetime(2026, 6, 1, 10, 0, 0, tzinfo=dt_timezone.utc)
    assert parsed['status'] == 'Shipped'
    assert len(parsed['lines']) == 1


def test_parse_mouser_order_lines_inherit_order_currency():
    parsed = _parse_mouser_order(_raw_order_history_item(), _raw_order_detail(currency='AUD'))
    assert parsed['lines'][0]['currency'] == 'AUD'


def test_parse_mouser_order_handles_missing_order_lines():
    parsed = _parse_mouser_order(_raw_order_history_item(), _raw_order_detail(lines=[]))
    assert parsed['lines'] == []


def test_parse_mouser_order_line_index_is_positional():
    parsed = _parse_mouser_order(_raw_order_history_item(), _raw_order_detail(lines=[
        _raw_order_line(sku='SKU-A'), _raw_order_line(sku='SKU-B'),
    ]))
    assert [line['supplier_line_number'] for line in parsed['lines']] == ['0', '1']


# --- _match_or_create_part_for_mouser_line ---

@pytest.mark.django_db
def test_match_or_create_part_matches_existing_variant():
    part = Part.objects.create(name='Existing Part')
    source = PartSource.objects.create(part=part, supplier_name='Mouser', manufacturer_sku='MFR1')
    variant = PartSourceVariant.objects.create(source=source, supplier_sku='593-CRCW060310K0FKEA')

    matched_part, matched_variant = _match_or_create_part_for_mouser_line('593-CRCW060310K0FKEA', 'ignored')

    assert matched_part == part
    assert matched_variant == variant


@pytest.mark.django_db
def test_match_or_create_part_matches_case_insensitively():
    part = Part.objects.create(name='Existing Part')
    source = PartSource.objects.create(part=part, supplier_name='Mouser', manufacturer_sku='MFR1')
    PartSourceVariant.objects.create(source=source, supplier_sku='SKU-ABC')

    matched_part, matched_variant = _match_or_create_part_for_mouser_line('sku-abc', 'ignored')

    assert matched_part == part


@pytest.mark.django_db
def test_match_or_create_part_creates_new_part_when_no_match():
    assert not PartSourceVariant.objects.filter(supplier_sku='NEWSKU').exists()

    matched_part, matched_variant = _match_or_create_part_for_mouser_line('NEWSKU', 'A new widget')

    assert matched_part is not None
    assert matched_part.name == 'NEWSKU'
    assert matched_part.description == 'A new widget'
    assert matched_variant.supplier_sku == 'NEWSKU'
    assert matched_variant.source.supplier_name == 'Mouser'
    assert matched_variant.source.part == matched_part


@pytest.mark.django_db
def test_match_or_create_part_returns_none_for_blank_sku():
    matched_part, matched_variant = _match_or_create_part_for_mouser_line('', 'desc')
    assert matched_part is None
    assert matched_variant is None


# --- _upsert_parts_order with the Mouser matcher ---

@pytest.mark.django_db
def test_upsert_parts_order_creates_mouser_order_and_lines():
    parsed = _parse_mouser_order(
        _raw_order_history_item(sales_order_number='SO1'),
        _raw_order_detail(lines=[_raw_order_line(sku='SKU-A', qty=3)]),
    )

    parts_order = _upsert_parts_order(parsed, supplier_name='Mouser',
                                       part_matcher=_match_or_create_part_for_mouser_line)

    assert parts_order.supplier_name == 'Mouser'
    assert parts_order.supplier_order_number == 'SO1'
    assert parts_order.lines.count() == 1
    assert parts_order.lines.first().supplier_sku == 'SKU-A'
    assert parts_order.lines.first().quantity == 3
    assert parts_order.lines.first().part_source_variant.source.supplier_name == 'Mouser'


@pytest.mark.django_db
def test_upsert_parts_order_preserves_received_across_resync_via_positional_line_number():
    parsed = _parse_mouser_order(
        _raw_order_history_item(sales_order_number='SO2'),
        _raw_order_detail(lines=[_raw_order_line(sku='SKU-A', qty=3)]),
    )
    parts_order = _upsert_parts_order(parsed, supplier_name='Mouser',
                                       part_matcher=_match_or_create_part_for_mouser_line)
    line = parts_order.lines.get()
    line.received = True
    line.received_dt = timezone.now()
    line.save(update_fields=['received', 'received_dt'])

    # Resync: same position (index 0), but quantity changed - should update in place, not
    # replace the row, so the manually-set received flag survives.
    resynced = _parse_mouser_order(
        _raw_order_history_item(sales_order_number='SO2'),
        _raw_order_detail(lines=[_raw_order_line(sku='SKU-A', qty=5)]),
    )
    parts_order = _upsert_parts_order(resynced, supplier_name='Mouser',
                                       part_matcher=_match_or_create_part_for_mouser_line)

    line.refresh_from_db()
    assert parts_order.lines.count() == 1
    assert line.received is True
    assert line.received_dt is not None
    assert line.quantity == 5


@pytest.mark.django_db
def test_upsert_parts_order_digikey_default_matcher_unaffected():
    # Confirms the part_matcher default keeps the existing DigiKey call sites working
    # unchanged after the refactor to accept a part_matcher parameter.
    from erp.views import _parse_digikey_order

    parsed = _parse_digikey_order({
        'SalesOrderId': 'SODK1',
        'OrderNumber': 1,
        'DateEntered': '2026-06-01T10:00:00Z',
        'Currency': 'USD',
        'Status': {'SalesOrderStatus': 'Shipped'},
        'LineItems': [{
            'DigiKeyProductNumber': 'DK-SKU', 'Description': 'Widget',
            'QuantityOrdered': 1, 'UnitPrice': 1.0, 'QuantityShipped': 1, 'DetailId': 1,
        }],
    })

    parts_order = _upsert_parts_order(parsed)

    assert parts_order.supplier_name == 'DigiKey'
    assert parts_order.lines.first().part_source_variant.source.supplier_name == 'DigiKey'


@pytest.mark.django_db
def test_upsert_parts_order_unique_together_keeps_digikey_and_mouser_orders_separate():
    # Same supplier_order_number, different supplier_name - must not collide, since
    # unique_together is on the (supplier_name, supplier_order_number) pair.
    digikey_parsed = {
        'supplier_order_number': 'SHARED123', 'supplier_order_url': '', 'order_dt': None,
        'expected_arrival_date': None, 'status': '', 'lines': [],
    }
    mouser_parsed = dict(digikey_parsed)

    _upsert_parts_order(digikey_parsed, supplier_name='DigiKey')
    _upsert_parts_order(mouser_parsed, supplier_name='Mouser', part_matcher=_match_or_create_part_for_mouser_line)

    assert PartsOrder.objects.filter(supplier_order_number='SHARED123').count() == 2

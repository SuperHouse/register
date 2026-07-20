# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from datetime import date, datetime, timezone as dt_timezone

import pytest
from django.utils import timezone

from erp.models import Part, PartSource, PartSourceVariant, PartsOrder, PartsOrderLine
from erp.views import (
    _digikey_expected_arrival_date,
    _map_digikey_line_status,
    _match_or_create_part_for_digikey_line,
    _parse_digikey_date,
    _parse_digikey_dt,
    _parse_digikey_order,
    _parse_digikey_order_line,
    _upsert_parts_order,
)


def _raw_line(sku='ABC123-CT-ND', description='Widget', qty=10, price=0.5, qty_shipped=0,
              schedules=None, detail_id=None):
    """Fixture using real DigiKey OrderStatus v4 LineItem field names, per the published
    OrderStatus.json swagger spec (definitions.LineItem)."""
    line = {
        'DigiKeyProductNumber': sku,
        'Description': description,
        'QuantityOrdered': qty,
        'UnitPrice': price,
        'QuantityShipped': qty_shipped,
        'Schedules': schedules if schedules is not None else [],
    }
    if detail_id is not None:
        line['DetailId'] = detail_id
    return line


def _raw_sales_order(order_id='SO123', order_number=9910000373735576, currency='USD',
                      status='Shipped', lines=None):
    """Fixture using real DigiKey OrderStatus v4 SalesOrder field names, per the published
    OrderStatus.json swagger spec (definitions.SalesOrder) - as nested under an Order's
    SalesOrders list in a SearchOrders response. order_id (SalesOrderId) and order_number
    (OrderNumber) are deliberately different-shaped defaults - they're distinct DigiKey
    identifiers, not two names for the same value (see _digikey_order_url)."""
    return {
        'SalesOrderId': order_id,
        'OrderNumber': order_number,
        'DateEntered': '2026-06-01T10:00:00Z',
        'Currency': currency,
        'Status': {'SalesOrderStatus': status},
        'LineItems': lines if lines is not None else [_raw_line()],
    }


# --- _parse_digikey_dt / _parse_digikey_date ---

def test_parse_digikey_dt_parses_iso_with_z_suffix():
    result = _parse_digikey_dt('2026-06-01T10:00:00Z')
    assert result == datetime(2026, 6, 1, 10, 0, 0, tzinfo=dt_timezone.utc)


def test_parse_digikey_dt_parses_sub_microsecond_fraction():
    # DigiKey's own spec example uses 7 fractional digits - fromisoformat truncates to
    # microseconds rather than erroring.
    result = _parse_digikey_dt('2019-05-30T21:16:13.7526329Z')
    assert result == datetime(2019, 5, 30, 21, 16, 13, 752632, tzinfo=dt_timezone.utc)


def test_parse_digikey_dt_returns_none_for_missing():
    assert _parse_digikey_dt(None) is None
    assert _parse_digikey_dt('') is None


def test_parse_digikey_dt_returns_none_for_unparseable():
    assert _parse_digikey_dt('not-a-date') is None


def test_parse_digikey_date_extracts_date_part():
    assert _parse_digikey_date('2026-06-10T00:00:00Z') == date(2026, 6, 10)


# --- _map_digikey_line_status ---

@pytest.mark.parametrize('raw, expected', [
    ('Shipped', PartsOrderLine.SHIPPED),
    ('shipped', PartsOrderLine.SHIPPED),
    ('Delivered', PartsOrderLine.RECEIVED),
    ('Canceled', PartsOrderLine.CANCELLED),
    ('canceled', PartsOrderLine.CANCELLED),
    ('Cancelled', PartsOrderLine.OPEN),  # British spelling isn't the real enum value
    ('Received', PartsOrderLine.OPEN),  # deliberately not RECEIVED - see docstring
    ('Processing', PartsOrderLine.OPEN),
    ('GenericDelay', PartsOrderLine.OPEN),
    ('Proforma', PartsOrderLine.OPEN),
    ('ActionRequiredWireTransfer', PartsOrderLine.OPEN),
    ('', PartsOrderLine.OPEN),
    (None, PartsOrderLine.OPEN),
    ('SomeUnknownStatus', PartsOrderLine.OPEN),
])
def test_map_digikey_line_status(raw, expected):
    assert _map_digikey_line_status(raw) == expected


# --- _parse_digikey_order_line ---

def test_parse_digikey_order_line_maps_fields():
    parsed = _parse_digikey_order_line(
        _raw_line(sku='SKU1', description='Desc', qty=5, price=1.25, qty_shipped=5, detail_id=3),
        order_status='', currency='USD',
    )
    assert parsed['supplier_sku'] == 'SKU1'
    assert parsed['supplier_line_number'] == '3'
    assert parsed['description'] == 'Desc'
    assert parsed['quantity'] == 5
    assert parsed['unit_price'] == 1.25
    assert parsed['currency'] == 'USD'
    assert parsed['status'] == PartsOrderLine.SHIPPED


def test_parse_digikey_order_line_blank_supplier_line_number_when_missing():
    parsed = _parse_digikey_order_line(_raw_line(detail_id=None), order_status='')
    assert parsed['supplier_line_number'] == ''


def test_parse_digikey_order_line_open_when_not_fully_shipped():
    parsed = _parse_digikey_order_line(_raw_line(qty=10, qty_shipped=3), order_status='')
    assert parsed['status'] == PartsOrderLine.OPEN


def test_parse_digikey_order_line_order_status_cancelled_overrides_quantities():
    # Fully shipped by quantity, but the order itself was cancelled - cancellation wins.
    parsed = _parse_digikey_order_line(_raw_line(qty=10, qty_shipped=10), order_status='Canceled')
    assert parsed['status'] == PartsOrderLine.CANCELLED


def test_parse_digikey_order_line_order_status_delivered_overrides_partial_quantities():
    parsed = _parse_digikey_order_line(_raw_line(qty=10, qty_shipped=3), order_status='Delivered')
    assert parsed['status'] == PartsOrderLine.RECEIVED


def test_parse_digikey_order_line_falls_back_to_locale_currency_when_none_given():
    parsed = _parse_digikey_order_line(_raw_line(), order_status='')
    assert parsed['currency']  # whatever _digikey_locale_currency() resolves to, non-blank


# --- _digikey_expected_arrival_date ---

def test_digikey_expected_arrival_date_picks_earliest_schedule_across_lines():
    order = _raw_sales_order(lines=[
        _raw_line(sku='A', schedules=[{'ScheduledDate': '2026-07-15T00:00:00Z'}]),
        _raw_line(sku='B', schedules=[{'ScheduledDate': '2026-07-01T00:00:00Z'}]),
    ])
    assert _digikey_expected_arrival_date(order) == date(2026, 7, 1)


def test_digikey_expected_arrival_date_none_when_no_schedules():
    order = _raw_sales_order(lines=[_raw_line(schedules=[])])
    assert _digikey_expected_arrival_date(order) is None


# --- _parse_digikey_order ---

def test_parse_digikey_order_maps_top_level_fields(monkeypatch):
    monkeypatch.setenv('DIGIKEY_LOCALE_SITE', 'AU')
    parsed = _parse_digikey_order(
        _raw_sales_order(order_id='SO999', order_number=9910000373735576, status='Shipped'),
    )
    assert parsed['supplier_order_number'] == 'SO999'
    assert parsed['supplier_order_url'] == (
        'https://www.digikey.com.au/OrderHistory/ReviewOrder/9910000373735576'
    )
    assert parsed['order_dt'] == datetime(2026, 6, 1, 10, 0, 0, tzinfo=dt_timezone.utc)
    assert parsed['status'] == 'Shipped'
    assert len(parsed['lines']) == 1


def test_parse_digikey_order_lines_inherit_order_currency():
    parsed = _parse_digikey_order(_raw_sales_order(currency='AUD', lines=[_raw_line()]))
    assert parsed['lines'][0]['currency'] == 'AUD'


def test_parse_digikey_order_handles_missing_line_items():
    parsed = _parse_digikey_order(_raw_sales_order(lines=[]))
    assert parsed['lines'] == []


# --- _match_or_create_part_for_digikey_line ---

@pytest.mark.django_db
def test_match_or_create_part_matches_existing_variant():
    part = Part.objects.create(name='Existing Part')
    source = PartSource.objects.create(part=part, supplier_name='DigiKey', manufacturer_sku='MFR1')
    variant = PartSourceVariant.objects.create(source=source, supplier_sku='ABC123-CT-ND')

    matched_part, matched_variant = _match_or_create_part_for_digikey_line('ABC123-CT-ND', 'ignored')

    assert matched_part == part
    assert matched_variant == variant


@pytest.mark.django_db
def test_match_or_create_part_matches_case_insensitively():
    part = Part.objects.create(name='Existing Part')
    source = PartSource.objects.create(part=part, supplier_name='DigiKey', manufacturer_sku='MFR1')
    PartSourceVariant.objects.create(source=source, supplier_sku='ABC123-CT-ND')

    matched_part, matched_variant = _match_or_create_part_for_digikey_line('abc123-ct-nd', 'ignored')

    assert matched_part == part


@pytest.mark.django_db
def test_match_or_create_part_creates_new_part_when_no_match():
    assert not PartSourceVariant.objects.filter(supplier_sku='NEWSKU-ND').exists()

    matched_part, matched_variant = _match_or_create_part_for_digikey_line('NEWSKU-ND', 'A new widget')

    assert matched_part is not None
    assert matched_part.name == 'NEWSKU-ND'
    assert matched_part.description == 'A new widget'
    assert matched_variant.supplier_sku == 'NEWSKU-ND'
    assert matched_variant.source.supplier_name == 'DigiKey'
    assert matched_variant.source.part == matched_part


@pytest.mark.django_db
def test_match_or_create_part_returns_none_for_blank_sku():
    matched_part, matched_variant = _match_or_create_part_for_digikey_line('', 'desc')
    assert matched_part is None
    assert matched_variant is None


# --- _upsert_parts_order ---

@pytest.mark.django_db
def test_upsert_parts_order_creates_order_and_lines():
    parsed = _parse_digikey_order(_raw_sales_order(order_id='SO1', lines=[_raw_line(sku='SKU-A', qty=3)]))

    parts_order = _upsert_parts_order(parsed)

    assert parts_order.supplier_name == 'DigiKey'
    assert parts_order.supplier_order_number == 'SO1'
    assert parts_order.lines.count() == 1
    assert parts_order.lines.first().supplier_sku == 'SKU-A'
    assert parts_order.lines.first().quantity == 3


@pytest.mark.django_db
def test_upsert_parts_order_replaces_lines_on_resync_not_duplicate():
    first = _parse_digikey_order(_raw_sales_order(order_id='SO2', lines=[_raw_line(sku='SKU-A', qty=3)]))
    _upsert_parts_order(first)

    second = _parse_digikey_order(_raw_sales_order(order_id='SO2', lines=[_raw_line(sku='SKU-B', qty=7)]))
    parts_order = _upsert_parts_order(second)

    assert PartsOrder.objects.filter(supplier_name='DigiKey', supplier_order_number='SO2').count() == 1
    assert parts_order.lines.count() == 1
    assert parts_order.lines.first().supplier_sku == 'SKU-B'


@pytest.mark.django_db
def test_upsert_parts_order_unique_together_prevents_duplicates():
    parsed = _parse_digikey_order(_raw_sales_order(order_id='SO3'))
    _upsert_parts_order(parsed)
    _upsert_parts_order(parsed)

    assert PartsOrder.objects.filter(supplier_name='DigiKey', supplier_order_number='SO3').count() == 1


@pytest.mark.django_db
def test_upsert_parts_order_preserves_received_across_resync_via_supplier_line_number():
    parsed = _parse_digikey_order(
        _raw_sales_order(order_id='SO4', lines=[_raw_line(sku='SKU-A', qty=3, detail_id=1)]),
    )
    parts_order = _upsert_parts_order(parsed)
    line = parts_order.lines.get()
    line.received = True
    line.received_dt = timezone.now()
    line.save(update_fields=['received', 'received_dt'])

    # Resync: same DetailId, but quantity/status changed - should update in place, not
    # replace the row, so the manually-set received flag survives.
    resynced = _parse_digikey_order(
        _raw_sales_order(order_id='SO4', lines=[_raw_line(sku='SKU-A', qty=5, detail_id=1)]),
    )
    parts_order = _upsert_parts_order(resynced)

    line.refresh_from_db()
    assert parts_order.lines.count() == 1
    assert line.received is True
    assert line.received_dt is not None
    assert line.quantity == 5


@pytest.mark.django_db
def test_upsert_parts_order_deletes_line_no_longer_present_in_resync():
    parsed = _parse_digikey_order(_raw_sales_order(order_id='SO5', lines=[
        _raw_line(sku='SKU-A', detail_id=1), _raw_line(sku='SKU-B', detail_id=2),
    ]))
    parts_order = _upsert_parts_order(parsed)
    assert parts_order.lines.count() == 2

    resynced = _parse_digikey_order(_raw_sales_order(order_id='SO5', lines=[_raw_line(sku='SKU-A', detail_id=1)]))
    parts_order = _upsert_parts_order(resynced)

    assert parts_order.lines.count() == 1
    assert parts_order.lines.first().supplier_sku == 'SKU-A'


@pytest.mark.django_db
def test_upsert_parts_order_blank_supplier_line_number_always_creates_fresh_row():
    # Defensive fallback path - shouldn't happen with real DigiKey data (DetailId is always
    # present), but a blank supplier_line_number must never merge two different lines.
    parsed = _parse_digikey_order(_raw_sales_order(order_id='SO6', lines=[
        _raw_line(sku='SKU-A', detail_id=None), _raw_line(sku='SKU-B', detail_id=None),
    ]))
    parts_order = _upsert_parts_order(parsed)

    assert parts_order.lines.count() == 2
    assert set(parts_order.lines.values_list('supplier_sku', flat=True)) == {'SKU-A', 'SKU-B'}

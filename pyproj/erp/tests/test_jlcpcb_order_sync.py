# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import base64
import hashlib
import hmac
from datetime import datetime, timezone as dt_timezone

import pytest

from crm.models import Org
from device.models import Design
from erp.models import Part, PartsOrder, PartsOrderLine
from erp.views import (
    _jlcpcb_order_status_label,
    _jlcpcb_sign_request,
    _map_jlcpcb_order_status,
    _parse_jlcpcb_date,
    _parse_jlcpcb_dt,
    _parse_jlcpcb_order,
    _parse_jlcpcb_order_item,
    _upsert_parts_order,
)


@pytest.fixture
def design():
    org = Org.objects.create(company_name='JLCPCB Sync Test Org')
    return Design.objects.create(client=org, sku='JLC1', name='JLCPCB Sync Test Design', hw_version='1.0')


def _set_jlcpcb_env(monkeypatch, app_id='APP1', access_key='ACCESS1', secret_key='SECRET1'):
    monkeypatch.setenv('JLCPCB_APP_ID', app_id)
    monkeypatch.setenv('JLCPCB_ACCESS_KEY', access_key)
    monkeypatch.setenv('JLCPCB_SECRET_KEY', secret_key)


def _order_item(order_type=1, count=1, price='10.00', order_status=4, file_name='design-v1.zip',
                 produce_code='PC1', order_date='2026-07-08 16:11:03', delivery_time='2026-07-15 00:00:00'):
    # order_status defaults to 4 ("Submitted to the factory") - a documented, non-edge-case
    # value, per the confirmed enum in Resources/JLCPCB-API/Order Information Query API.pdf.
    return {
        'orderType': order_type,
        'pcbItem': {
            'count': count, 'price': price, 'orderStatus': order_status, 'fileName': file_name,
            'produceCode': produce_code, 'orderDate': order_date, 'deliveryTime': delivery_time,
        },
    }


def _stencil_order_item():
    # Shape confirmed by the docs' own worked example: a Stencil (orderType 3) entry's data
    # lives under smtItem, with pcbItem absent/irrelevant.
    return {
        'orderType': 3,
        'smtItem': {'produceCode': 'SMT1', 'fileName': 'stencil.zip', 'count': 1, 'price': '20.00'},
    }


# --- _jlcpcb_sign_request ---

def test_jlcpcb_sign_request_string_to_sign_format(monkeypatch):
    _set_jlcpcb_env(monkeypatch)

    auth = _jlcpcb_sign_request(
        'post', '/overseas/openapi/pcb/order/detail', body_json='{"batchNum": "B1"}',
        timestamp='1700000000', nonce='nonce1234567890123456789012345678',
    )

    expected_string_to_sign = (
        'POST\n/overseas/openapi/pcb/order/detail\n1700000000\n'
        'nonce1234567890123456789012345678\n{"batchNum": "B1"}\n'
    )
    expected_signature = base64.b64encode(
        hmac.new(b'SECRET1', expected_string_to_sign.encode('utf-8'), hashlib.sha256).digest()
    ).decode('utf-8')

    assert auth == (
        f'JOP appid="APP1",accesskey="ACCESS1",timestamp="1700000000",'
        f'nonce="nonce1234567890123456789012345678",signature="{expected_signature}"'
    )


def test_jlcpcb_sign_request_method_uppercased_and_no_body_is_empty_string(monkeypatch):
    _set_jlcpcb_env(monkeypatch)

    auth = _jlcpcb_sign_request(
        'get', '/overseas/openapi/jpay/customerJpayAccount/getAccountDetail',
        timestamp='1700000000', nonce='n' * 32,
    )

    expected_string_to_sign = (
        f'GET\n/overseas/openapi/jpay/customerJpayAccount/getAccountDetail\n1700000000\n{"n" * 32}\n\n'
    )
    expected_signature = base64.b64encode(
        hmac.new(b'SECRET1', expected_string_to_sign.encode('utf-8'), hashlib.sha256).digest()
    ).decode('utf-8')
    assert f'signature="{expected_signature}"' in auth


def test_jlcpcb_sign_request_query_params_appended_to_canonical_uri(monkeypatch):
    _set_jlcpcb_env(monkeypatch)

    auth = _jlcpcb_sign_request(
        'get', '/some/path', query_params={'batchNum': 'B1'}, timestamp='1700000000', nonce='n' * 32,
    )

    expected_string_to_sign = f'GET\n/some/path?batchNum=B1\n1700000000\n{"n" * 32}\n\n'
    expected_signature = base64.b64encode(
        hmac.new(b'SECRET1', expected_string_to_sign.encode('utf-8'), hashlib.sha256).digest()
    ).decode('utf-8')
    assert f'signature="{expected_signature}"' in auth


def test_jlcpcb_sign_request_random_nonce_and_timestamp_when_not_supplied(monkeypatch):
    _set_jlcpcb_env(monkeypatch)

    auth1 = _jlcpcb_sign_request('get', '/x')
    auth2 = _jlcpcb_sign_request('get', '/x')

    assert auth1 != auth2  # different nonce each time -> different signature


# --- _parse_jlcpcb_dt / _parse_jlcpcb_date ---

def test_parse_jlcpcb_dt_parses_space_separated_format():
    assert _parse_jlcpcb_dt('2026-07-08 16:11:03') == datetime(2026, 7, 8, 16, 11, 3, tzinfo=dt_timezone.utc)


def test_parse_jlcpcb_dt_parses_epoch_millis():
    result = _parse_jlcpcb_dt(1700000000000)
    assert result == datetime.fromtimestamp(1700000000, tz=dt_timezone.utc)


def test_parse_jlcpcb_dt_returns_none_for_missing_or_unparseable():
    assert _parse_jlcpcb_dt(None) is None
    assert _parse_jlcpcb_dt('') is None
    assert _parse_jlcpcb_dt('not-a-date') is None


def test_parse_jlcpcb_date_returns_date_not_datetime():
    result = _parse_jlcpcb_date('2026-07-15 00:00:00')
    assert result == datetime(2026, 7, 15, tzinfo=dt_timezone.utc).date()
    assert _parse_jlcpcb_date(None) is None


# --- _map_jlcpcb_order_status / _jlcpcb_order_status_label ---

@pytest.mark.parametrize('raw, expected', [
    (0, PartsOrderLine.CANCELLED),
    (1, PartsOrderLine.OPEN),
    (2, PartsOrderLine.OPEN),
    (3, PartsOrderLine.OPEN),
    (4, PartsOrderLine.OPEN),
    (5, PartsOrderLine.SHIPPED),
    (7, PartsOrderLine.OPEN),  # the docs' own worked example uses this undocumented value
    (None, PartsOrderLine.OPEN),
    ('not-an-int', PartsOrderLine.OPEN),
])
def test_map_jlcpcb_order_status(raw, expected):
    assert _map_jlcpcb_order_status(raw) == expected


@pytest.mark.parametrize('raw, expected', [
    (0, 'Cancelled'),
    (5, 'Shipped'),
    (7, 'Unknown (7)'),
    (None, ''),
    ('not-an-int', ''),
])
def test_jlcpcb_order_status_label(raw, expected):
    assert _jlcpcb_order_status_label(raw) == expected


# --- _parse_jlcpcb_order_item ---

def test_parse_jlcpcb_order_item_maps_fields():
    item = _order_item(count=5, price='50.00', file_name='board.zip', produce_code='PC9')

    parsed = _parse_jlcpcb_order_item(item, order_status=PartsOrderLine.OPEN, currency='USD', line_index=0)

    assert parsed['supplier_sku'] == 'PC9'
    assert parsed['supplier_line_number'] == 'PC9'  # produceCode, a real per-item id per the docs - not positional
    assert parsed['description'] == 'board.zip'
    assert parsed['quantity'] == 5
    assert parsed['unit_price'] == 10  # price / count - plausible against the docs' own worked example (5/10)
    assert parsed['currency'] == 'USD'
    assert parsed['status'] == PartsOrderLine.OPEN


def test_parse_jlcpcb_order_item_falls_back_to_positional_line_number_when_produce_code_blank():
    item = _order_item(produce_code='')

    parsed = _parse_jlcpcb_order_item(item, order_status=PartsOrderLine.OPEN, currency='USD', line_index=2)

    assert parsed['supplier_sku'] == ''
    assert parsed['supplier_line_number'] == '2'


def test_parse_jlcpcb_order_item_handles_missing_price():
    item = _order_item(count=3)
    item['pcbItem']['price'] = None

    parsed = _parse_jlcpcb_order_item(item, order_status=PartsOrderLine.OPEN, currency='USD', line_index=0)

    assert parsed['unit_price'] is None


# --- _parse_jlcpcb_order ---

def test_parse_jlcpcb_order_maps_top_level_fields():
    data = {'orderItem': [_order_item(order_status=5)]}

    parsed = _parse_jlcpcb_order(data, batch_num='BATCH123')

    assert parsed['supplier_order_number'] == 'BATCH123'
    assert parsed['supplier_order_url'] == ''
    assert parsed['order_dt'] == datetime(2026, 7, 8, 16, 11, 3, tzinfo=dt_timezone.utc)
    assert parsed['expected_arrival_date'] == datetime(2026, 7, 15, tzinfo=dt_timezone.utc).date()
    assert parsed['status'] == 'Shipped'
    assert len(parsed['lines']) == 1
    assert parsed['lines'][0]['status'] == PartsOrderLine.SHIPPED


def test_parse_jlcpcb_order_handles_empty_order_items():
    parsed = _parse_jlcpcb_order({'orderItem': []}, batch_num='BATCH123')
    assert parsed['lines'] == []
    assert parsed['order_dt'] is None
    assert parsed['status'] == ''


def test_parse_jlcpcb_order_handles_missing_order_item_key():
    parsed = _parse_jlcpcb_order({}, batch_num='BATCH123')
    assert parsed['lines'] == []


def test_parse_jlcpcb_order_multiple_items_use_produce_code_as_line_number():
    data = {'orderItem': [_order_item(produce_code='PC1'), _order_item(produce_code='PC2')]}

    parsed = _parse_jlcpcb_order(data, batch_num='BATCH123')

    assert [line['supplier_line_number'] for line in parsed['lines']] == ['PC1', 'PC2']
    assert [line['supplier_sku'] for line in parsed['lines']] == ['PC1', 'PC2']


def test_parse_jlcpcb_order_excludes_stencil_order_items():
    # orderType 3 (Stencil) entries carry their data under smtItem, not pcbItem - this app
    # only tracks PCB orders (orderType 1), so a mixed order should only surface the PCB line.
    data = {'orderItem': [_order_item(produce_code='PC1'), _stencil_order_item()]}

    parsed = _parse_jlcpcb_order(data, batch_num='BATCH123')

    assert len(parsed['lines']) == 1
    assert parsed['lines'][0]['supplier_sku'] == 'PC1'


def test_parse_jlcpcb_order_all_stencil_items_yields_no_lines_and_blank_status():
    data = {'orderItem': [_stencil_order_item()]}

    parsed = _parse_jlcpcb_order(data, batch_num='BATCH123')

    assert parsed['lines'] == []
    assert parsed['status'] == ''


# --- _upsert_parts_order with part_matcher=None (issue #100) ---
#
# JLCPCB lines are never matched/created as Parts any more (produceCode isn't stable across
# reorders - see _sync_jlcpcb_parts_order's docstring). Instead each line's `design` is left
# unset by _upsert_parts_order entirely and is set later, by hand, per line, via
# parts_order_line_set_design - see erp/tests/test_parts_order_views.py for that path.

@pytest.mark.django_db
def test_upsert_parts_order_with_none_matcher_leaves_part_and_variant_none():
    parsed = _parse_jlcpcb_order({'orderItem': [_order_item(produce_code='PC1', count=10)]}, batch_num='BATCH1')

    parts_order = _upsert_parts_order(parsed, supplier_name='JLCPCB', part_matcher=None)

    assert parts_order.supplier_name == 'JLCPCB'
    assert parts_order.supplier_order_number == 'BATCH1'
    assert parts_order.lines.count() == 1
    line = parts_order.lines.first()
    assert line.supplier_sku == 'PC1'
    assert line.quantity == 10
    assert line.part is None
    assert line.part_source_variant is None
    assert line.design is None
    assert Part.objects.count() == 0  # confirms no stray Part was created


@pytest.mark.django_db
def test_upsert_parts_order_jlcpcb_reuses_row_on_resubmit():
    # parts_order_add_jlcpcb re-submits an existing batchNum to manually refresh it -
    # relies on _upsert_parts_order's update_or_create behaviour, not a new row each time.
    parsed = _parse_jlcpcb_order({'orderItem': [_order_item(order_status=4)]}, batch_num='BATCH1')
    _upsert_parts_order(parsed, supplier_name='JLCPCB', part_matcher=None)

    resynced = _parse_jlcpcb_order({'orderItem': [_order_item(order_status=5)]}, batch_num='BATCH1')
    _upsert_parts_order(resynced, supplier_name='JLCPCB', part_matcher=None)

    assert PartsOrder.objects.filter(supplier_name='JLCPCB', supplier_order_number='BATCH1').count() == 1
    assert PartsOrder.objects.get(supplier_name='JLCPCB', supplier_order_number='BATCH1').status == 'Shipped'


@pytest.mark.django_db
def test_upsert_parts_order_jlcpcb_resync_preserves_a_human_set_design(design):
    # design is never part of _upsert_parts_order's line defaults, so a resync (e.g. the
    # scheduled refresh_parts_orders run, which never knows about designs at all) must never
    # clobber an association a human set via parts_order_line_set_design.
    parsed = _parse_jlcpcb_order({'orderItem': [_order_item(produce_code='PC1')]}, batch_num='BATCH1')
    parts_order = _upsert_parts_order(parsed, supplier_name='JLCPCB', part_matcher=None)
    line = parts_order.lines.get(supplier_sku='PC1')
    line.design = design
    line.save(update_fields=['design'])

    resynced = _parse_jlcpcb_order({'orderItem': [_order_item(produce_code='PC1', order_status=5)]}, batch_num='BATCH1')
    _upsert_parts_order(resynced, supplier_name='JLCPCB', part_matcher=None)

    line.refresh_from_db()
    assert line.design_id == design.pk


@pytest.mark.django_db
def test_upsert_parts_order_jlcpcb_does_not_collide_with_other_suppliers_sharing_the_number():
    digikey_parsed = {
        'supplier_order_number': 'SHARED1', 'supplier_order_url': '', 'order_dt': None,
        'expected_arrival_date': None, 'status': '', 'lines': [],
    }
    jlcpcb_parsed = dict(digikey_parsed)

    _upsert_parts_order(digikey_parsed, supplier_name='DigiKey')
    _upsert_parts_order(jlcpcb_parsed, supplier_name='JLCPCB', part_matcher=None)

    assert PartsOrder.objects.filter(supplier_order_number='SHARED1').count() == 2
    assert Part.objects.count() == 0  # confirms no stray Parts were created for either row


# --- PartsOrderLine.display_sku ---

@pytest.mark.django_db
def test_display_sku_compounds_filename_and_produce_code_for_jlcpcb():
    parts_order = PartsOrder.objects.create(supplier_name='JLCPCB', supplier_order_number='BATCH1')
    line = PartsOrderLine.objects.create(
        parts_order=parts_order, supplier_sku='Y466', description='BeetleBot-v1_0.zip', quantity=1,
    )

    assert line.display_sku == 'BeetleBot-v1_0_Y466'


@pytest.mark.django_db
def test_display_sku_strips_whatever_extension_is_present_not_just_zip():
    parts_order = PartsOrder.objects.create(supplier_name='JLCPCB', supplier_order_number='BATCH1')
    line = PartsOrderLine.objects.create(
        parts_order=parts_order, supplier_sku='Y466', description='BeetleBot-v1_0.rar', quantity=1,
    )

    assert line.display_sku == 'BeetleBot-v1_0_Y466'


@pytest.mark.django_db
def test_display_sku_falls_back_to_filename_alone_when_produce_code_blank():
    parts_order = PartsOrder.objects.create(supplier_name='JLCPCB', supplier_order_number='BATCH1')
    line = PartsOrderLine.objects.create(
        parts_order=parts_order, supplier_sku='', description='BeetleBot-v1_0.zip', quantity=1,
    )

    assert line.display_sku == 'BeetleBot-v1_0'


@pytest.mark.django_db
def test_display_sku_falls_back_to_supplier_sku_when_description_blank():
    parts_order = PartsOrder.objects.create(supplier_name='JLCPCB', supplier_order_number='BATCH1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, supplier_sku='Y466', description='', quantity=1)

    assert line.display_sku == 'Y466'


@pytest.mark.django_db
def test_display_sku_is_plain_supplier_sku_for_non_jlcpcb_suppliers():
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    line = PartsOrderLine.objects.create(
        parts_order=parts_order, supplier_sku='DK123', description='Some Part', quantity=1,
    )

    assert line.display_sku == 'DK123'

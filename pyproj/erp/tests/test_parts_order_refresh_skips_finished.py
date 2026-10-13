# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
"""Bulk parts-order refreshes skip finished orders (every non-cancelled line received), so
they don't spend a per-order supplier API call on orders that can no longer change. The
supplier HTTP calls themselves are stubbed out via monkeypatch."""
from datetime import timedelta
from types import SimpleNamespace

from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone
import pytest

from erp import views
from erp.models import PartsOrder, PartsOrderLine


def _order(supplier_name, number, lines=()):
    """lines: (received, status) pairs."""
    parts_order = PartsOrder.objects.create(supplier_name=supplier_name, supplier_order_number=number)
    for index, (received, status) in enumerate(lines):
        PartsOrderLine.objects.create(
            parts_order=parts_order, supplier_sku=f'SKU{index}', supplier_line_number=str(index),
            quantity=1, received=received, status=status,
        )
    return parts_order


RECEIVED = (True, PartsOrderLine.RECEIVED)
OPEN = (False, PartsOrderLine.OPEN)
CANCELLED = (False, PartsOrderLine.CANCELLED)


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)


@pytest.fixture
def jlcpcb_env(monkeypatch):
    monkeypatch.setenv('JLCPCB_APP_ID', 'APP1')
    monkeypatch.setenv('JLCPCB_ACCESS_KEY', 'ACCESS1')
    monkeypatch.setenv('JLCPCB_SECRET_KEY', 'SECRET1')


# --- _finished_parts_order_numbers ---

@pytest.mark.django_db
def test_finished_includes_order_with_every_line_received():
    _order('LCSC', 'DONE', [RECEIVED, RECEIVED])

    assert views._finished_parts_order_numbers('LCSC') == {'DONE'}


@pytest.mark.django_db
def test_finished_excludes_order_with_an_unreceived_line():
    _order('LCSC', 'PARTLY', [RECEIVED, OPEN])

    assert views._finished_parts_order_numbers('LCSC') == set()


@pytest.mark.django_db
def test_finished_ignores_cancelled_lines():
    _order('LCSC', 'DONE-WITH-CANCELLED', [RECEIVED, CANCELLED])
    _order('LCSC', 'ALL-CANCELLED', [CANCELLED, CANCELLED])

    assert views._finished_parts_order_numbers('LCSC') == {'DONE-WITH-CANCELLED', 'ALL-CANCELLED'}


@pytest.mark.django_db
def test_finished_excludes_order_with_no_lines():
    _order('LCSC', 'EMPTY')

    assert views._finished_parts_order_numbers('LCSC') == set()


@pytest.mark.django_db
def test_finished_is_scoped_to_one_supplier():
    _order('LCSC', 'SAME-NUMBER', [RECEIVED])
    _order('JLCPCB', 'OTHER', [RECEIVED])

    assert views._finished_parts_order_numbers('LCSC') == {'SAME-NUMBER'}


# --- per-supplier sync loops ---

@pytest.mark.django_db
def test_mouser_sync_skips_detail_call_for_finished_orders(monkeypatch):
    _order('Mouser', '1001', [RECEIVED])
    _order('Mouser', '1002', [OPEN])
    monkeypatch.setenv('MOUSER_ORDER_API_KEY', 'KEY')
    monkeypatch.setattr(views, '_mouser_order_history_list', lambda *args: {
        'OrderHistoryItems': [{'SalesOrderNumber': n} for n in (1001, 1002, 1003)],
    })
    detail_calls = []
    monkeypatch.setattr(views, '_mouser_order_detail', lambda key, number: detail_calls.append(number) or {})
    monkeypatch.setattr(views, '_parse_mouser_order', lambda item, detail: item)
    monkeypatch.setattr(views, '_upsert_parts_order', lambda *args, **kwargs: None)
    monkeypatch.setattr(views.time, 'sleep', lambda seconds: None)

    today = timezone.now().date()
    result = views._sync_mouser_parts_orders(today - timedelta(days=90), today)

    assert detail_calls == [1002, 1003]
    assert result == {'ok': True, 'orders_synced': 2, 'orders_skipped': 1}


@pytest.mark.django_db
def test_lcsc_sync_skips_detail_call_for_finished_orders(monkeypatch, tmp_path):
    _order('LCSC', 'WM-DONE', [RECEIVED])
    _order('LCSC', 'WM-OPEN', [OPEN])
    session_file = tmp_path / 'session.json'
    session_file.write_text('{"cookies": []}')
    monkeypatch.setenv('LCSC_SESSION_FILE', str(session_file))

    created = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    detail_calls = []

    class FakeOrdersClient:
        def __init__(self, session):
            pass

        def iter_orders(self, **kwargs):
            for code in ('WM-NEW', 'WM-DONE', 'WM-OPEN'):
                yield SimpleNamespace(order_code=code, uuid=f'uuid-{code}', create_time=created)

        def get_order_detail(self, uuid):
            detail_calls.append(uuid)

    import lcsc_toolkit.orders
    monkeypatch.setattr(lcsc_toolkit.orders, 'OrdersClient', FakeOrdersClient)
    monkeypatch.setattr(views, '_parse_lcsc_order', lambda summary, detail: summary)
    monkeypatch.setattr(views, '_upsert_parts_order', lambda *args, **kwargs: None)

    today = timezone.now().date()
    result = views._sync_lcsc_parts_orders(today - timedelta(days=90), today)

    assert detail_calls == ['uuid-WM-NEW', 'uuid-WM-OPEN']
    assert result == {'ok': True, 'orders_synced': 2, 'orders_skipped': 1}


@pytest.mark.django_db
def test_known_jlcpcb_sync_skips_finished_orders(monkeypatch, jlcpcb_env):
    _order('JLCPCB', 'B-DONE', [RECEIVED, CANCELLED])
    _order('JLCPCB', 'B-OPEN', [OPEN])
    _order('JLCPCB', 'B-EMPTY')
    synced = []
    monkeypatch.setattr(views, '_sync_jlcpcb_parts_order', lambda batch_num: synced.append(batch_num) or {'ok': True})

    result = views._sync_known_jlcpcb_parts_orders()

    assert sorted(synced) == ['B-EMPTY', 'B-OPEN']
    assert result == {'ok': True, 'orders_synced': 2, 'orders_skipped': 1, 'errors': []}


@pytest.mark.django_db
def test_known_jlcpcb_sync_reports_each_failure_with_its_batch_number(monkeypatch, jlcpcb_env):
    _order('JLCPCB', 'B-1', [OPEN])
    _order('JLCPCB', 'B-2', [OPEN])
    monkeypatch.setattr(views, '_sync_jlcpcb_parts_order', lambda batch_num: {'ok': False, 'error': 'boom'})

    result = views._sync_known_jlcpcb_parts_orders()

    assert result['ok'] is False
    assert sorted(result['errors']) == ['B-1: boom', 'B-2: boom']
    assert 'B-1: boom' in result['error']


# --- the Refresh Orders view ---

@pytest.mark.django_db
def test_refresh_view_queues_synced_and_skipped_summary(client, staff_user, monkeypatch, jlcpcb_env):
    monkeypatch.delenv('MOUSER_ORDER_API_KEY', raising=False)
    monkeypatch.delenv('LCSC_SESSION_FILE', raising=False)
    monkeypatch.setattr(views, '_sync_digikey_parts_orders', lambda *args: {'ok': True, 'orders_synced': 3})
    monkeypatch.setattr(views, '_sync_known_jlcpcb_parts_orders', lambda: {
        'ok': True, 'orders_synced': 1, 'orders_skipped': 4, 'errors': [],
    })

    client.force_login(staff_user)
    response = client.post(reverse('erp:parts_order_refresh'))

    assert response.json()['ok'] is True
    assert [str(m) for m in get_messages(response.wsgi_request)] == [
        'Refreshed 4 orders. Skipped 4 finished orders (every line received).'
    ]


@pytest.mark.django_db
def test_refresh_view_queues_no_summary_on_failure(client, staff_user, monkeypatch):
    monkeypatch.delenv('MOUSER_ORDER_API_KEY', raising=False)
    monkeypatch.delenv('LCSC_SESSION_FILE', raising=False)
    monkeypatch.delenv('JLCPCB_APP_ID', raising=False)
    monkeypatch.setattr(views, '_sync_digikey_parts_orders', lambda *args: {'ok': False, 'error': 'nope'})

    client.force_login(staff_user)
    response = client.post(reverse('erp:parts_order_refresh'))

    assert response.json()['ok'] is False
    assert list(get_messages(response.wsgi_request)) == []


# --- the receiving-status dot on the Parts Orders list agrees with "finished" ---

@pytest.mark.django_db
@pytest.mark.parametrize('lines, expected', [
    ([], 'bg-secondary'),
    ([OPEN, OPEN], 'bg-secondary'),
    ([RECEIVED, OPEN], 'bg-info'),
    ([RECEIVED, RECEIVED], 'bg-success'),
    ([RECEIVED, CANCELLED], 'bg-success'),
    ([CANCELLED, CANCELLED], 'bg-success'),
    ([OPEN, CANCELLED], 'bg-secondary'),
])
def test_receiving_status_color_ignores_cancelled_lines(lines, expected):
    parts_order = _order('JLCPCB', 'B-1', lines)

    assert parts_order.get_receiving_status_color_class() == expected


@pytest.mark.django_db
@pytest.mark.parametrize('lines', [[], [OPEN], [RECEIVED, OPEN], [RECEIVED], [RECEIVED, CANCELLED], [CANCELLED]])
def test_green_dot_exactly_when_order_is_finished(lines):
    parts_order = _order('JLCPCB', 'B-1', lines)

    is_green = parts_order.get_receiving_status_color_class() == 'bg-success'
    assert is_green == ('B-1' in views._finished_parts_order_numbers('JLCPCB'))

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import pytest

from erp.views import _digikey_order_history_host, _digikey_order_url


# --- _digikey_order_history_host ---

def test_digikey_order_history_host_defaults_to_au(monkeypatch):
    monkeypatch.delenv('DIGIKEY_LOCALE_SITE', raising=False)
    assert _digikey_order_history_host() == 'www.digikey.com.au'


def test_digikey_order_history_host_respects_locale_site_env_var(monkeypatch):
    monkeypatch.setenv('DIGIKEY_LOCALE_SITE', 'UK')
    assert _digikey_order_history_host() == 'www.digikey.co.uk'


def test_digikey_order_history_host_defaults_to_us_for_unmapped_locale(monkeypatch):
    monkeypatch.setenv('DIGIKEY_LOCALE_SITE', 'DE')
    assert _digikey_order_history_host() == 'www.digikey.com'


# --- _digikey_order_url ---

def test_digikey_order_url_uses_order_number_not_sales_order_id(monkeypatch):
    # Regression check: DigiKey's OrderHistory/ReviewOrder page 404s on the Sales Order ID
    # (PartsOrder.supplier_order_number) - it needs the separate OrderNumber value instead,
    # confirmed by comparing a real order against what actually resolves on DigiKey's site.
    monkeypatch.setenv('DIGIKEY_LOCALE_SITE', 'AU')
    assert _digikey_order_url(9910000373735576) == (
        'https://www.digikey.com.au/OrderHistory/ReviewOrder/9910000373735576'
    )


def test_digikey_order_url_blank_for_missing_order_number():
    assert _digikey_order_url(None) == ''
    assert _digikey_order_url('') == ''


def test_digikey_order_url_percent_encodes_order_number(monkeypatch):
    monkeypatch.setenv('DIGIKEY_LOCALE_SITE', 'AU')
    assert _digikey_order_url('SO 1/2') == 'https://www.digikey.com.au/OrderHistory/ReviewOrder/SO%201%2F2'


@pytest.mark.django_db
def test_upsert_parts_order_persists_supplier_order_url(monkeypatch):
    from erp.views import _parse_digikey_order, _upsert_parts_order

    monkeypatch.setenv('DIGIKEY_LOCALE_SITE', 'AU')
    raw_sales_order = {
        'SalesOrderId': 100259094,
        'OrderNumber': 9910000373735576,
        'DateEntered': '2026-06-01T10:00:00Z',
        'Currency': 'USD',
        'Status': {'SalesOrderStatus': 'Shipped'},
        'LineItems': [],
    }

    parts_order = _upsert_parts_order(_parse_digikey_order(raw_sales_order))

    assert parts_order.supplier_order_number == '100259094'
    assert parts_order.supplier_order_url == (
        'https://www.digikey.com.au/OrderHistory/ReviewOrder/9910000373735576'
    )

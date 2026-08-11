# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from erp.models import PartsOrder
from erp.views import (
    PARTS_ORDER_REFRESH_LOOKBACK_DAYS, _jlcpcb_configured, _sync_digikey_parts_orders, _sync_jlcpcb_parts_order,
    _sync_mouser_parts_orders,
)


class Command(BaseCommand):
    help = (
        "Refresh PartsOrder/PartsOrderLine data from supplier order-status APIs "
        "(DigiKey; Mouser if MOUSER_ORDER_API_KEY is configured; JLCPCB if its three "
        "JLCPCB_* env vars are configured). Part.incoming_stock is read live from "
        "PartsOrderLine, so there's nothing further to recompute once lines are synced. "
        "Intended to run on a cron schedule; see SETUP.md - note Mouser's Order History API "
        "needs one extra call per order (unlike DigiKey's single paginated call), so a busy "
        "Mouser account may warrant a coarser cron cadence to stay within Mouser's 30 "
        "calls/minute, 1000 calls/day limit. DigiKey/Mouser use a rolling lookback window "
        "rather than a 'last synced' cursor, so a status change on an already-synced order, "
        "a missed cron run, or a locally-deleted PartsOrder all self-heal on the next run. "
        "JLCPCB has no discovery endpoint at all (unlike the other two), so it instead "
        "re-syncs every already-known JLCPCB PartsOrder one at a time - see "
        "erp.views._sync_jlcpcb_parts_order. LCSC is deliberately NOT included here - see "
        "erp.views.parts_order_refresh's module comment for why."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--lookback-days', type=int, default=PARTS_ORDER_REFRESH_LOOKBACK_DAYS,
            help=f'How many days back to check for orders (default: {PARTS_ORDER_REFRESH_LOOKBACK_DAYS}).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report the date range that would be queried without calling any supplier API.',
        )

    def handle(self, *args, **options):
        to_date = timezone.now().date()
        from_date = to_date - timedelta(days=options['lookback_days'])

        if options['dry_run']:
            self.stdout.write(f'Would sync DigiKey parts orders from {from_date} to {to_date}.')
            if os.environ.get('MOUSER_ORDER_API_KEY', '').strip():
                self.stdout.write(f'Would sync Mouser parts orders from {from_date} to {to_date}.')
            if _jlcpcb_configured():
                jlcpcb_count = PartsOrder.objects.filter(supplier_name='JLCPCB').count()
                self.stdout.write(f'Would re-sync {jlcpcb_count} existing JLCPCB parts order(s).')
            return

        digikey_result = _sync_digikey_parts_orders(from_date, to_date)
        if digikey_result.get('ok'):
            self.stdout.write(f"DigiKey OK: synced {digikey_result.get('orders_synced', 0)} order(s).")
        else:
            self.stderr.write(f"DigiKey FAILED: {digikey_result.get('error')}")

        if os.environ.get('MOUSER_ORDER_API_KEY', '').strip():
            mouser_result = _sync_mouser_parts_orders(from_date, to_date)
            if mouser_result.get('ok'):
                self.stdout.write(f"Mouser OK: synced {mouser_result.get('orders_synced', 0)} order(s).")
            else:
                self.stderr.write(f"Mouser FAILED: {mouser_result.get('error')}")

        if _jlcpcb_configured():
            errors = []
            synced = 0
            for order in PartsOrder.objects.filter(supplier_name='JLCPCB'):
                result = _sync_jlcpcb_parts_order(order.supplier_order_number)
                if result.get('ok'):
                    synced += 1
                else:
                    errors.append(f"{order.supplier_order_number}: {result.get('error')}")
            self.stdout.write(f"JLCPCB OK: synced {synced} order(s).")
            for error in errors:
                self.stderr.write(f"JLCPCB FAILED: {error}")

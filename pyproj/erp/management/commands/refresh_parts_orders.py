# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from erp.views import PARTS_ORDER_REFRESH_LOOKBACK_DAYS, _sync_digikey_parts_orders


class Command(BaseCommand):
    help = (
        "Refresh PartsOrder/PartsOrderLine data from supplier order-status APIs "
        "(DigiKey only for now). Part.incoming_stock is read live from PartsOrderLine, "
        "so there's nothing further to recompute once lines are synced. "
        "Intended to run on a cron schedule (e.g. every few hours); see SETUP.md. "
        "Deliberately simpler than refresh_part_sources: this is one supplier making "
        "one (paginated) date-range list call - SearchOrders returns full line-item "
        "detail per order already, so no separate per-order detail call multiplies "
        "request count with order volume, and no per-supplier batching/rate-limit dict "
        "is needed. Uses a rolling lookback window rather than a 'last synced' cursor, "
        "so a status change on an already-synced order, a missed cron run, or a "
        "locally-deleted PartsOrder all self-heal on the next run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--lookback-days', type=int, default=PARTS_ORDER_REFRESH_LOOKBACK_DAYS,
            help=f'How many days back to check for orders (default: {PARTS_ORDER_REFRESH_LOOKBACK_DAYS}).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report the date range that would be queried without calling the DigiKey API.',
        )

    def handle(self, *args, **options):
        to_date = timezone.now().date()
        from_date = to_date - timedelta(days=options['lookback_days'])

        if options['dry_run']:
            self.stdout.write(f'Would sync DigiKey parts orders from {from_date} to {to_date}.')
            return

        result = _sync_digikey_parts_orders(from_date, to_date)

        if result.get('ok'):
            self.stdout.write(f"OK: synced {result.get('orders_synced', 0)} order(s).")
        else:
            self.stderr.write(f"FAILED: {result.get('error')}")

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import math
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from erp.models import PartSourceVariant
from erp.views import _refresh_variant

REFRESH_INTERVAL = timedelta(hours=24)

# Minimum gap (seconds) between consecutive API calls to the same supplier within
# one run. LCSC is an unofficial/undocumented API so gets the most conservative
# value; the others have published per-minute limits comfortably above these rates.
SUPPLIER_MIN_INTERVAL = {
    'lcsc': 3.0,
    'digikey': 1.0,
    'mouser': 2.0,
    'element14': 2.0,
}
DEFAULT_MIN_INTERVAL = 2.0


def _supplier_bucket(supplier_name):
    """Map a PartSource.supplier_name to the same supplier grouping _refresh_variant uses."""
    name = supplier_name.lower()
    if name == 'lcsc':
        return 'lcsc'
    if 'digikey' in name:
        return 'digikey'
    if name == 'mouser':
        return 'mouser'
    if 'element14' in name or 'farnell' in name or 'newark' in name:
        return 'element14'
    return 'other'


class Command(BaseCommand):
    help = (
        "Refresh PartSourceVariant pricing/stock/MOQ from supplier APIs, a bounded "
        "batch at a time. Intended to run hourly via cron: each run only refreshes "
        "the most stale variants (roughly total/24), spreading a day's worth of "
        "supplier API calls across 24 runs instead of one nightly burst."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-per-run', type=int, default=50,
            help='Upper bound on how many variants to refresh in one invocation, regardless of '
                 'how many are due (default: 50). Protects suppliers from a burst if a backlog '
                 'has built up, e.g. after a missed cron run.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='List which variants would be refreshed without calling any supplier API.',
        )

    def handle(self, *args, **options):
        total_variants = PartSourceVariant.objects.count()
        if total_variants == 0:
            self.stdout.write('No part source variants to refresh.')
            return

        cutoff = timezone.now() - REFRESH_INTERVAL
        due_qs = PartSourceVariant.objects.filter(
            Q(last_refreshed__isnull=True) | Q(last_refreshed__lt=cutoff)
        ).select_related('source').order_by('last_refreshed')
        total_due = due_qs.count()

        batch_size = min(max(1, math.ceil(total_variants / 24)), options['max_per_run'])
        due = list(due_qs[:batch_size])

        if not due:
            self.stdout.write('Nothing due for refresh.')
            return

        if options['dry_run']:
            for variant in due:
                self.stdout.write(f'Would refresh: {variant} (last_refreshed={variant.last_refreshed})')
            self.stdout.write(f'{len(due)} of {total_due} due variant(s) would be refreshed this run (of {total_variants} total).')
            return

        last_call_at = {}
        refreshed = failed = skipped = 0

        for variant in due:
            # A DigiKey refresh backfills last_refreshed on sibling SKUs too (see
            # _sync_digikey_sibling_variants), so a sibling later in this same batch may
            # already have been freshened as a side effect - re-check rather than repeat
            # the API call for it.
            variant.refresh_from_db(fields=['last_refreshed'])
            if variant.last_refreshed and variant.last_refreshed >= cutoff:
                skipped += 1
                self.stdout.write(f'Skipped (already refreshed via a sibling SKU this run): {variant}')
                continue

            bucket = _supplier_bucket(variant.source.supplier_name)
            min_interval = SUPPLIER_MIN_INTERVAL.get(bucket, DEFAULT_MIN_INTERVAL)
            last_at = last_call_at.get(bucket)
            if last_at is not None:
                elapsed = time.monotonic() - last_at
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
            last_call_at[bucket] = time.monotonic()

            try:
                result = _refresh_variant(variant)
            except Exception as e:
                result = {'ok': False, 'error': str(e)}

            variant.last_refreshed = timezone.now()
            variant.save(update_fields=['last_refreshed'])

            if result.get('ok'):
                refreshed += 1
                self.stdout.write(f'OK: {variant}')
            else:
                failed += 1
                self.stderr.write(f'FAILED: {variant}: {result.get("error")}')

        self.stdout.write(
            f'Done: {refreshed} refreshed, {failed} failed, {skipped} skipped (already fresh via a sibling) '
            f'({len(due)} of {total_due} due variants selected, {total_variants} total variants).'
        )

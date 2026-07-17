# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import importlib

from django.apps import apps as real_apps
import pytest

from erp.models import Part, PartSource

# Migration filenames aren't valid dotted-import identifiers, so import_module() is the
# standard way to reach one directly. No custom migration-state fixture exists in this
# project, so the function is exercised against the real (post-migration) app registry
# rather than a historical one - safe here since it only does plain ORM filter/bulk_create
# calls with no schema dependency beyond what already exists at HEAD.
_migration = importlib.import_module('erp.migrations.0040_backfill_partsourcestockhistory')


def _run_backfill():
    _migration.backfill_initial_stock_history(real_apps, None)


@pytest.mark.django_db
def test_backfill_seeds_history_for_a_stock_with_none():
    part = Part.objects.create(name='Backfill me', value='1')
    source = PartSource.objects.create(part=part, supplier_name='LCSC', stock=42)
    source.stock_history.all().delete()
    assert source.stock_history.count() == 0

    _run_backfill()

    assert list(source.stock_history.values_list('stock', flat=True)) == [42]


@pytest.mark.django_db
def test_backfill_skips_sources_that_already_have_history():
    part = Part.objects.create(name='Already tracked', value='1')
    source = PartSource.objects.create(part=part, supplier_name='LCSC', stock=42)
    assert source.stock_history.count() == 1  # from the normal save() path

    _run_backfill()

    assert source.stock_history.count() == 1


@pytest.mark.django_db
def test_backfill_skips_sources_with_unknown_stock():
    part = Part.objects.create(name='Unknown stock', value='1')
    source = PartSource.objects.create(part=part, supplier_name='LCSC', stock=None)
    source.stock_history.all().delete()

    _run_backfill()

    assert source.stock_history.count() == 0

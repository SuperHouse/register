# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings
from django.core import management
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


def _flush_app_data():
    """Delete all app data in reverse FK dependency order."""
    from erp.models import BatchProductionStage, Batch, BomEquivalenceRule, BomExclusionRule, BomLibrarySetting, Location, Part, PartAsset, PartCategory, PartSource, ProductionStageTemplateStep, ProductionStageTemplate, ProductionStage
    from device.models import DeviceEvent, DeviceAsset, DeviceImage, TestImage, TestRecord, Device, DesignAsset, Design
    from crm.models import Org
    from easy_thumbnails.models import Source, Thumbnail

    BatchProductionStage.objects.all().delete()
    Batch.objects.all().delete()
    ProductionStageTemplateStep.objects.all().delete()
    ProductionStageTemplate.objects.all().delete()
    ProductionStage.objects.all().delete()
    Location.objects.all().delete()
    PartCategory.objects.all().delete()
    PartAsset.objects.all().delete()
    PartSource.objects.all().delete()
    Part.objects.all().delete()
    BomEquivalenceRule.objects.all().delete()
    BomExclusionRule.objects.all().delete()
    BomLibrarySetting.objects.all().delete()
    DeviceEvent.objects.all().delete()
    DeviceAsset.objects.all().delete()
    DeviceImage.objects.all().delete()
    TestImage.objects.all().delete()
    TestRecord.objects.all().delete()
    Device.objects.all().delete()
    DesignAsset.objects.all().delete()
    Design.objects.all().delete()
    Org.objects.all().delete()
    Source.objects.all().delete()
    Thumbnail.objects.all().delete()


class Command(BaseCommand):
    help = 'Import application data and media files from a ZIP archive (replaces ALL existing data)'

    def add_arguments(self, parser):
        parser.add_argument('input', help='ZIP archive produced by export_data')
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Skip the confirmation prompt',
        )

    def handle(self, *args, **options):
        input_path = options['input']

        if not zipfile.is_zipfile(input_path):
            raise CommandError(f'{input_path} is not a valid ZIP file')

        with zipfile.ZipFile(input_path, 'r') as zf:
            names = set(zf.namelist())
            if 'manifest.json' not in names or 'data.json' not in names:
                raise CommandError(
                    'Archive is missing manifest.json or data.json — not a valid register export'
                )
            manifest = json.loads(zf.read('manifest.json'))

        if not options['yes']:
            self.stdout.write(self.style.WARNING(
                '\nWARNING: This will permanently delete ALL existing application data and\n'
                'replace it with the contents of the import archive. This cannot be undone.\n'
            ))
            self.stdout.write(f"  Archive date: {manifest['export_dt']}")
            self.stdout.write(f"  App version:  {manifest['app_version']}")
            self.stdout.write(f"  Records:      {manifest['record_count']}\n")
            confirm = input('Type "yes" to continue: ')
            if confirm.strip() != 'yes':
                self.stdout.write('Aborted.')
                return

        with zipfile.ZipFile(input_path, 'r') as zf:
            # Write fixture to a temp file so loaddata can infer format from extension.
            tmp_fd, tmp_path = tempfile.mkstemp(suffix='.json')
            try:
                with os.fdopen(tmp_fd, 'wb') as tmp:
                    tmp.write(zf.read('data.json'))

                with transaction.atomic():
                    self.stdout.write('Clearing existing data...')
                    _flush_app_data()

                    self.stdout.write('Loading database records...')
                    management.call_command('loaddata', tmp_path, verbosity=0)
            finally:
                os.unlink(tmp_path)

            self.stdout.write('Restoring media files...')
            media_root = Path(settings.MEDIA_ROOT) if settings.MEDIA_ROOT else None
            if not media_root:
                self.stdout.write(self.style.WARNING('MEDIA_ROOT is not configured — skipping media restore'))
            else:
                if media_root.exists():
                    shutil.rmtree(media_root)
                media_root.mkdir(parents=True, exist_ok=True)

                media_files = [n for n in zf.namelist() if n.startswith('media/') and not n.endswith('/')]
                for name in media_files:
                    rel_path = name[len('media/'):]
                    dest = media_root / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as src, open(dest, 'wb') as dst:
                        shutil.copyfileobj(src, dst)

                self.stdout.write(self.style.SUCCESS(
                    f'Import complete: {manifest["record_count"]} records and {len(media_files)} media files restored.'
                ))

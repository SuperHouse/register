# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import datetime
import io
import json
import zipfile
from pathlib import Path

import django
from django.conf import settings
from django.core import management
from django.core.management.base import BaseCommand

EXPORT_APPS = ['crm', 'device', 'erp']


class Command(BaseCommand):
    help = 'Export application data and media files to a ZIP archive'

    def add_arguments(self, parser):
        parser.add_argument(
            'output',
            nargs='?',
            help='Output ZIP file path (default: register-export-YYYY-MM-DD.zip in current directory)',
        )

    def handle(self, *args, **options):
        output = options['output'] or f'register-export-{datetime.date.today().isoformat()}.zip'

        self.stdout.write('Dumping database records...')
        buf = io.StringIO()
        management.call_command(
            'dumpdata',
            *EXPORT_APPS,
            format='json',
            indent=2,
            stdout=buf,
        )
        data = json.loads(buf.getvalue())

        # Strip Org.users M2M — user accounts are not included in the export.
        for obj in data:
            if obj['model'] == 'crm.org':
                obj['fields'].pop('users', None)

        manifest = {
            'export_dt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'app_version': settings.VERSION,
            'django_version': django.__version__,
            'record_count': len(data),
        }

        self.stdout.write(f'Writing {len(data)} records to {output}...')
        media_root = Path(settings.MEDIA_ROOT) if settings.MEDIA_ROOT else None
        thumbnail_basedir = getattr(settings, 'THUMBNAIL_BASEDIR', 'thumbs')
        media_file_count = 0

        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('manifest.json', json.dumps(manifest, indent=2))
            zf.writestr('data.json', json.dumps(data, indent=2))

            if media_root and media_root.exists():
                for file_path in sorted(media_root.rglob('*')):
                    if not file_path.is_file():
                        continue
                    rel = file_path.relative_to(media_root)
                    if rel.parts and rel.parts[0] == thumbnail_basedir:
                        continue  # thumbnails regenerate on access; skip them
                    zf.write(file_path, 'media/' + str(rel))
                    media_file_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Exported {len(data)} records and {media_file_count} media files to {output}'
        ))

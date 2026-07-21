# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import os

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Interactively capture an LCSC login session for the Parts Orders LCSC sync. "
        "This CANNOT run on the production server: it opens a real, visible browser "
        "window and needs a human to log in to LCSC by hand (including any CAPTCHA/2FA). "
        "Run it on a machine with a display - your desktop, not this server - then copy "
        "the saved session file to wherever LCSC_SESSION_FILE points on the server. "
        "Requires the lcsc-toolkit[auth] extra: pip install lcsc-toolkit[auth] && "
        "playwright install chromium."
    )

    def handle(self, *args, **options):
        session_file = os.environ.get('LCSC_SESSION_FILE', '').strip()
        if not session_file:
            raise CommandError('LCSC_SESSION_FILE is not set in .env - set it before running this command.')

        self.stdout.write(self.style.WARNING(
            "This opens a real browser window on THIS machine. If you're running this over "
            "SSH on a headless server, stop now - it won't work. Run it on a machine with a "
            "display instead (e.g. your desktop), then copy the resulting session file to "
            f"{session_file} on the server."
        ))

        try:
            from lcsc_toolkit.orders import LcscSession
        except ImportError:
            raise CommandError(
                'lcsc-toolkit is not installed in this environment. Run: pip install lcsc-toolkit'
            )

        try:
            session = LcscSession.capture_interactively()
        except RuntimeError as e:
            raise CommandError(
                f'{e}\nInstall it with: pip install lcsc-toolkit[auth] && playwright install chromium'
            )

        os.makedirs(os.path.dirname(session_file) or '.', exist_ok=True)
        session.save(session_file)
        self.stdout.write(f'Session saved to {session_file}')

        self.stdout.write('Confirming the saved session works...')
        try:
            if session.check_valid():
                self.stdout.write(self.style.SUCCESS('Confirmed - session is logged in and working.'))
            else:
                self.stdout.write(self.style.WARNING(
                    'check_valid() returned False - login may not have completed. Try again.'
                ))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Couldn't confirm session validity: {e}"))

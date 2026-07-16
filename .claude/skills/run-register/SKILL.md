---
name: run-register
description: Build, run, and drive the Testomatic Circuit Board Register (a Django web app) at pyproj/. Use when asked to start the dev server, run its tests, take a screenshot of a page, log in as a test user, or click through a UI change to verify it.
---

A Django app under `pyproj/`. Drive it by starting the dev server, then
using the Playwright driver at `.claude/skills/run-register/driver.py`
(installed into `pyproj/venv`) to log in as a dedicated test account,
navigate, click, and screenshot — `chromium-cli` isn't available in this
environment, so this script is the harness.

All paths below are relative to the repo root unless stated otherwise;
`cd pyproj` before any `python`/`pytest` command.

## Prerequisites

macOS or Linux with Python 3.13 (this app targets Django >=5.2,<6; any
recent Python 3 works). No system packages beyond Python itself were
needed in this environment — no Xvfb/GTK libs, because Playwright's
Chromium runs fully headless and this is a server-rendered web app, not
an Electron/desktop app.

## Setup

The venv, `conf/local_settings.py`, and `.env` should already exist in a
working checkout (see `SETUP.md` for first-time creation). To add the
browser-driving pieces used by this skill:

```bash
cd pyproj
source venv/bin/activate
pip install playwright pytest-playwright
playwright install chromium
```

This downloads Chromium (~170MB) into `~/Library/Caches/ms-playwright/`
(outside the repo — nothing to gitignore).

### Test account

The driver logs in as a dedicated automation account rather than a real
user's credentials. Its password is generated locally and written to
`.claude/skills/run-register/.test-account-password`, which is
gitignored — it's never hardcoded or committed. Create the account once
per database (safe to re-run — it's a `get_or_create` that also
regenerates the password each time):

```bash
cd pyproj
source venv/bin/activate
python manage.py shell -c "
import secrets
from authuser.models import User

password = secrets.token_urlsafe(16)
u, _ = User.objects.get_or_create(
    email='skill-agent@example.local',
    defaults={'full_name': 'Skill Agent (automation test user)'},
)
u.set_password(password)
u.is_staff = True
u.is_active = True
u.save()

with open('../.claude/skills/run-register/.test-account-password', 'w') as f:
    f.write(password)
"
```

Only ever run this against a local dev database — it creates a
staff-privileged account, so don't run it against anything
production-like.

## Build

No separate build step — Django serves templates/static files directly
in dev.

## Run (agent path)

```bash
cd pyproj
source venv/bin/activate

# 1. Ensure the dev server is up (starts it in the background if not;
#    safe to run even if a server is already running — it detects that
#    and does nothing).
python ../.claude/skills/run-register/driver.py up --project-dir .

# 2. Drive it: log in, go to a page, optionally click something, screenshot.
python ../.claude/skills/run-register/driver.py shot /parts/ /tmp/parts.png

# 3. When done, stop it (only if this driver started it — see Gotchas):
python ../.claude/skills/run-register/driver.py down
```

`shot` subcommand reference:

| flag | what it does |
|---|---|
| `path` (positional) | URL path to visit, e.g. `/parts/`, `/batches/3/` |
| `out` (positional) | output PNG path |
| `--click "<css selector>"` | click an element before the screenshot (e.g. to expand a collapsed section, submit a form) |
| `--wait "<css selector>"` | wait for a selector before acting — use for pages with async content |
| `--no-login` | skip login (e.g. to screenshot the login page itself) |

Example — verified working in this session: clicking a Parts-list
category header to expand it (`.category-header[data-category="1"]` is
the "Audio" category's header row):

```bash
python ../.claude/skills/run-register/driver.py shot /parts/ /tmp/parts-expanded.png \
  --click '.category-header[data-category="1"]' --wait '.category-header'
```

Logs from a driver-started server go to `/tmp/register-dev-server.log`.

## Run (human path)

```bash
cd pyproj
source venv/bin/activate
python manage.py runserver
```

Then open `http://127.0.0.1:8000/` in a real browser. Ctrl-C to stop.

## Test

```bash
cd pyproj
pytest
```

109 tests pass as of this writing (~20s). Uses Django's own test
database — never touches `db.sqlite3`, the dev database.

Sanity-check the app is wired up correctly without running the full
suite:

```bash
cd pyproj
source venv/bin/activate
python manage.py check
```

---

## Gotchas

- **Port 8000 may already be occupied by a human-started `runserver`.**
  `driver.py up` checks for this first (`curl`-equivalent probe) and
  no-ops if something's already answering — don't assume you started
  it, and don't blindly `kill` whatever's on that port. `driver.py down`
  only kills a PID it recorded itself; if `up` no-op'd, `down` prints
  "nothing to stop" rather than touching the pre-existing process.
- **`gh auth login --web` cannot open a real browser window from this
  shell**, even though this runs on the user's own Mac — it can copy
  the one-time code to the clipboard, but the actual browser tab has to
  be opened by the user. Not directly related to running this app, but
  bit us in this same session, so worth remembering if a future task
  needs GitHub auth alongside app testing.
- **Django Debug Toolbar renders a wide panel docked to the right edge
  of every page** (staff users only) and overlaps the last ~200px of
  content at the driver's default 1280px viewport width — visible in
  screenshots as content cut off behind the toolbar's sidebar. Either
  crop/ignore that edge when reading a screenshot, or widen
  `viewport={"width": ...}` in `driver.py`'s `cmd_shot` if a specific
  page needs the full width visible.
- **The login form's username field is `name="username"`, not `email`**,
  even though the app authenticates by email address (`AbstractBaseUser`
  with email as `USERNAME_FIELD`) — Django's default `AuthenticationForm`
  keeps the field named `username` regardless. Fill that field with the
  email address.
- **No `chromium-cli`, `timeout`, or `gh` in a clean shell on this
  machine** — `timeout`/`gtimeout` came from `brew install coreutils`,
  `gh` from `brew install gh`. `chromium-cli` was never found at all;
  hence the Python/Playwright driver instead of the usual `chromium-cli`
  heredoc pattern for web apps.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'playwright'`**: the Setup
  step's `pip install playwright pytest-playwright` + `playwright
  install chromium` wasn't run in this venv yet — do that first.
- **`driver.py shot` hangs or times out on `page.goto`**: the dev server
  isn't actually up. Run `driver.py up` first and check
  `/tmp/register-dev-server.log` for a traceback (commonly a stale
  `.env`/`conf/local_settings.py` — see Setup in `SETUP.md`).

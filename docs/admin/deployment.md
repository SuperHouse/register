# Production Deployment

The Register runs on Linux under uWSGI Emperor. Two deployments are typically maintained in parallel: `register` (production) and `register-test`.

## Overview

uWSGI Emperor watches ini files in `/etc/uwsgi-emperor/vassals/`. Both `register.ini` and `register-test.ini` are symlinks to a shared template `/etc/uwsgi-emperor/django-app-template.ini`, which uses the `%n` magic variable (vassal name without extension) to derive paths — so the same template serves both apps.

uWSGI embeds its own Python interpreter via the `python3` plugin, which uses the operating system's Python (Python 3.14 on Ubuntu 26.04). Each app's virtualenv **must** be created with the same Python minor version, or uWSGI will fail at startup with "no python application found". The real error (`ModuleNotFoundError`) only appears in the per-app log at `/var/log/uwsgi/app/%n.log` immediately after a restart.

### After an operating system upgrade

An Ubuntu release upgrade usually changes the system Python version. The existing virtualenvs then stop working and both apps fail as described above. Rebuild the virtualenv of each app with the new Python:

```bash
cd ~/register/pyproj          # then repeat for ~/register-test/pyproj
mv env env-old
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
deactivate
sudo touch /etc/uwsgi-emperor/vassals/register.ini
```

When the app works again, delete `env-old`. Then check that the cron jobs (for example `refresh_part_sources`) still run, because they call the virtualenv's Python by its path.

The upgrade from Ubuntu 24.04 (Python 3.12) to 26.04 (Python 3.14) on 2026-10-14 needed this procedure.

## KiCAD import

Register uses `kicad-cli` (KiCad 9 or later) to extract files from uploaded KiCAD projects. Without it, Fusion import still works, but a KiCAD upload shows a "kicad-cli not found" warning and nothing is extracted from it.

On Ubuntu 26.04, install KiCad from Flathub for all users, so the `uwsgi` user can run it:

```bash
sudo flatpak install --system flathub org.kicad.KiCad
```

A Flatpak app has its own private `/tmp`, so `kicad-cli` cannot see files that Register unpacks there. Give it a working directory that both can use:

```bash
sudo mkdir -p /srv/register-cad-work
sudo chown uwsgi:uwsgi /srv/register-cad-work
sudo flatpak override --system --filesystem=/srv/register-cad-work org.kicad.KiCad
```

Then add these lines to each app's `.env` file and restart the app:

```
KICAD_CLI = "flatpak run --command=kicad-cli org.kicad.KiCad"
CAD_IMPORT_WORK_DIR = "/srv/register-cad-work"
```

To check the setup, run a render as the `uwsgi` user. The `.kicad_pcb` file must be inside the working directory:

```bash
sudo -u uwsgi flatpak run --command=kicad-cli org.kicad.KiCad pcb render \
    --output /srv/register-cad-work/test.png /srv/register-cad-work/board.kicad_pcb
```

If the render fails because no display is available, install `xvfb` and set `KICAD_CLI = "xvfb-run -a flatpak run --command=kicad-cli org.kicad.KiCad"`.

## Deploying an update

Run these steps for the test deployment first, verify it, then repeat for production.

```bash
cd ~/register-test/pyproj
source env/bin/activate

git pull
pip install -r requirements.txt
# Check for changes to .env.template and conf/local_settings.py.template

python manage.py migrate
pytest
python manage.py collectstatic --noinput
python manage.py check

sudo touch /etc/uwsgi-emperor/vassals/register-test.ini
```

After touching the ini file, Emperor detects the change and reloads the app. Verify the deployment:

```bash
curl -s https://portaltest.superhouse.tv/api/v1/test-endpoint-noauth/ -w ' %{http_code}\n'
```

Repeat for production:

```bash
cd ~/register/pyproj
source env/bin/activate
git pull
pip install -r requirements.txt
python manage.py migrate
pytest
python manage.py collectstatic --noinput
python manage.py check
sudo touch /etc/uwsgi-emperor/vassals/register.ini
```

## Restarting

To restart an individual app:

```bash
sudo touch /etc/uwsgi-emperor/vassals/register.ini      # production
sudo touch /etc/uwsgi-emperor/vassals/register-test.ini # test
```

To restart the Emperor process itself:

```bash
sudo systemctl restart uwsgi-emperor
```

## Media file permissions

uWSGI runs as the `uwsgi` user with `umask = 002` set in the vassal template, so uploaded files are group-writable. If any files were created before this setting was in place (e.g. during initial setup), they may not be group-writable. Fix with:

```bash
sudo chmod -R g+w /path/to/media/root
```

This matters when running `import_data` as a different user than `uwsgi`.

## Logs

Per-app logs are at `/var/log/uwsgi/app/%n.log`. This is the first place to look for startup errors or Python tracebacks.

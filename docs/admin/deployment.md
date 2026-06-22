# Production Deployment

The Register runs on Linux under uWSGI Emperor. Two deployments are typically maintained in parallel: `register` (production) and `register-test`.

## Overview

uWSGI Emperor watches ini files in `/etc/uwsgi-emperor/vassals/`. Both `register.ini` and `register-test.ini` are symlinks to a shared template `/etc/uwsgi-emperor/django-app-template.ini`, which uses the `%n` magic variable (vassal name without extension) to derive paths — so the same template serves both apps.

uWSGI embeds its own Python interpreter via the `python3` plugin (built for Python 3.12). Each app's virtualenv **must** be created with the same Python minor version, or uWSGI will fail at startup with "no python application found". The real error (`ModuleNotFoundError`) only appears in the per-app log at `/var/log/uwsgi/app/%n.log` immediately after a restart.

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

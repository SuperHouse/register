# Production Deployment

The Register runs on Linux under uWSGI Emperor, behind the Caddy web server. Two deployments are typically maintained in parallel: `register` (production) and `register-test`.

| Deployment | Code | Hostnames |
|---|---|---|
| Production | `/var/www/register/pyproj` | `portal.superhouse.tv`, `d.superlab.au` |
| Test | `/var/www/register-test/pyproj` | `portaltest.superhouse.tv`, `dtest.superlab.au` (in the Caddyfile, but no DNS record yet) |

Each app's virtualenv is `env/`, inside its `pyproj` directory.

## Overview

uWSGI Emperor watches ini files in `/etc/uwsgi-emperor/vassals/`. Both `register.ini` and `register-test.ini` are symlinks to a shared template `/etc/uwsgi-emperor/django-app-template.ini`, which uses the `%n` magic variable (vassal name without extension) to derive paths — so the same template serves both apps.

uWSGI embeds its own Python interpreter via the `python3` plugin, which uses the operating system's Python (Python 3.14 on Ubuntu 26.04). Each app's virtualenv **must** be created with the same Python minor version, or uWSGI will fail at startup with "no python application found". The real error (`ModuleNotFoundError`) only appears in the per-app log at `/var/log/uwsgi/app/%n.log` immediately after a restart.

### After an operating system upgrade

An Ubuntu release upgrade usually changes the system Python version. The existing virtualenvs then stop working and both apps fail as described above. Rebuild the virtualenv of each app with the new Python:

```bash
cd /var/www/register/pyproj          # then repeat for /var/www/register-test/pyproj
mv env env-old
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
deactivate
sudo touch /etc/uwsgi-emperor/vassals/register.ini
```

When the app works again, delete `env-old`. Then check that the cron jobs (for example `refresh_part_sources`) still run, because they call the virtualenv's Python by its path.

The upgrade from Ubuntu 24.04 (Python 3.12) to 26.04 (Python 3.14) on 2026-10-14 needed this procedure.

## Web server (Caddy)

Caddy listens on ports 80 and 443 and passes requests to uWSGI. Its configuration is `/etc/caddy/Caddyfile`. The Caddyfile is the only source of configuration: the service does not use `--resume`, so changes made through the Caddy API are lost on restart.

Each deployment has one site block. The site address line lists every hostname for that deployment, and the block ends with a `reverse_proxy` to the app's uWSGI socket:

```
d.superlab.au, portal.superhouse.tv {
    ...
    handle_path /static/* {
        root * /var/www/register/static
        file_server
    }

    reverse_proxy unix//run/uwsgi/register.sock
}
```

- **uWSGI socket.** The vassal template sets `http-socket = /run/uwsgi/%n.sock`, so Caddy sends plain HTTP over a Unix socket. Django receives the original `Host` header. It also detects HTTPS correctly from Caddy's `X-Forwarded-Proto` header, so CSRF checks and absolute URLs (QR codes, password reset links) use `https://`.
- **Static files.** Caddy serves `/static/*` and `/favicon.ico` from the app's `STATIC_ROOT` directly.
- **Media files are not served by Caddy.** Requests for `/media/*` must go through Django, which checks each file against the record that owns it. Staff can download every file. A client user can only download files that belong to their own organisation, and never files marked internal. Do not add a `handle_path /media/*` block with `file_server`. If you do, Caddy skips these checks, and uploaded files (design files, client attachments, firmware) can be downloaded by anyone who knows the URL. This was the case until 2026-10-19.
- **TLS certificates.** Caddy gets and renews a Let's Encrypt certificate for each hostname in the Caddyfile automatically. There is no certbot. A hostname that is not in the Caddyfile is refused during the TLS handshake and never reaches Django.
- **Logs.** Per-site access logs are in `/var/log/caddy/` (`register.log`, `register-test.log`). Certificate events are in the service journal: `sudo journalctl -u caddy`.

After you edit the Caddyfile, check it and then reload Caddy. A reload does not interrupt current connections:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## Adding a vanity hostname

A client can use their own hostname (for example `serials.example.com`) in the QR codes on their boards. A vanity hostname shows the same Register site as `d.superlab.au`.

Do these steps in this order. Caddy requests a certificate as soon as the hostname is in the Caddyfile, and the request fails if DNS does not yet point at the server. Caddy then retries only every few hours.

1. **The client creates the DNS record.** Ask for a CNAME record that points to `d.superlab.au`. A CNAME continues to work if the server's IP address changes. If their DNS provider cannot make a CNAME, an A record for the server's IP address also works. Check the record before you continue:

    ```bash
    dig +short serials.example.com
    ```

    The output must end with the server's IP address.

2. **Add the hostname to Caddy.** Add it to the address line of the production site block, then validate and reload:

    ```
    d.superlab.au, portal.superhouse.tv, serials.example.com {
    ```

    ```bash
    sudo caddy validate --config /etc/caddy/Caddyfile
    sudo systemctl reload caddy
    ```

3. **Add the hostname to Django.** In `/var/www/register/pyproj/conf/local_settings.py`, add it to `ALLOWED_HOSTS`:

    ```python
    ALLOWED_HOSTS = ['d.superlab.au', 'portal.superhouse.tv', 'localhost', 'serials.example.com']
    ```

    Then restart the app:

    ```bash
    sudo touch /etc/uwsgi-emperor/vassals/register.ini
    ```

    If you forget this step, Django returns "400 Bad Request" for every page on that hostname.

4. **Check the result.**

    ```bash
    curl -sI https://serials.example.com/1234 | head -1    # expect HTTP/2 302
    sudo journalctl -u caddy --since '10 minutes ago' | grep -i serials.example.com
    ```

    Then open `https://serials.example.com/` in a browser and log in.

5. **Add the client's branding (optional).** In Register, edit the client's organisation and add the hostname in the **Branding** card. See [Branding](../user-guide/organisations.md#branding). Without branding, the hostname shows the normal SuperHouse site.

Notes:

- Login sessions are separate for each hostname. A user who is logged in on `portal.superhouse.tv` must log in again on a vanity hostname.
- Password reset emails link to the hostname the reset was requested on, and use that hostname's brand name.
- To remove a vanity hostname, do the steps in reverse: remove it from `ALLOWED_HOSTS`, then from the Caddyfile.

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
cd /var/www/register-test/pyproj
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
cd /var/www/register/pyproj
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

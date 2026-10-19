# Vanity Domains Plan (register#149, register#150)

## Question

register#149 — Check status of support for vanity domains: production answers on both
`d.superlab.au` and `portal.superhouse.tv` with the same pages. Clients will want their own hostnames
(e.g. `serials.example.com`) on QR codes. Check how production maps hostnames to the Django app, and
document how to add new hostnames.

register#150 — White label UI with customer logo when loaded with their vanity hostname: when the
system is reached via a client's vanity hostname, show their logo (and link), and perhaps a colour
scheme. No per-client template replacement — that would make documentation and support painful.
Depends on #149.

Plan written 2026-10-19, before any code changes. Order: do #149 first (server check + docs), then
#150.

## What the repo shows (relevant to both)

- **Production hostname config isn't in git.** `ALLOWED_HOSTS` is in the server's own
  `pyproj/conf/local_settings.py`; `local_settings.py.template` only has placeholders. Both names
  work today, so prod either lists both or uses `'*'`.
- **The front-end web server isn't documented.** `docs/admin/deployment.md` covers uWSGI Emperor
  (vassals, `%n` template, logs) but not nginx/Apache, `server_name`, or TLS certificates.
  `pyproj/deploy.md` is stale (still refers to `gunicorn.service`).
- **Sites framework is installed but pinned.** `SITE_ID = 1` → `portal.superhouse.tv`
  (`authuser/migrations/0003_add_superhouse_site.py`). Password-reset emails will link to
  `portal.superhouse.tv` even when the user started on a vanity host.
- **QR scanners hit the login page first.** The short link `/<int:device_number>/`
  (`conf/urls.py`) redirects to `device:device_detail`, which requires login.
- **Top-left logo is hard-coded** in `device/templates/device/partial-sidebar.html` (lines 3–7),
  linking to superhouse.tv. `crm.Org` already has a `logo` field.
- **Colour customisation exists per deployment, not per host:** `BACKGROUND_SETTINGS` in
  `conf/settings.py` + `device.context_processor.background_processor` (dev/test/prod).

## #149 — Server configuration check

Run on the server, read-only, for `register` and then `register-test`:

1. **DNS** — `dig +short d.superlab.au portal.superhouse.tv portaltest.superhouse.tv`. Is each name
   an A record or a CNAME, and do they all resolve to the same machine?
2. **Find the front-end server** — `sudo ss -tlnp | grep -E ':(80|443)\b'`.
3. **Map hostnames to apps** (assuming nginx) —
   `sudo nginx -T 2>/dev/null | grep -nE 'server_name|listen|uwsgi_pass|proxy_pass|ssl_certificate|default_server|include'`.
   Check:
   - which `server` block holds which names
   - whether a `default_server` catch-all exists
   - which uWSGI socket each block sends to
   - that the Host header is passed through (`uwsgi_params` / `$host`)
4. **uWSGI** — `cat /etc/uwsgi-emperor/django-app-template.ini` to confirm the socket path `%n`
   derives for each app.
5. **TLS** — `sudo certbot certificates`: which names are on which certificate, expiry. Find out
   how renewal works (HTTP-01 vs DNS-01); HTTP-01 needs the client's DNS pointing at us before a
   certificate can be issued.
6. **Django settings** —
   `grep -nE 'ALLOWED_HOSTS|CSRF_TRUSTED_ORIGINS|SITE_ID|SECURE_PROXY_SSL_HEADER|USE_X_FORWARDED_HOST|SESSION_COOKIE_DOMAIN|CSRF_COOKIE_DOMAIN' conf/local_settings.py .env`,
   and dump the Sites table:
   `python manage.py shell -c "from django.contrib.sites.models import Site; print(list(Site.objects.values()))"`.
7. **Test the behaviour** —
   - `curl -sI https://d.superlab.au/1234` should return a 302 to `/device/...`.
   - `curl -sI -k -H 'Host: bogus.example.com' https://<server-ip>/` shows what an unknown host
     gets (nginx default, or a Django 400).
   - Log in through a browser on `d.superlab.au` to confirm CSRF/POST works on a non-primary
     hostname.

### Findings

**2026-10-19 — steps 1–2 done:**

- **DNS:** `d.superlab.au`, `portal.superhouse.tv` and `portaltest.superhouse.tv` all resolve to
  `45.79.239.136`. `dig +short` printed no CNAME targets, so all three are plain A records. (Any
  CNAME in the chain would have shown up as an extra line before the IP.)
- **Front-end server is Caddy** (pid 810, listening on `*:80` and `*:443`). It's not nginx, so
  steps 3 and 5 are replaced by Caddy equivalents (below). Caddy gets and renews a TLS certificate
  for every hostname in its config by itself (ACME HTTP-01/TLS-ALPN), so there's no certbot step.
  The client's DNS still has to point at us before Caddy can get their certificate.

**Revised remaining steps (Caddy instead of nginx/certbot):**

3. **Map hostnames to apps:**
   - `caddy version`
   - `systemctl cat caddy` shows which config file the service actually loads (normally
     `/etc/caddy/Caddyfile`).
   - `cat /etc/caddy/Caddyfile`, plus any files it pulls in (`grep -rn import /etc/caddy`).
   - Look for:
     - the site blocks and which hostnames each lists
     - whether both prod names share one block
     - what each block sends to: `reverse_proxy` to an HTTP port/socket, or something else
     - static/media file handling (`file_server`, `handle_path /static/*`)
     - any `on_demand_tls` / `tls` settings
4. **uWSGI:** `grep -nE 'socket|http|protocol' /etc/uwsgi-emperor/django-app-template.ini`.
   Caddy has no native uwsgi-protocol support, so uWSGI is probably on an `http-socket` and Caddy
   uses `reverse_proxy`. Confirm the two match.
5. **TLS:** `sudo find / -path '*caddy/certificates*' -name '*.crt' 2>/dev/null` lists the
   certificates Caddy holds, one per hostname. `journalctl -u caddy --since '30 days ago' | grep -iE 'certificate|obtain|renew|error'`
   shows whether issuing and renewing are working.
6. **Django settings** (as before). One extra thing to check: with `reverse_proxy` in front, Django
   sees plain HTTP unless `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` is set.
   Without it, `request.build_absolute_uri()` builds `http://` URLs, which affects the Batch print
   page's QR code and password-reset links. Caddy passes the original Host header and sets
   `X-Forwarded-Proto` by default.
7. **Behaviour tests:** unchanged.

**2026-10-19 — steps 3–4 done:**

- **Caddy v2.10.2.** The systemd unit loads `/etc/caddy/Caddyfile` (`caddy run --environ`), and
  reload runs `caddy reload --force`. No `--resume`, so the Caddyfile is the only source of config.
  The only `import` lines are the local `(cors-headers)` snippet, which only the InvenTree site uses.
- **Hostname → app mapping is the site address line:**
  - `d.superlab.au, portal.superhouse.tv { … reverse_proxy unix//run/uwsgi/register.sock }`, which
    is production.
  - `dtest.superlab.au, portaltest.superhouse.tv { … reverse_proxy unix//run/uwsgi/register-test.sock }`,
    which is test. Note there's also a `dtest.superlab.au` short-link name for test.
  - `itree.superlab.au` is a separate InvenTree instance on the same server.
- **No catch-all/default site.** Caddy only answers for the names it lists, and only gets
  certificates for those names.
- **uWSGI** template: `http-socket = /run/uwsgi/%n.sock`, `chmod-socket = 660`,
  `chown-socket = uwsgi:www-data`. This matches Caddy's `reverse_proxy unix//…` (plain HTTP over a
  unix socket), so the original Host header reaches Django unchanged, and Caddy adds
  `X-Forwarded-Proto`/`-For`/`-Host`.
- **Static/media are served directly by Caddy** from `/var/www/register/static` and
  `/var/www/register/media` (test: `/var/www/register-test/…`). These paths differ from the
  `local_settings.py.template` example (`/var/www/register-static/`), so check the real
  `STATIC_ROOT`/`MEDIA_ROOT` in step 6.
- **Each site sets HSTS** (`max-age=31536000`, no `includeSubDomains`). A vanity hostname added to
  the block gets the same header, which only affects that one hostname on the client's domain.

**So adding a vanity hostname to production is:** client DNS → `45.79.239.136` (or a CNAME to
`d.superlab.au`); add the name to the prod site's address line; `sudo caddy validate --config
/etc/caddy/Caddyfile`; `sudo systemctl reload caddy` (graceful; Caddy then gets the certificate);
add the name to `ALLOWED_HOSTS` (and `CSRF_TRUSTED_ORIGINS` if used); touch the vassal ini.

**Option for later (#150):** Caddy's `on_demand_tls { ask <url> }` can get certificates for any
hostname that a Django endpoint approves (e.g. one that checks `BrandedHost`). With that, adding a
client hostname wouldn't need a Caddyfile edit or a deploy. Not worth it for a handful of clients;
keep it in mind if many arrive.

**2026-10-19 — steps 5–7 done:**

- **The production app lives at `/var/www/register/pyproj`**, not `~/register/pyproj` as
  `docs/admin/deployment.md` says (`cd ~/register/pyproj` failed for user `jon`). The venv is
  `env/` inside it. Fix the docs as part of #149, and check where `register-test` really lives.
- **Certificates:** the journal shows Caddy holds certificates for `d.superlab.au`,
  `portal.superhouse.tv`, `portaltest.superhouse.tv` and `itree.superlab.au`, and checks renewal
  information (ACME ARI) for each regularly. The storage directory isn't
  `/var/lib/caddy/.local/share/caddy/` (that `ls` failed). This doesn't matter for adding
  hostnames; `caddy environ` or `sudo find / -type d -name certificates -path '*caddy*'` would find
  it if it's ever needed.
- **`dtest.superlab.au` has no DNS record (NXDOMAIN).** It's in the test site block, so Caddy has
  been failing to get a certificate for it for about 5 days (attempt 42, retrying every 6 h, and
  now falling back to Let's Encrypt staging). Either add an A record for it, or remove it from
  the Caddyfile. **This is also the lesson for vanity hosts: the client's DNS must be in place
  before the name is added to Caddy**, or the same retry loop happens.
- **Unrelated:** `itree.superlab.au` returns 502. `/run/uwsgi/inventree.sock` doesn't exist, so
  the InvenTree vassal isn't running.
- **Django (`conf/local_settings.py`):**
  - `ALLOWED_HOSTS = ['d.superlab.au', 'portal.superhouse.tv', 'localhost']`. It's an explicit
    list, so every vanity hostname must be added here, or Django returns 400 for it.
  - `SITE_ID = 1`, `DEBUG = False`.
  - `STATIC_ROOT = '/var/www/register/static/'` and `MEDIA_ROOT = '/var/www/register/media/'`,
    which match the Caddy `root` paths.
  - `CSRF_TRUSTED_ORIGINS`, `SECURE_PROXY_SSL_HEADER` and `USE_X_FORWARDED_HOST` are **not set**,
    in either `local_settings.py` or `.env`.
- **Sites table:** `[{'id': 1, 'domain': 'portal.superhouse.tv', 'name': 'SuperHouse'}]`.
- **Behaviour:**
  - `https://d.superlab.au/1234` → `HTTP/2 302`, so the short link works.
  - An unknown host on 443 → curl exit 35 (TLS handshake refused). Caddy has no certificate for
    unlisted names, so they're refused before reaching Django. That's good: there's no catch-all.

**Closing checks (2026-10-19):** the test app is at `/var/www/register-test/pyproj` (confirmed),
logging in through `https://d.superlab.au/` works in a browser, and `pyproj/deploy.md` was
deleted. Docs written: `docs/admin/deployment.md` ("Web server (Caddy)" and "Adding a vanity
hostname" sections, corrected paths). The `mkdocs build --strict` check passes. #149 is complete
apart from committing and closing.

**Still open (at the time; now resolved, see above and below):**

- **Does Django know requests are HTTPS?** `SECURE_PROXY_SSL_HEADER` isn't set, and plain
  `http-socket` uWSGI doesn't turn `X-Forwarded-Proto` into `wsgi.url_scheme` by itself. If Django
  thinks requests are HTTP, its CSRF Origin check (`http://host` vs the browser's `https://host`)
  should reject logins. Logins work, so something probably sets HTTPS. Possibly a uWSGI `route`
  or `HTTPS` var in the vassal template. Confirm with
  `grep -niE 'https|scheme|forwarded|route' /etc/uwsgi-emperor/django-app-template.ini`.
  Then **log in via `https://d.superlab.au/`** in a browser to confirm a non-primary hostname
  works end to end.
  - **Update:** the vassal template has nothing matching `https|scheme|forwarded|route`, and the
    repo's `settings.py` has no `SECURE_*`/`CSRF_*`/proxy settings at all. Logins work every day
    and browsers send `Origin` on form POSTs, so Django is probably already seeing HTTPS, most
    likely because uWSGI's `http-socket` sets the scheme from Caddy's `X-Forwarded-Proto`
    (inferred, not confirmed). Test: POST to `/accounts/login/` with
    `Origin: https://portal.superhouse.tv` and no cookie, then check
    `/var/log/uwsgi/app/register.log`. "CSRF cookie not set" means the Origin check passed
    (Django sees HTTPS); "Origin checking failed" means it doesn't.
  - **Log test didn't work:** the POST returned 403, but nothing was logged. The repo has no
    `LOGGING` setting, and Django's default console handler only logs when `DEBUG=True`, so prod
    records no Django warnings (CSRF rejections, `DisallowedHost`, 404s). Use the response body
    instead: the default CSRF failure page (no custom `403_csrf.html` or `CSRF_FAILURE_VIEW`
    exists) includes "requires a CSRF cookie when submitting forms" only when the Origin check
    passed and the missing cookie was what failed.
  - **RESOLVED 2026-10-19: Django already sees HTTPS.** The no-cookie POST with
    `Origin: https://portal.superhouse.tv` returned the CSRF page containing "requires a CSRF
    cookie when submitting forms", so the Origin check passed and `request.is_secure()` is True.
    uWSGI's `http-socket` must be setting the scheme from Caddy's `X-Forwarded-Proto`. Nothing in
    Register's settings does it.
  - **Follow-up (small, separate):** add a basic console `LOGGING` config so warnings reach
    `/var/log/uwsgi/app/register.log`. Without it, a vanity hostname missing from `ALLOWED_HOSTS`
    fails silently with a 400.
  - Whatever the result, I'd recommend setting
    `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` explicitly (a settings change,
    to do later with approval), so HTTPS detection doesn't depend on unstated uWSGI behaviour. It's
    safe here: the uWSGI socket is a unix socket only Caddy can reach (`chown uwsgi:www-data`,
    660), and Caddy sets `X-Forwarded-Proto` itself rather than passing a client's value through.
- **Media exposure check: CONFIRMED (2026-10-19).**
  `curl -sI https://portal.superhouse.tv/media/design_assets/100/HLS-v1_1-3d.png` with no cookies
  returned `HTTP/2 200` from Caddy. See the separate finding below.

**⚠ Separate finding (not #149's scope): `/media/*` is served with no authentication.** The prod
site block uses a plain `file_server` for media, so a request for a media URL never reaches Django
and skips the login check. Files under `design_assets/{design_id}/…`, `device_assets/…` and
`test_step_assets/…` (including `internal=True` assets and client design files) can be downloaded
by anyone who knows or guesses the URL, and design IDs are sequential. The InvenTree block on the
same server already shows the fix pattern (`forward_auth` to the app before `file_server`). This
needs its own issue; vanity hosts make it a little worse, since each one is another way in to the
same files.

Confirmed live on 2026-10-19 (anonymous `200` for a design asset). **The repo is public**, so
don't describe this in a public GitHub issue until it's fixed. Use a private security advisory, or
fix it first and file afterwards.

- **Interim fix, no code change:** delete the `handle_path /media/* { … }` block from the prod
  (and test) site in the Caddyfile, then `caddy validate` and `systemctl reload caddy`. Media
  requests then fall through to `reverse_proxy`, reaching Django's existing
  `re_path(r'^media/…', serve, …)` in `conf/urls.py`. `/media/` isn't in
  `LOGIN_REQUIRED_IGNORE_PATHS`, so `LoginRequiredMiddleware` then requires a login. Nothing
  outside the browser fetches Register's `/media/` directly: testomatic-ui uses the
  `download_design_asset` API endpoint, and its own `/media/` is local. Cost: Django serves these
  files more slowly than Caddy would, which is fine at this traffic level.
- **Interim fix APPLIED 2026-10-19** (by Jon). The `/media/` blocks were removed from the
  Caddyfile, the config validated and Caddy reloaded. The same anonymous request now returns
  `HTTP/2 302` → `/accounts/login/?next=/media/design_assets/100/HLS-v1_1-3d.png`, served via
  Django (`via: 1.1 Caddy`, `vary: Cookie`). The live Caddyfile now differs from the copy recorded
  in this file's step-3 findings. Verified while logged in: design images and downloads load, and
  the Batch print page renders correctly with images. The test site was updated the same way.
- **What the interim fix doesn't cover:** any logged-in user (including a client) can still fetch
  another org's files, or `internal=True` files, by URL.
- **Proper fix:** an authorising Django view that checks login, org membership and the `internal`
  flag, then hands the file back to Caddy to send. Either Caddy `forward_auth`, like the InvenTree
  block, or Django returning an `X-Accel-Redirect`-style header that Caddy handles with
  `intercept`/`handle_response`.

### Deliverable for #149

- A new "Adding a vanity hostname" section in `docs/admin/deployment.md`. Likely steps, to confirm
  against the findings:
  1. Client adds a CNAME pointing at a name we control (e.g. `d.superlab.au`), not an A record, so
     a server IP change doesn't break it.
  2. Add the name to the web server's `server_name`.
  3. Issue or expand the TLS certificate.
  4. Add the name to `ALLOWED_HOSTS` (and `CSRF_TRUSTED_ORIGINS` if needed).
  5. Reload the web server and touch the vassal ini.
  6. Run the curl checks.
- Note in the doc that sessions are per-host: a user logged in on `portal.superhouse.tv` must log in
  again on a vanity host.
- Update or delete the stale `pyproj/deploy.md`.

## #150 — White label by hostname

**Scope (as the issue says):** per hostname, a logo, logo link, display name, and one or two
colours. No per-client templates. State this explicitly in the docs, so there's something to point
to when clients push for more.

1. **Model** — new `BrandedHost` in `crm`:
   - `hostname` (unique, stored lowercased)
   - `org` (FK to `Org`; one org may have several hostnames)
   - optional `logo` (falls back to `org.logo`)
   - `logo_link_url`, `display_name`
   - `primary_colour` (validated hex), `is_active`

   Preferred over reusing `django.contrib.sites`: switching that to host-based lookup means
   removing `SITE_ID`, and then any unknown host causes a 500.
2. **Context processor** — `branding`, next to the existing ones. Resolves `request.get_host()`
   (port stripped, lowercased) to a `BrandedHost`; falls back to the current SuperHouse defaults.
   Cache the lookup; clear the cache when a `BrandedHost` is saved.
3. **Templates**
   - Sidebar: logo + link in `partial-sidebar.html`. Keep the Testomatic logo at the bottom as a
     "powered by" mark.
   - `base.html`: `<title>`, and a CSS custom property (CoreUI `--cui-primary` / sidebar vars) from
     the colour.
   - Login page — the most important one, given the QR redirect.
   - Password-reset templates (`authuser/templates/registration/superhouse_*`).
4. **Interactions to decide**
   - The test server's background marker (`BACKGROUND_SETTINGS`) must still win over a client
     colour, so nobody mistakes test for live.
   - Check how it works with demo mode (`b5demo`).
   - Password-reset links should use the request host, not `SITE_ID`.
5. **Management UI** — staff-only, on the org edit page or in the Settings hub. Add a
   `manage.py check` warning when a `BrandedHost` isn't covered by `ALLOWED_HOSTS`, so the #149
   server step isn't forgotten.
6. **Tests** — `RequestFactory` with different `HTTP_HOST` values: known host, unknown host
   (fallback), host with port, mixed case, inactive entry, logo fallback to `org.logo`, test-server
   marker still taking priority.
7. **Docs** — admin guide covering how to add a branded host, start to finish (server steps from
   #149, then the Register entry), plus the scope statement.

### Open decisions before starting #150

- **Host-level or org-level branding?** Recommendation: host-level, with logo fallback to
  `org.logo`.
- **Should branding change data visibility?** Recommendation: no — purely cosmetic; access stays
  governed by org permissions. A user from Org B visiting Org A's domain just sees Org A's logo.

# Media Access Plan

Not committed on purpose (the repo is public). Written 2026-10-19 after the register#149 server
check (see `VANITY_DOMAINS_PLAN.md`).

## Background

- **Until 2026-10-19,** Caddy served `/media/*` directly with `file_server`, so every uploaded
  file could be downloaded without logging in.
- **Interim fix (applied 2026-10-19, prod and test):** the Caddy `/media/` blocks were removed.
  Media now goes through Django's plain `serve` route in `conf/urls.py`, behind
  `LoginRequiredMiddleware`. Verified: an anonymous request gets a 302 to login, and logged-in
  pages and the Batch print page still show images.
- **Remaining gap:** any logged-in user can fetch any file by URL, whatever its org or `internal`
  flag. **As of 2026-10-19 there are no client users** (Jon is the only login on prod and test),
  so the deadline is: **fix before any client is given access.** Do this before #150.
- **Already public:** CLAUDE.md, committed and pushed in `ae5c55f`, mentions the remaining gap.
  Jon accepted this given there are no client users. Reword that line once the fix is in.

## Plan

Replace the `serve` route with a Django view that finds the record that owns the requested file
and applies the same access rules the pages use. URLs stay `/media/...`, so no template or Caddy
changes are needed.

| Path | Owner lookup | Who may download |
|---|---|---|
| `design_assets/` | `DesignAsset` | staff; members of `design.client`, if not `internal` |
| `device_assets/` | `DeviceAsset` | staff; members of `device.design.client`, if not `internal` |
| `device_images/` | `DeviceImage` | staff; members of the device's org |
| `test_images/` (flat) | `TestImage` | staff; members of the test record's device's org |
| `clients/` (org logos) | `Org.logo` | staff; members of that org |
| `part_images/`, `part_assets/` | none | staff only |
| `test_step_assets/`, `test_step_diagnostic_images/` | none | staff only |
| `thumbs/…` (easy_thumbnails, `THUMBNAIL_BASEDIR = 'thumbs'`) | the source file | same as the source file |
| anything else | none | staff only (deny by default) |

- **Find the owner by the stored file name** (e.g. `DesignAsset.objects.filter(file=path)`), not
  by parsing the ID from the path. `test_images/` has no ID folder, and the `internal` flag needs
  the row anyway.
- **Return 404 for both forbidden and missing files**, so the response doesn't confirm that a
  file exists. Anonymous users still get the login redirect from the middleware.
- **Use `Content-Disposition: attachment`** for anything that isn't a raster image or PDF. This
  prevents stored XSS from an uploaded `.html` or `.svg` being shown inline on Register's own
  origin.
- **Add `Cache-Control: private`**, and keep paths inside `MEDIA_ROOT` (reject `../`).
- **Serve with `FileResponse`.** Optionally add `offload-threads = 2` to the uWSGI vassal template.
  Caddy `forward_auth` or internal redirects aren't needed at this traffic level.
- **Tests:** each role (anonymous, staff, member of the owning org, member of another org) against
  each row of the table, plus an `internal` file, a thumbnail and a traversal attempt.
- **#150 link:** a per-host branding logo has to be public (the login page shows it to anonymous
  visitors). Give branding logos their own prefix (e.g. `branding/`) that the view serves to
  everyone. Don't open up `clients/`.

## Server checks

- **DB backups:** `DBBACKUP_STORAGE_OPTIONS = {'location': '/var/www/register/backups/'}`. This is
  outside `MEDIA_ROOT` and not served by Caddy, so it was never exposed. OK.
- **Was the anonymous exposure used? No, as far as the logs show (checked 2026-10-19).** Caddy's
  log format puts a space after each colon (`"uri": "/media/…"`), and rotated logs are gzipped,
  so search with `zcat -f`. Browser requests carry `"Cookie": ["REDACTED"]`, so a media request
  with no `Cookie` header came from someone not logged in. Searching all prod and test logs
  (`/var/log/caddy/register*.log*`, oldest from 2026-07-25) for anonymous `/media/` requests with
  status 200 found exactly one: `2400:8907::f03c:94ff:fe5a:985a`. That is the server's own IPv6
  address, and the request was Jon's `curl -I` test (`HEAD
  /media/design_assets/100/HLS-v1_1-3d.png` at 2026-10-19 05:58:59). A second `HEAD` at 07:51:01
  was the post-fix test and returned 302. Nothing before 2026-07-25 can be checked: those logs
  are gone.

# Supplier API Setup

The Parts library can look up component data from LCSC, DigiKey, Mouser, and Element14 to auto-populate part source records (manufacturer SKU, stock, packaging, description, product image, and price breaks).

---

## LCSC

LCSC lookup uses LCSC's unofficial JSON API directly. **No API key or account is required.** The LCSC fetch button works out of the box.

### Order history sync (optional)

Parts Orders can also import your LCSC order history. This part does need your LCSC account. LCSC has no API key or OAuth flow for it, so Register uses the cookies from a real browser login instead, saved to a file. The file is called a *session file*.

LCSC orders sync only when someone clicks **Refresh Orders** on the Parts Orders page. The scheduled `refresh_parts_orders` job does not sync LCSC.

The session file can only be made on a computer with a screen, because you must log in to LCSC by hand in a browser window. Make it on your desktop, then copy it to the server.

#### 1. Install the browser tools (desktop, once)

On the desktop, in a Register checkout with its venv active:

```bash
pip install "lcsc-toolkit[auth]"
playwright install chromium
```

#### 2. Make a session file (desktop)

```bash
cd pyproj
LCSC_SESSION_FILE=$HOME/lcsc_session.json python manage.py lcsc_capture_session
```

Setting `LCSC_SESSION_FILE` on the command line is only needed if the desktop's own `.env` does not set it.

A Chromium window opens. Log in to LCSC, including any CAPTCHA or two-factor step. The command then saves the file and checks it. Make sure that it prints `Confirmed - session is logged in and working.` If it does not, run it again.

#### 3. Copy the session file to the server

Find the path that the server expects:

```bash
grep LCSC_SESSION_FILE /path/to/register/pyproj/.env
```

Copy the file to that path:

```bash
scp ~/lcsc_session.json yourserver:/path/from/the/env/file.json
```

!!! warning
    The session file gives access to your LCSC account, like a password. On the server, make it readable only by the user that runs Register (for example `chmod 600`, owned by the uWSGI user). Delete the copy on your desktop when you are done.

If the server's `.env` does not set `LCSC_SESSION_FILE` yet, add it and restart Register:

```env
LCSC_SESSION_FILE=/path/to/lcsc_session.json
```

#### 4. Check that it works

Click **Refresh Orders** on the Parts Orders page. You do not need to restart Register when you replace the file, because Register reads it each time it syncs.

#### When the session expires

LCSC sessions expire after some time. The exact lifetime is not known, and there is no way to renew a session automatically. When the session has expired, **Refresh Orders** shows an error like one of these. The wording depends on the installed version of `lcsc-toolkit`:

```
Refresh failed: LCSC order sync failed: LCSC session has expired (/wmsc/order/page returned code=302) - capture a new session and replace the saved session file
```

```
Refresh failed: LCSC order sync failed: /wmsc/order/page returned code=302:
```

To fix it, do steps 2 to 4 again. You do not need to change `.env`.

---

## DigiKey

DigiKey lookup requires a free developer account and a one-time OAuth setup.

### 1. Register a DigiKey API application

1. Sign in or create an account at [developer.digikey.com](https://developer.digikey.com)
2. Create a new application and subscribe it to the **Production Information V4** API product
3. When asked for an **OAuth Callback URL**, enter:
   ```
   https://yourdomain.com/parts/source/digikey-callback/
   ```
   For local development, use `https://localhost:8000/parts/source/digikey-callback/`
4. Copy the **Client ID** and **Client Secret**

### 2. Configure the environment

Create a directory to store the OAuth token:

```bash
mkdir pyproj/.digikey
```

Add to `pyproj/.env`:

```env
DIGIKEY_CLIENT_ID=your-client-id
DIGIKEY_CLIENT_SECRET=your-client-secret
DIGIKEY_STORAGE_PATH=/absolute/path/to/pyproj/.digikey
DIGIKEY_CLIENT_SANDBOX=False
```

### 3. Set up local HTTPS (development only)

DigiKey requires HTTPS for the OAuth callback, even on localhost. Use `mkcert` and `runserver_plus` (already included via `django-extensions`):

```bash
brew install mkcert
mkcert -install
cd pyproj
mkcert localhost
```

This creates `localhost.pem` and `localhost-key.pem` in `pyproj/`.

### 4. Complete the one-time OAuth flow

Start the development server with SSL:

```bash
python manage.py runserver_plus --cert-file localhost.pem --key-file localhost-key.pem
```

Then visit `https://localhost:8000/parts/source/digikey-connect/`. You will be redirected to the DigiKey login page. After granting access, DigiKey redirects back to the app, which exchanges the code for a token and saves it to `DIGIKEY_STORAGE_PATH`.

The token refreshes automatically on subsequent use — this OAuth flow is only needed once (or if the refresh token expires, typically after 90 days of inactivity).

!!! note
    For day-to-day use after the token is saved, run the normal `python manage.py runserver` without SSL. HTTPS is only needed for the initial OAuth flow.

---

## Mouser

Mouser lookup uses a simple API key — no OAuth flow is needed.

### 1. Register for a Mouser Search API key

1. Sign in or create an account at [mouser.com/api-hub](https://www.mouser.com/api-hub/)
2. Under **Search API**, generate an API key

### 2. Configure the environment

Add to `pyproj/.env`:

```env
MOUSER_SEARCH_API_KEY=your-api-key
```

Restart the server. The Mouser fetch button is active immediately.

---

## Element14 / Farnell / Newark

Element14 covers three regional storefronts: Element14 (Asia-Pacific), Farnell (UK/Europe), and Newark (USA). All use the same API with a store ID parameter.

### 1. Register for an Element14 API key

1. Sign in or create an account at [partner.element14.com](https://partner.element14.com)
2. Create a new application and note the **API key**

### 2. Configure the environment

Add to `pyproj/.env`:

```env
ELEMENT14_API_KEY=your-api-key
ELEMENT14_STORE_ID=au.element14.com
```

See [Configuration Reference](configuration.md) for the list of store IDs. Restart the server. The E14 fetch button is active immediately.

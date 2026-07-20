# Supplier API Setup

The Parts library can look up component data from LCSC, DigiKey, Mouser, and Element14 to auto-populate part source records (manufacturer SKU, stock, packaging, description, product image, and price breaks).

---

## LCSC

LCSC lookup uses LCSC's unofficial JSON API directly. **No API key or account is required.** The LCSC fetch button works out of the box.

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

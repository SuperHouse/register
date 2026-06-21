# Configuration Reference

All configuration is done via `pyproj/.env`. Copy `.env.template` as a starting point.

## Core settings

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key — generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DEPLOY_TYPE` | `dev`, `test`, or `prod` — controls the background colour/image in the UI |
| `DEMO_MODE` | `True` hides sensitive data in the UI |
| `API_ALLOW_IPV4_SUBNET` | Additional IPv4 CIDR block allowed to use the API (e.g. `10.0.0.0/24`); localhost is always allowed |
| `ENABLE_GRAVATAR` | `True` to allow Gravatar avatars for user accounts |

## Email (for password resets)

| Variable | Description |
|---|---|
| `EMAIL_HOST` | SMTP server hostname |
| `EMAIL_PORT` | SMTP port |
| `EMAIL_HOST_USER` | SMTP username |
| `EMAIL_HOST_PASSWORD` | SMTP password |
| `EMAIL_USE_TLS` | `True` to use TLS |

## DigiKey API

| Variable | Description |
|---|---|
| `DIGIKEY_CLIENT_ID` | OAuth2 client ID from [developer.digikey.com](https://developer.digikey.com) |
| `DIGIKEY_CLIENT_SECRET` | OAuth2 client secret |
| `DIGIKEY_STORAGE_PATH` | Absolute path to directory where the OAuth token file is stored (e.g. `/home/user/register/pyproj/.digikey`) |
| `DIGIKEY_CLIENT_SANDBOX` | `True` to use the sandbox API (`sandbox-api.digikey.com`). Set to `True` only if your DigiKey app is subscribed to sandbox (not Production Information V4) APIs. |

## Mouser API

| Variable | Description |
|---|---|
| `MOUSER_API_KEY` | Search API key from [mouser.com/api-hub](https://www.mouser.com/api-hub/) |

## Element14 / Farnell / Newark API

| Variable | Description |
|---|---|
| `ELEMENT14_API_KEY` | API key from [partner.element14.com](https://partner.element14.com) |
| `ELEMENT14_STORE_ID` | Regional storefront — see table below |

**Element14 store IDs:**

| Region | Store ID |
|---|---|
| Australia / Asia-Pacific | `au.element14.com` |
| UK / Europe | `uk.farnell.com` |
| USA | `www.newark.com` |

Defaults to `au.element14.com` if not set.

## Local settings

Machine-specific overrides (database connection, `DEBUG`, `MEDIA_ROOT`) go in `pyproj/conf/local_settings.py`. This file is not committed to version control. Copy from `conf/local_settings.py.template` as a starting point.

# Testomatic Circuit Board Register

A Django application for tracking individual printed circuit boards (PCBs) through production, testing, programming, and shipping. Originally designed to store data from the [Testomatic](https://github.com/superhouse/testomatic) PCB test jig system, but works independently.

## Project Layout

```
register/
├── pyproj/             # Django project root (run everything from here)
│   ├── authuser/       # Custom user model app
│   ├── conf/           # Django settings, URLs, middleware
│   ├── device/         # Main app: all PCB/device logic, API, views
│   └── manage.py
├── API.md              # Full REST API documentation
├── BARCODES.md         # Planning notes for barcode scheme (future ERP/stock extension)
├── BARCODE-analysis.MD # Analysis of BARCODES.md ideas with industry best-practice recommendations
├── README.md
└── SETUP.md            # Dev setup instructions
```

## Running the Project

```bash
cd pyproj
source venv/bin/activate
python manage.py runserver
```

- Main UI: http://127.0.0.1:8000/device/
- Dashboard: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/office/
- API docs: http://127.0.0.1:8000/api/v1/docs (requires staff login)

## Running Tests

```bash
cd pyproj
pytest
```

## Data Model

The hierarchy is: **Client → Design → Device → TestRecord / DeviceEvent / DeviceImage**

| Model | Description | Key fields |
|---|---|---|
| `Client` | Organisation/customer | `company_name`, `logo`, `api_key`, M2M `users` |
| `Design` | PCB board type | `sku`, `hw_version` (unique together), `client`, `price` |
| `Device` | Individual board | PK = serial number, `design`, `creation_dt`, `invoice`, `po`, `notes` |
| `TestRecord` | Test result | `device`, `test_dt`, `result` (NEW/PASS/FAIL/HUH?), `notes` |
| `TestImage` | Image on a test record | `test_record`, `image` |
| `DeviceImage` | Image on a device | `device`, `image`, `image_dt`, `notes` |
| `DeviceEvent` | Event on a device | `device`, `event_type` (NOTE/SW_VERSION/SHIPPING), `description`, `internal` |

`DeviceEvent.internal = True` hides the event from non-staff users. `Device.pk` is the hardware serial number.

## Apps

### `device` (main app)

All PCB business logic lives here.

- **[models.py](pyproj/device/models.py)** — All models. `get_dt_as_string()` suppresses time display when stored with the sentinel `witching_hour` (3:14:15 AM local time), used for date-only imports.
- **[views.py](pyproj/device/views.py)** — Django views. Non-staff users only see data belonging to their associated `Client`(s).
- **[api.py](pyproj/device/api.py)** — Django Ninja REST API. Auth via `X-API-Key` header + IP allowlist.
- **[schemas.py](pyproj/device/schemas.py)** — Pydantic schemas for the API.
- **[admin.py](pyproj/device/admin.py)** — Django admin config at `/office/`.
- **[urls.py](pyproj/device/urls.py)** — URL patterns under `/device/`.
- **[management/commands/import-xlsx.py](pyproj/device/management/commands/import-xlsx.py)** — Bulk import from Excel; expects sheets: Devices, Queue, DeviceTypes, Raw Serials, Patched Boards.

### `authuser`

Custom user model using **email as username** instead of a username field. Users have `full_name`, `preferred_name`, and `avatar_type` (initials or Gravatar).

- **[models.py](pyproj/authuser/models.py)** — `User` extends `AbstractBaseUser`. Get it via `from django.contrib.auth import get_user_model`.

### `conf`

Django project configuration.

- **[settings.py](pyproj/conf/settings.py)** — Main settings. Database config is in `local_settings.py`.
- **[local_settings.py](pyproj/conf/local_settings.py)** — Machine-specific overrides (gitignored in prod). Sets `DEBUG`, database, `API_ALLOW_IPV4_SUBNET`, `MEDIA_ROOT`.
- **[middleware.py](pyproj/conf/middleware.py)** — `TimezoneMiddleware` activates the configured timezone per request.
- **[urls.py](pyproj/conf/urls.py)** — Root URL configuration.

## REST API

Base URL: `/api/v1/` — implemented with [Django Ninja](https://django-ninja.dev/).

**Authentication:** `X-API-Key: <key>` header OR Django session cookies. Keys are stored on `Client` objects. API key requests are restricted by IP (localhost always allowed; configure `API_ALLOW_IPV4_SUBNET` for other subnets).

Key endpoints:

| Method | URL | Description | Auth |
|---|---|---|---|
| GET | `/api/v1/clients/` | List all clients | API key |
| GET | `/api/v1/designs/` | List designs (filter with `?client_pk=`) | API key |
| POST | `/api/v1/device/add/` | Create or update a device | API key |
| GET | `/api/v1/device/{pk}/` | Get device details | API key |
| POST | `/api/v1/device/{pk}/program/` | Record firmware version | API key |
| POST | `/api/v1/device/{pk}/add-tr/` | Add test record | API key |
| POST | `/api/v1/device/{tr_pk}/add-image/` | Upload test image (multipart) | API key |
| POST | `/api/v1/device/{pk}/add-device-image/` | Upload device image (multipart, client must own device) | API key |
| GET | `/api/v1/dashboard-stats/` | Dashboard statistics (client/design/device counts + chart data) | Session or API key |

Full documentation in [API.md](API.md).

## Access Control

- **Staff users** see all data across all clients.
- **Non-staff users** only see `Client`, `Design`, and `Device` objects associated with their user account via the `Client.users` M2M relationship.
- Internal `DeviceEvent` records (`internal=True`) are hidden from non-staff users.
- All views require login (enforced by `login_required` middleware).
- **API endpoints:** Traditional API endpoints require `X-API-Key` header + IP allowlist. The dashboard stats endpoint (`/api/v1/dashboard-stats/`) accepts either API key auth or Django session cookies (for browser-based polling).

## Configuration / Environment

Environment variables are loaded from `pyproj/.env` (see `.env.template`):

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEPLOY_TYPE` | `dev`, `test`, or `prod` — controls background colour/image in the UI |
| `DEMO_MODE` | `True` hides sensitive data in the UI |
| `API_ALLOW_IPV4_SUBNET` | Additional IPv4 CIDR block allowed to use the API (e.g. `10.0.0.0/24`) |
| `ENABLE_GRAVATAR` | `True` to allow Gravatar avatars |
| `EMAIL_HOST` / `EMAIL_PORT` / etc. | SMTP settings for password reset emails |

## Dashboard

The dashboard (`/`) displays summary statistics (client/design/device counts) and a line chart of boards assembled per month. The display updates periodically via polling `/api/v1/dashboard-stats/` every 30 seconds. The chart only redraws if the underlying board data has changed.

Access control: Users see only data for their associated clients (if non-staff). Staff see all data.

## Key Dependencies

- **Django >=5.2,<6** — web framework
- **Django Ninja** — REST API (OpenAPI/Swagger auto-docs at `/api/v1/docs`)
- **easy_thumbnails** — image thumbnail generation
- **django-hijack** — staff can impersonate users (`/hijack/`)
- **dj-database-url** — database config from URL string
- **django-dbbackup** — database backup utility
- **openpyxl** — Excel import
- **login_required** — middleware to require login globally

# Testomatic Circuit Board Register

A Django application for tracking individual printed circuit boards (PCBs) through production, testing, programming, and shipping. Originally designed to store data from the [Testomatic](https://github.com/superhouse/testomatic) PCB test jig system, but works independently.

## Project Layout

```
register/
├── pyproj/             # Django project root (run everything from here)
│   ├── authuser/       # Custom user model app
│   ├── conf/           # Django settings, URLs, middleware
│   ├── api/            # Django Ninja API app: NinjaAPI instance, shared router, auth
│   ├── crm/            # Org (client/customer) model, organisation views, API endpoint
│   ├── erp/            # ERP app: Settings hub, Production Stages and Production Stage Templates (for future Batch tracking)
│   ├── pcba/           # Placeholder app; pcba.designs holds a WIP redesign of Design/DesignAsset (not yet in use)
│   ├── device/         # Main app: all PCB/device logic, API endpoints, views
│   └── manage.py
├── API.md              # Full REST API documentation
├── BARCODES.md         # Planning notes for barcode scheme (future ERP/stock extension)
├── BARCODE-analysis.MD # Analysis of BARCODES.md ideas with industry best-practice recommendations
├── README.md
└── SETUP.md            # Dev setup instructions
```

## Running the Project

**Development:**
```bash
cd pyproj
source venv/bin/activate
python manage.py runserver
```

**Production (Linux):** uWSGI Emperor manages apps via ini files in `/etc/uwsgi-emperor/vassals/`. Touch an ini file to restart the app (`sudo touch /etc/uwsgi-emperor/vassals/register.ini`). See [SETUP.md](SETUP.md) for full setup instructions.

- Dashboard: http://127.0.0.1:8000/
- Boards: http://127.0.0.1:8000/device/
- Designs: http://127.0.0.1:8000/design/
- Organisations: http://127.0.0.1:8000/organisation/
- Admin: http://127.0.0.1:8000/office/
- API docs: http://127.0.0.1:8000/api/v1/docs (requires staff login)

## Running Tests

```bash
cd pyproj
pytest
```

## Data Model

The hierarchy is: **Org → Design → Device → TestRecord / DeviceEvent / DeviceImage**

| Model | App | Description | Key fields |
|---|---|---|---|
| `Org` | `crm` | Organisation/customer | `company_name`, `logo`, `api_key`, M2M `users`, `is_client`, `is_manufacturer`, `is_supplier` |
| `Design` | `device` | PCB board type | `sku`, `hw_version` (unique together), `client` (FK → `crm.Org`), `price` |
| `DesignAsset` | `device` | File attached to a design | `design`, `file`, `name`, `description`, `asset_type`, `uploaded_dt`, `internal` |
| `DeviceAsset` | `device` | File attached to a device | `device`, `file`, `name`, `description`, `asset_type`, `uploaded_dt`, `internal` |
| `Device` | `device` | Individual board | PK = serial number, `design`, `creation_dt`, `invoice`, `po`, `notes` |
| `TestRecord` | `device` | Test result | `device`, `test_dt`, `result` (NEW/PASS/FAIL/HUH?), `notes` |
| `TestImage` | `device` | Image on a test record | `test_record`, `image` |
| `DeviceImage` | `device` | Image on a device | `device`, `image`, `image_dt`, `notes` |
| `DeviceEvent` | `device` | Event on a device | `device`, `event_type` (NOTE/SW_VERSION/SHIPPING), `description`, `internal` |

`DeviceEvent.internal = True`, `DesignAsset.internal = True`, and `DeviceAsset.internal = True` hide records from non-staff users. `Device.pk` is the hardware serial number. `Org` has class methods `get_clients()`, `get_manufacturers()`, and `get_suppliers()` that filter by the corresponding boolean flags.

### Design Assets

`DesignAsset` stores files against a `Design` record. Files are stored on disk under `MEDIA_ROOT/design_assets/{design_id}/`; only the path and metadata live in the database. Assets fall into two categories:

### Device Assets

`DeviceAsset` stores files against a `Device` record. Files are stored on disk under `MEDIA_ROOT/device_assets/{device_id}/`. Currently only the `ATTACHMENT` type is used, but the model is structured identically to `DesignAsset` (with an empty `CORE_ASSET_TYPES` frozenset and an `asset_type` field) so core asset types can be added in future without structural changes. The device detail page shows a sortable Attachments table with an inline upload row, filename auto-population, and edit/delete actions for staff — matching the Design detail page behaviour.

**Design Files** (`DesignAsset.CORE_ASSET_TYPES`) — one per design per type; uploading a new one automatically replaces the previous. Display order: `PCB_3D` (PCB 3D View), `PCB_TOP` (PCB Top View), `PCB_BOTTOM` (PCB Bottom View), `FUSION` (Fusion Electronics Project), `SCHEMATIC` (Schematic Design File), `PCB_DESIGN` (PCB Design File), `BOM` (Bill of Materials), `FIRMWARE` (Firmware Binary).

**Attachments** (`ATTACHMENT`) — arbitrary number per design, no specific workflow role (images, PDFs, additional firmware images, notes, etc.).

Staff can upload, edit metadata (name/description), and delete assets from the design detail page. Non-staff users see non-internal assets only.

The design detail page shows the `PCB_TOP` file as an image banner immediately below the page title (respects the `internal` flag). Below that, the **Design Files** table lists all eight types; staff always see all rows (missing types show "Not uploaded"); non-staff only see rows where a file exists. Rows with an uploaded file are fully clickable (downloads the file) with a hover highlight; the filename including extension is shown as plain text (no link styling). The edit/delete action cell has a white background and no row border to visually separate it from the data cells. Each asset type maps to a Bootstrap Icons glyph via `DesignAsset.get_icon_class()`; icon colours are set via `DesignAsset.get_icon_color()` (PCB Design File = `#198754` green, Schematic Design File = `#0d6efd` blue). The `FUSION` type uses a custom SVG at `static/img/filetypes/fusion.svg` rendered as an `<img>` instead of an icon glyph.

Below the Design Files table, the **Attachments** section lists attachment files with a file-type icon, name as a download link, description, and upload date. When a file is selected in the upload form, JavaScript auto-populates the Name field from the filename (extension stripped) and sets the Asset Type and Description based on the file extension: `.f3z` → Fusion / "Fusion project"; `.brd` → PCB Design File / "PCB design file"; `.sch` → Schematic Design File / "Schematic design file"; other extensions leave the type as Attachment.

When a `.f3z` Fusion Electronics Project file is uploaded, `_extract_fusion_assets()` in [views.py](pyproj/device/views.py) automatically extracts and stores the following assets using the `fusionextractor` library: BOM (`.csv`), PCB Design File (`.brd`), Schematic (`.sch`), PCB Top View (3D render via `extract_board_image('pcb_3d_top')`), PCB Bottom View (3D render via `extract_board_image('pcb_3d_bottom')`), and PCB 3D View (thumbnail via `get_previews(include_large_images=False)`, source `'3d_model'`). Each extracted file gets a name suffix to ensure uniqueness (`-top`, `-bottom`, `-3d`). The `.f3d` nested archive inside `.f3z` files uses zstd compression for some entries — `zipfile-zstd` must be installed for the PCB 3D View thumbnail to be extracted.

The Attachments list is client-side sortable: clicking any column header sorts by that column (ascending first); clicking again reverses the order. The active sort column shows a Bootstrap Icons up/down arrow; inactive columns show an invisible placeholder so header widths stay stable. Default sort is Uploaded ascending (oldest first). The Uploaded cell stores `data-sort-value` as a full ISO datetime (`Y-m-d H:i:s`) so items uploaded on the same day are ordered by time; hovering the date shows a tooltip with the full datetime in `j-M-Y H:i:s` format.

## Apps

### `api`

Holds the shared Django Ninja API plumbing, split out of `device.api`.

- **[app.py](pyproj/api/app.py)** — The `NinjaAPI` instance (`api`), with docs gated behind `@staff_member_required`. Mounted at `/api/v1/` in `conf/urls.py`.
- **[routes.py](pyproj/api/routes.py)** — The shared `router` (auth via `AuthByApiKey`), added to `api` via `api.add_router("/", router)`. Endpoint modules (e.g. `device/api.py`) import this `router` and decorate functions on it.
- **[auth.py](pyproj/api/auth.py)** — `AuthByApiKey` (API-key + IP-allowlist auth for the shared router) and `session_or_api_key_auth` (accepts either a Django session or an API key, used for endpoints like `dashboard-stats/`).

**Known issue (WIP):** `device/api.py` calls `@router.get('dashboard-stats/', auth=session_or_api_key_auth, ...)` but does not import `session_or_api_key_auth` from `api.auth` — the equivalent function is defined but commented out locally in `device/api.py`. This will raise a `NameError` on import until fixed.

### `crm`

Organisation (customer/supplier/manufacturer) data.

- **[models.py](pyproj/crm/models.py)** — `Org` model (formerly `Client` in `device`). Fields: `company_name`, `logo`, `api_key`, M2M `users`, `is_client`, `is_manufacturer`, `is_supplier`.
- **[views.py](pyproj/crm/views.py)** — `organisation_list`, `organisation_detail`, `organisation_edit` views (all staff-only); this is the module actually wired up in `conf/urls.py`. Templates live in `device/templates/device/` for now. The Designs table on the organisation detail page mirrors the Designs page layout (PCB top-view thumbnail column, same headers, no Organisation column) and includes the same live filter (`q` param, server-side, via `initServerFilter`), shown only when the org has at least one design.
- **[admin.py](pyproj/crm/admin.py)** — Registers `Org` with the Django admin.
- **[context_processor.py](pyproj/crm/context_processor.py)** — `get_client_logo_processor`: injects `client_logo` and `client_name` into all templates for non-staff users.
- **`views/` directory (WIP, currently unused/broken)** — `crm/views/api.py`, `crm/views/schema.py`, and `crm/views/__init__..py` (note the double dot — not a valid `__init__.py`) are leftovers from an in-progress attempt to split `crm/views.py` into a package. Because `__init__..py` isn't a real package init, `crm.views` still resolves to `crm/views.py` above. These files reference modules that don't exist (`device.views.forms`, `device.views.router`, `views.schema`) and should either be finished or removed.

### `erp`

ERP/stock-and-ordering features. Provides the **Settings** hub with **Production Stages** and **Production Stage Templates**, and **Batches** — production runs of a `Design` with an ordered checklist of production stages.

- **[models.py](pyproj/erp/models.py)**:
  - `ProductionStage` — a stage a batch can pass through during production (e.g. "PCBs stocked", "Top SMT complete"). Fields: `name` (unique), `color` (hex string, used to highlight the stage in the UI), `order` (controls display order and the order of choices in the `ProductionStageTemplateStep` dropdown — both use `Meta.ordering = ['order']`).
  - `ProductionStageTemplate` — a named, reusable collection of production stages (e.g. "Double-sided hi-rel load"). Fields: `name` (unique), `description`.
  - `ProductionStageTemplateStep` — a `ProductionStage` at a position within a `ProductionStageTemplate`. Fields: `template` (FK → `ProductionStageTemplate`, `related_name='steps'`, `CASCADE`), `production_stage` (FK → `ProductionStage`, `PROTECT` — a stage in use by any template cannot be deleted), `order`.
  - `Batch` — a production run of a `Design`. Fields: `design` (FK → `device.Design`, `PROTECT`, `related_name='batches'`), `reference`, `quantity`, `notes`, `created_dt` (`Meta.ordering = ['-created_dt']`).
  - `BatchProductionStage` — a production stage on a `Batch`, **snapshotted** from a `ProductionStage` at the time it was added (`name`/`color` copied at apply time, so later edits to the template or `ProductionStage` don't retroactively affect in-progress batches). Fields: `batch` (FK → `Batch`, `CASCADE`, `related_name='production_stages'`), `name`, `color`, `order` (`Meta.ordering = ['order']`), `status` (`NOT_STARTED`/`IN_PROGRESS`/`ON_HOLD`/`DONE`, via `STATUS_CHOICES`), `due_date`, `completion_date`. `get_bootstrap_table_class()` maps status to a table row class for the batch detail page.
- **[views.py](pyproj/erp/views.py)** / **[urls.py](pyproj/erp/urls.py)** (all staff-only, `app_name = 'erp'`, mounted at the site root — each `path()` includes its own `settings/` or `batches/` prefix):
  - `settings_index` (`/settings/`) — hub page with cards linking to each settings section.
  - `production_stage_list` / `production_stage_edit` / `production_stage_delete` / `production_stage_move` (`/settings/production-stages/...`) — CRUD for `ProductionStage`, with an inline add row and up/down reordering (swaps `order` with the adjacent row). Delete is blocked with a warning message if the stage is referenced by a template (`ProtectedError`).
  - `production_stage_template_list` / `production_stage_template_edit` / `production_stage_template_delete` (`/settings/production-stage-templates/...`) — CRUD for `ProductionStageTemplate`, with an inline add row on the list page.
  - `production_stage_template_step_add` / `_delete` / `_move` — manage the ordered list of `ProductionStageTemplateStep`s on the template edit page (add via dropdown, remove, and up/down reordering by swapping `order`).
  - `batch_list` / `batch_add` / `batch_edit` / `batch_delete` (`/batches/...`) — CRUD for `Batch`. `batch_edit` is also the detail page, managing the batch's `BatchProductionStage` list.
  - `batch_apply_template` — applies a `ProductionStageTemplate` to a batch via `_apply_template_to_batch()`, which snapshots each `ProductionStageTemplateStep`'s stage into a new `BatchProductionStage`, appended after any existing stages. Stages whose `name` already exists on the batch are skipped, so re-applying (or applying a second template) only adds genuinely new stages.
  - `batch_production_stage_add` / `_update` / `_delete` / `_move` — manage individual `BatchProductionStage` rows on a batch: manual add (snapshots name/color from a chosen `ProductionStage`), inline status/due-date/completion-date update, delete, and up/down reordering (swapping `order`).
- **[forms.py](pyproj/erp/forms.py)** — `ProductionStageForm` (name + colour picker), `ProductionStageTemplateForm` (name + description), `ProductionStageTemplateStepForm` (production stage select, ordered per `ProductionStage.Meta.ordering`), `BatchForm` (design/reference/quantity/notes), `BatchApplyTemplateForm` (template select), `BatchProductionStageAddForm` (production stage select, for manual add), `BatchProductionStageUpdateForm` (status/due_date/completion_date).
- **[admin.py](pyproj/erp/admin.py)** — registers `ProductionStage` and `ProductionStageTemplate` (with an inline `ProductionStageTemplateStep` editor), and `Batch` (with an inline `BatchProductionStage` editor).
- Sidebar: staff users see a "Batches" link (`erp:batch_list`) alongside Boards, and a "Settings" link (`erp:settings_index`) below Organisations.

### `pcba`

Placeholder app, plus a `pcba.designs` sub-app (also in `INSTALLED_APPS`) containing a parallel, **not-yet-wired-up** redesign of the PCB design data model:

- **[designs/models.py](pyproj/pcba/designs/models.py)** — New `Design` / `DesignVersion` / `DesignAsset` models. `Design` now holds only `name`, `sku`, `description`, and `owner` (FK → `crm.Org`); per-revision fields (`hw_version`, `price`, `DesignAsset`s) move to `DesignVersion`. `DesignAsset` here is a near-copy of `device.DesignAsset` but FKs to `DesignVersion` instead of `Design`.
- **[designs/admin.py](pyproj/pcba/designs/admin.py)** — Admin registrations for the above (`DesignVersionAdmin` with inline `DesignAsset`, `DesignAdmin` with inline `DesignVersion`).
- No views, URLs, or templates reference `pcba.designs` yet — the live Design/DesignAsset models are still `device.models.Design` / `device.models.DesignAsset`.

### `device` (main app)

All PCB business logic lives here.

- **[models.py](pyproj/device/models.py)** — All device models, plus the still-current `Design`/`DesignAsset` (see `pcba` above for their planned eventual replacements). `get_dt_as_string()` suppresses time display when stored with the sentinel `witching_hour` (3:14:15 AM local time), used for date-only imports.
- **[views.py](pyproj/device/views.py)** — Django views. Non-staff users only see data belonging to their associated `Org`(s). List pages (Boards, Designs) use server-side filtering (not client-side) so filtering works correctly with pagination. Designs list is paginated. Device asset views (`device_asset_add`, `device_asset_edit`, `device_asset_delete`) mirror the design asset views.
- **[api.py](pyproj/device/api.py)** — Device/design/test-record API endpoints, decorated onto the shared `router` imported from `api.routes`. See the `api` app above for the router/auth setup, and the known `session_or_api_key_auth` issue.
- **[schemas.py](pyproj/device/schemas.py)** — Pydantic schemas for the device API endpoints.
- **[admin.py](pyproj/device/admin.py)** — Django admin config at `/office/`.
- **[urls.py](pyproj/device/urls.py)** — URL patterns under `/device/`. Note: design and organisation URLs are in `conf/urls.py`, not here.
- **[context_processor.py](pyproj/device/context_processor.py)** — Context processors: `background_processor` (deploy-type background), `demo_processor` (demo mode vars), `version_processor` (injects `app_version` from `settings.VERSION`).
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

**Authentication:** `X-API-Key: <key>` header OR Django session cookies. Keys are stored on `Org` objects. API key requests are restricted by IP (localhost always allowed; configure `API_ALLOW_IPV4_SUBNET` for other subnets).

Key endpoints:

| Method | URL | Description | Auth |
|---|---|---|---|
| GET | `/api/v1/clients/` | List all clients (currently **not registered** — only exists in the broken `crm/views/api.py`, see `crm` app notes) | API key |
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

- **Staff users** see all data across all organisations.
- **Non-staff users** only see `Org`, `Design`, and `Device` objects associated with their user account via the `Org.users` M2M relationship.
- Internal `DeviceEvent` records (`internal=True`) are hidden from non-staff users.
- All views require login (enforced by `login_required` middleware).
- **API endpoints:** Traditional API endpoints require `X-API-Key` header + IP allowlist. The dashboard stats endpoint (`/api/v1/dashboard-stats/`) accepts either API key auth or Django session cookies (for browser-based polling).
- Internal `DesignAsset` and `DeviceAsset` records (`internal=True`) are hidden from non-staff users.

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

The dashboard (`/`) displays summary statistics (client/design/device counts) and a line chart of boards assembled per month. The display updates periodically via polling `/api/v1/dashboard-stats/` every 30 seconds. The chart only redraws if the underlying board data has changed; on each timed update the chart canvas size is also checked and redrawn if it has changed (handles window resizing). Stat cards briefly pulse green when their data changes. A "clean view" button temporarily hides navigation for use as a status screen display.

Access control: Users see only data for their associated clients (if non-staff). Staff see all data.

## Version Number

`settings.VERSION` holds the current app version string. It is set in [`__VERSION.py`](__VERSION.py) at the repo root (format `YYYY.MM.DD.N`). At import time it reads `.git/HEAD` and automatically appends the current branch name as a suffix (e.g. `2026.06.09.1-refactor-modules`); the suffix is omitted on `main` and when no `.git` directory exists (e.g. a non-git production deployment). The version is injected into all templates as `app_version` via `device.context_processor.version_processor` and displayed in the bottom of the left sidebar as a link to the project source repository on GitHub, satisfying the AGPL network-use disclosure requirement.

## License

This project is licensed under the **GNU Affero General Public License v3 or later** (AGPL-3.0-or-later). The full license text is in `LICENSE`. Key source files carry an SPDX identifier and copyright notice. Because this is a network service, any modified deployment must make its corresponding source available to users — the sidebar version link serves this purpose.

## Key Dependencies

- **Django >=5.2,<6** — web framework
- **Django Ninja** — REST API (OpenAPI/Swagger auto-docs at `/api/v1/docs`)
- **easy_thumbnails** — image thumbnail generation
- **django-hijack** — staff can impersonate users (`/hijack/`)
- **dj-database-url** — database config from URL string
- **django-dbbackup** — database backup utility
- **openpyxl** — Excel import
- **login_required** — middleware to require login globally
- **fusionextractor >=1.2.0** — extracts BOM, board, schematic, and PCB render images from Autodesk Fusion Electronics `.f3z` files
- **zipfile-zstd** — zstd codec support for `zipfile`; required to read zstd-compressed entries inside `.f3z` nested archives (e.g. the PCB 3D View thumbnail)

## Frontend Libraries (CDN)

Loaded in `device/templates/device/base.html` for all pages:

| Library | Version | Purpose |
|---|---|---|
| CoreUI | 4.3.2 | CSS framework, layout, components |
| CoreUI Icons | 3.0.1 | Icon font (`cil-*` classes) used throughout the UI |
| Bootstrap Icons | 1.13.1 | File-type icons (`bi-*` classes) used in the asset list |
| SimpleBar | latest | Custom scrollbar for the sidebar |

Custom icons (SVG files) live in `static/img/filetypes/` and are referenced via `{% static %}` in templates.

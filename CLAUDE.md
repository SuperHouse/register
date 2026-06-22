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
├── docs/               # MkDocs source — end-user and admin documentation
│   ├── index.md
│   ├── user-guide/     # Dashboard, Boards, Designs, Organisations, Parts, Batches
│   ├── admin/          # Setup, deployment, configuration, supplier APIs, data export/import
│   └── api/            # REST API reference
├── .github/
│   └── workflows/
│       └── docs.yml    # GitHub Actions: builds and deploys docs to GitHub Pages on push to main
├── mkdocs.yml          # MkDocs configuration (Material theme, nav structure)
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

**Production (Linux):** uWSGI Emperor manages apps via ini files in `/etc/uwsgi-emperor/vassals/`. Touch an ini file to restart the app (`sudo touch /etc/uwsgi-emperor/vassals/register.ini`). `register.ini` and `register-test.ini` are both symlinks to the shared `/etc/uwsgi-emperor/django-app-template.ini`, which uses uWSGI's `%n` (vassal name) magic variable for `chdir`/`virtualenv`/socket/log paths — so changes to the template affect both apps. uWSGI embeds its own Python interpreter via the `python3` plugin (currently built for 3.12) rather than exec'ing the venv's own binary; each app's `env` venv **must** be created with the matching Python minor version, or uWSGI fails at startup with a generic "no python application found" (the real `ModuleNotFoundError` only shows in the per-app log under `/var/log/uwsgi/app/%n.log` right after a restart). See [SETUP.md](SETUP.md) for full setup instructions.

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

## Documentation

End-user and admin documentation lives in `docs/` and is built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/). The published site is at `https://superhouse.github.io/register/`.

**Build locally:**
```bash
pip install mkdocs-material
mkdocs serve          # live-reload preview at http://127.0.0.1:8000
mkdocs build --strict # one-off build to site/
```

**Deployment:** `.github/workflows/docs.yml` builds and deploys to GitHub Pages automatically on every push to `main` (and can be triggered manually from the Actions tab). The Pages source in the repo settings must be set to **GitHub Actions**.

The `site/` build output is gitignored. `docs/` source is the only thing committed.

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

The design detail page shows the `PCB_TOP` and `PCB_BOTTOM` files as an image banner immediately below the page title (respects the `internal` flag): if both exist they appear side by side (each capped at `max-width: 400px`); if only one exists it is shown alone. Below that, the **Design Files** table lists all eight types; staff always see all rows (missing types show "Not uploaded"); non-staff only see rows where a file exists. Rows with an uploaded file are fully clickable (downloads the file) with a hover highlight; the filename including extension is shown as plain text (no link styling). The edit/delete action cell has a white background and no row border to visually separate it from the data cells. Each asset type maps to a Bootstrap Icons glyph via `DesignAsset.get_icon_class()`; icon colours are set via `DesignAsset.get_icon_color()` (PCB Design File = `#198754` green, Schematic Design File = `#0d6efd` blue). The `FUSION` type uses a custom SVG at `static/img/filetypes/fusion.svg` rendered as an `<img>` instead of an icon glyph.

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

ERP/stock-and-ordering features. Provides the **Settings** hub with **Production Stages**, **Production Stage Templates**, **Locations**, **Part Categories**, and **Part Import Filters**; a **Parts** library; and **Batches** — production runs of a `Design` with an ordered checklist of production stages.

- **[models.py](pyproj/erp/models.py)**:
  - `ProductionStage` — a stage a batch can pass through during production (e.g. "PCBs stocked", "Top SMT complete"). Fields: `name` (unique), `color` (hex string, used to highlight the stage in the UI), `order` (controls display order and the order of choices in the `ProductionStageTemplateStep` dropdown — both use `Meta.ordering = ['order']`).
  - `ProductionStageTemplate` — a named, reusable collection of production stages (e.g. "Double-sided hi-rel load"). Fields: `name` (unique), `description`, `order` (controls display order — `Meta.ordering = ['order', 'name']`). The list page supports drag-and-drop reordering (same pattern as `ProductionStage`).
  - `ProductionStageTemplateStep` — a `ProductionStage` at a position within a `ProductionStageTemplate`. Fields: `template` (FK → `ProductionStageTemplate`, `related_name='steps'`, `CASCADE`), `production_stage` (FK → `ProductionStage`, `PROTECT` — a stage in use by any template cannot be deleted), `order`.
  - `Batch` — a production run of a `Design`. Fields: `design` (FK → `device.Design`, `PROTECT`, `related_name='batches'`), `po` (verbose name "Purchase order"), `quantity`, `notes`, `created_dt` (`Meta.ordering = ['-created_dt']`).
  - `BatchProductionStage` — a production stage on a `Batch`, **snapshotted** from a `ProductionStage` at the time it was added (`name`/`color` copied at apply time, so later edits to the template or `ProductionStage` don't retroactively affect in-progress batches). Fields: `batch` (FK → `Batch`, `CASCADE`, `related_name='production_stages'`), `name`, `color`, `order` (`Meta.ordering = ['order']`), `status` (`NOT_STARTED`/`IN_PROGRESS`/`ON_HOLD`/`DONE`, via `STATUS_CHOICES`), `due_date`, `completion_date` (`DateTimeField`, recorded to the second). `get_bootstrap_table_class()` maps status to a table row class for the batch detail page.
  - `Location` — a physical location in a hierarchy (e.g. building › room › shelf). Fields: `parent` (self-referential FK, nullable, `CASCADE` — deleting a parent deletes all descendants), `name`, `description`, `order` (`Meta.ordering = ['order', 'name']`). The `_build_location_tree(all_locations, parent_id, depth)` helper in `views.py` performs a depth-first traversal of a pre-fetched list and returns `[(location, depth), ...]` for template rendering with indentation.
  - `PartCategory` — a category in a hierarchy for classifying parts (e.g. Passives › Resistors › SMD). Fields: `parent` (self-referential FK, nullable, `CASCADE`), `name`, `description`, `order` (`Meta.ordering = ['order', 'name']`, `verbose_name_plural = 'part categories'`). The `_build_part_category_tree(all_categories, parent_id, depth)` helper in `views.py` performs a depth-first traversal, returning `[(category, depth), ...]` for indented rendering — same pattern as `_build_location_tree`.
  - `Part` — a component part. Fields: `name`, `description`, `category` (FK → `PartCategory`, nullable, `SET_NULL` — deleting a category leaves parts uncategorised), `device`, `package`, `value`, `fusion_library`, `image` (`ImageField`, stored under `part_images/`), `created_dt` (`Meta.ordering = ['name']`). `__str__` appends the value in parentheses if set.
  - `PartSource` — a supplier or purchase source for a `Part`. Fields: `part` (FK, `CASCADE`, `related_name='sources'`), `supplier_name`, `supplier_sku`, `url` (`URLField`), `manufacturer_sku`, `packaging` (e.g. "Tape & Reel (TR)", "Cut Tape (CT)"), `stock` (`PositiveIntegerField`, nullable — `None` means unknown). `Meta.ordering = ['supplier_name']`.
  - `PartAsset` — a file attachment on a `Part` (e.g. datasheet). Fields: `part` (FK, `CASCADE`, `related_name='assets'`), `file` (stored under `part_assets/{part_id}/`), `name`, `description`, `uploaded_dt`. Has a `filename` property and `get_icon_class()` returning extension-based Bootstrap Icons class (PDF, ZIP, spreadsheet, paperclip fallback).
  - `BomExclusionRule` — a rule applied during BOM CSV import that causes matching rows to be skipped entirely (never created as a `Part`). Fields: `library`, `device`, `package`, `value` — each blank to match any value for that field; a row is excluded only if it matches every non-blank field. `Meta.ordering = ['library', 'device', 'package', 'value']`.
  - `BomEquivalenceRule` (UI label: "Transformation Rule") — a rule applied during BOM CSV import that remaps a (library, device, package, value) tuple to a different one before the duplicate check. Fields: `from_library`/`to_library`, `from_device`/`to_device`, `from_package`/`to_package`, `from_value`/`to_value` — "from" fields blank to match any value, "to" fields blank to leave that part of the tuple unchanged. Field order on the model, form, and templates groups each From/To pair adjacently (Library pair, then Device pair, then Package pair, then Value pair) rather than all-from-then-all-to, and the merged settings page draws a header grouping + divider (table) or a bordered `<fieldset>` (edit page) around each pair. `Meta.ordering = ['from_library', 'from_device', 'from_package', 'from_value']`.
  - `BomLibrarySetting` — per-Fusion-library behaviour applied during BOM CSV import, after exclusion and equivalence rules. Fields: `library` (unique), `ignore_device`, `ignore_package`, `ignore_value` (booleans) — when set, the corresponding field is blanked out before the duplicate check and is not stored on the created `Part` for rows from that library.
- **[views.py](pyproj/erp/views.py)** / **[urls.py](pyproj/erp/urls.py)** (all staff-only, `app_name = 'erp'`, mounted at the site root — each `path()` includes its own `settings/` or `batches/` prefix):
  - `settings_index` (`/settings/`) — hub page with cards linking to each settings section.
  - `production_stage_list` / `production_stage_edit` / `production_stage_delete` (`/settings/production-stages/...`) — CRUD for `ProductionStage`, with an inline add row. Delete is blocked with a warning message if the stage is referenced by a template (`ProtectedError`).
  - `production_stage_reorder` (`/settings/production-stages/reorder/`) — AJAX endpoint: accepts JSON `{"order": [id, ...]}` and rewrites `ProductionStage.order` for each id to match.
  - `production_stage_template_list` / `production_stage_template_edit` / `production_stage_template_delete` (`/settings/production-stage-templates/...`) — CRUD for `ProductionStageTemplate`, with an inline add row on the list page.
  - `production_stage_template_reorder` (`/settings/production-stage-templates/reorder/`) — AJAX endpoint: accepts JSON `{"order": [id, ...]}` and rewrites `ProductionStageTemplate.order` for each id to match.
  - `production_stage_template_step_add` / `_delete` — manage the ordered list of `ProductionStageTemplateStep`s on the template edit page (add via dropdown, remove).
  - `production_stage_template_step_reorder` (`/settings/production-stage-templates/<id>/reorder-steps/`) — AJAX endpoint, same `{"order": [...]}` pattern as `production_stage_reorder`, scoped to one template's steps.
  - `batch_list` / `batch_add` / `batch_edit` / `batch_delete` (`/batches/...`) — CRUD for `Batch`. `batch_edit` is also the detail page, managing the batch's `BatchProductionStage` list. `batch_add` pre-selects `design` from a `?design=<id>` query param.
  - `batch_apply_template` — applies a `ProductionStageTemplate` to a batch via `_apply_template_to_batch()`, which snapshots each `ProductionStageTemplateStep`'s stage into a new `BatchProductionStage`, appended after any existing stages. Stages whose `name` already exists on the batch are skipped, so re-applying (or applying a second template) only adds genuinely new stages.
  - `batch_production_stage_add` / `_update` / `_delete` — manage individual `BatchProductionStage` rows on a batch: manual add (snapshots name/color from a chosen `ProductionStage`), inline due-date/completion-date update, delete.
  - `batch_production_stage_reorder` (`/batches/<id>/reorder-production-stages/`) — AJAX endpoint, same `{"order": [...]}` pattern, scoped to one batch's production stages.
  - `batch_production_stage_set_status` (`/batches/production-stage/<id>/set-status/<status>/`) — AJAX endpoint (POST, no body): sets the stage's `status`; if `status == DONE`, also sets `completion_date = timezone.now()`. Returns JSON `{status, table_class, completion_date}` (the latter formatted `Y-m-dTH:i:s` in the active timezone for direct use in a `datetime-local` input).
  - `location_list` (`/settings/locations/`) — renders the full location tree using `_build_location_tree()`. Each row shows the name (indented by depth with a `└` glyph for non-root items), description, and Add Child / Edit / Delete buttons. "Add Child" links to `location_add?parent=<id>`.
  - `location_add` / `location_edit` / `location_delete` (`/settings/locations/...`) — CRUD for `Location`. Add pre-selects the parent from a `?parent=<id>` query param. Edit excludes the location and all its descendants from the parent dropdown to prevent cycles (`_get_descendant_pks()` helper in `forms.py`). Delete shows a cascade warning when the location has children.
  - `part_category_list` (`/settings/part-categories/`) — renders the full category tree using `_build_part_category_tree()`. Same layout as the location list: indented name, description, Add Child / Edit / Delete buttons.
  - `part_category_add` / `part_category_edit` / `part_category_delete` (`/settings/part-categories/...`) — CRUD for `PartCategory`. Same pattern as the location views: `?parent=<id>` pre-selection on add, cycle prevention on edit, cascade warning on delete.
  - `part_list` (`/parts/`) — lists all parts grouped by category, with `table-secondary` sub-heading rows. Uncategorised parts appear first. Uses `Prefetch` to load each category's parts in one query. Supports server-side filtering via the `q` query param (same `initServerFilter` pattern as the Designs list), filtering across `name`, `value`, `package`, and `device` fields. Includes a "Populate from BOM" button that opens a CoreUI modal for CSV upload.
  - `part_add` / `part_edit` / `part_delete` (`/parts/...`) — CRUD for `Part`. `part_edit` serves as both the detail and edit page: shows the image (if set) above the form, then a **Sources** card (see below), then an Attachments card. Saving a part redirects to `part_list`. Deleting a part also deletes the image file from disk.
  - `part_asset_add` / `part_asset_delete` (`/parts/<id>/add-asset/`, `/parts/asset/<id>/delete/`) — manage `PartAsset` attachments on a part; delete also removes the file from disk. The attachment upload row auto-populates the Name field from the selected filename via JavaScript.
  - `part_source_add` / `part_source_delete` (`/parts/<id>/add-source/`, `/parts/source/<id>/delete/`) — add or delete a `PartSource` record via POST form; delete redirects back to `part_edit`.
  - `part_source_refresh` (`/parts/source/<id>/refresh/`) — POST-only AJAX endpoint: re-fetches data from the supplier API identified by `source.supplier_name` (supports `'lcsc'`, `'digikey'` or any name containing `"digikey"`, and `'mouser'`), updates `manufacturer_sku`, `packaging`, `url`, `stock` on the source, fills `part.description` if empty, and saves a product image to the part if none exists. Returns `{"ok": true}` on success; JS reloads the page.
  - `part_source_fetch_lcsc` (`/parts/source/fetch-lcsc/`) — POST-only AJAX endpoint: accepts JSON `{"sku": "...", "part_id": N}`. Uses `_lcsc_search()` (direct `requests` calls to LCSC's unofficial JSON API at `wmsc.lcsc.com`, replicating the relevant part of the `lcsc` PyPI client's behaviour without that package's Python >=3.13 requirement) to look up the SKU. Creates a new `PartSource` (supplier `'LCSC'`) if none exists for that SKU; populates `manufacturer_sku` from `product_model`, `packaging` from `product_arrange`, `stock` from `stock_number`, `url` constructed from `product_code`. Fills `part.description` from `product_intro_en` if empty. Saves first product image to the part if the part has no image. Returns JSON including `source_saved` (bool); JS reloads on `source_saved`, otherwise pre-fills the add-source form.
  - `part_source_fetch_digikey` (`/parts/source/fetch-digikey/`) — POST-only AJAX endpoint: same contract as `fetch_lcsc` but uses the DigiKey API v4 (`GET /products/v4/search/{sku}/productdetails`). Calls `_get_digikey_access_token()` to obtain a valid Bearer token (refreshing from `token_storage.json` if expired). Extracts `packaging` from `ProductVariations` by matching `DigiKeyProductNumber` to the requested SKU. Fills `part.description` from `Description.DetailedDescription`. Saves `PhotoUrl` as the part image if none exists.
  - `part_source_fetch_mouser` (`/parts/source/fetch-mouser/`) — POST-only AJAX endpoint: same contract. Uses `POST /api/v1/search/partnumber?apiKey={key}` with `MOUSER_API_KEY`. Extracts `packaging` from `ProductAttributes` by finding an attribute whose name contains `"packag"`. Fills `part.description` from the `Description` field. Saves `ImagePath` as the part image if none exists.
  - `part_source_fetch_element14` (`/parts/source/fetch-element14/`) — POST-only AJAX endpoint: same contract. Uses `GET https://api.element14.com/catalog/products` with `ELEMENT14_API_KEY` and `ELEMENT14_STORE_ID` (regional storefront, e.g. `au.element14.com`). Searches by `term=sku:{sku}` with `resultsSettings.responseGroup=large`. Extracts `manufacturerPartNumberList[0]` for manufacturer SKU; packaging from `attributes[]` (attribute label containing "packag") or falls back to `packSize` formatted as "Pack of N"; stock from `stock`; image from `imageList.image[0].url` (protocol-relative URLs are prefixed with `https:`). The refresh view matches on supplier names containing `"element14"`, `"farnell"`, or `"newark"`. **TODO:** unlike LCSC/DigiKey/Mouser, this endpoint does not populate `PartSourceVariant.moq` — no `ELEMENT14_API_KEY` was configured at the time MOQ support was added, so the response's MOQ field name couldn't be verified live. Once a working key is available, check a live response for the MOQ field (candidates seen in other Element14/Farnell API versions: `translatedMinimumOrderQuanity`, `minimumOrderQuantity`) and wire it up the same way as the other suppliers.
  - `_digikey_base_url()` — helper that returns `https://sandbox-api.digikey.com` or `https://api.digikey.com` based on the `DIGIKEY_CLIENT_SANDBOX` env var. Used by all DigiKey OAuth and API calls so that sandbox/production is switched in one place.
  - `_get_digikey_access_token()` — helper that reads `{DIGIKEY_STORAGE_PATH}/token_storage.json`, refreshes the access token via `POST /v1/oauth2/token` if the `expires` timestamp has passed, saves the refreshed token back to the file, and returns `(client_id, access_token)`. Raises `RuntimeError` on missing config or failed refresh.
  - `digikey_connect` (`/parts/source/digikey-connect/`) — redirects to the DigiKey OAuth authorisation URL (using `_digikey_base_url()`). Staff-only.
  - `digikey_callback` (`/parts/source/digikey-callback/`) — receives the OAuth authorisation code from DigiKey, exchanges it for a token via `POST /v1/oauth2/token`, and saves the token JSON (with an added `expires` epoch timestamp) to `token_storage.json`. The token is saved in the format `_get_digikey_access_token()` expects.
  - `part_import_bom` (`/parts/import-bom/`) — POST-only; reads a CSV file (`utf-8-sig` encoding) with columns `reference`, `device`, `package`, `value`, `library`. For each row, in order: skips the row if it matches a `BomExclusionRule` (`_bom_row_is_excluded()`); applies the first matching `BomEquivalenceRule` to remap `library`/`device`/`package`/`value` (`_bom_apply_equivalence()`); applies the row's `BomLibrarySetting` (if any, looked up by the post-transformation library) to blank out `device`/`package`/`value` per its `ignore_*` flags; then checks for an existing `Part` matching `device`, `package`, and `value` (case-insensitive `__iexact`; `fusion_library` is intentionally excluded so the same physical part from different Fusion libraries is not duplicated) and skips if found, otherwise creates a new part with `name = " ".join([value, package, device.capitalize()])` and `fusion_library` set to the (possibly remapped) library. Reports added/skipped/excluded counts via messages. `_bom_field_matches(rule_value, row_value)` is the shared "blank rule field matches anything" comparison helper used by both rule types.
  - `part_import_filter_list` (`/settings/part-import-filters/`) — the merged "Part Import Filters" settings page: renders `BomExclusionRule`, `BomEquivalenceRule`, and `BomLibrarySetting` as three sections on one page, in the order they're applied in `part_import_bom`. `_part_import_filter_context()` builds the shared context (querysets + a form per section) reused by this view and by each rule type's `_add` view below.
  - `bom_exclusion_rule_add` / `bom_exclusion_rule_edit` / `bom_exclusion_rule_delete` (`/settings/bom-exclusion-rules/...`) — CRUD for `BomExclusionRule`. `_add` is POST-only (GET redirects to `part_import_filter_list`); on validation failure it re-renders the merged page via `_part_import_filter_context()` with the invalid bound form swapped in for that section, so errors show inline without a dedicated list page.
  - `bom_equivalence_rule_add` / `bom_equivalence_rule_edit` / `bom_equivalence_rule_delete` (`/settings/bom-equivalence-rules/...`) — CRUD for `BomEquivalenceRule`, same `_add`-redirect/re-render pattern as exclusion rules.
  - `bom_library_setting_add` / `bom_library_setting_edit` / `bom_library_setting_delete` (`/settings/bom-library-settings/...`) — CRUD for `BomLibrarySetting`, same pattern.
- **[forms.py](pyproj/erp/forms.py)** — `ProductionStageForm` (name + colour picker), `ProductionStageTemplateForm` (name + description), `ProductionStageTemplateStepForm` (production stage select, ordered per `ProductionStage.Meta.ordering`), `BatchForm` (design/po/quantity/notes — uses `DesignChoiceField`, a `ModelChoiceField` subclass that labels each option as `"{org} {sku}: {name} {version}"` and orders by org → SKU → name → version), `BatchApplyTemplateForm` (template select, ordered per `ProductionStageTemplate.Meta.ordering`), `BatchProductionStageAddForm` (production stage select, for manual add), `BatchProductionStageUpdateForm` (due_date/completion_date only — status is no longer part of this form, see below), `LocationForm` (parent dropdown with `empty_label='(top level)'`, name, description — uses `_get_descendant_pks()` to filter invalid parent choices when editing), `PartCategoryForm` (same structure as `LocationForm` — parent dropdown, name, description — also uses `_get_descendant_pks()` for cycle prevention), `PartForm` (`name`, `description`, `category` dropdown with `empty_label='(uncategorised)'`, `device`, `package`, `value`, `fusion_library`, `image` `ClearableFileInput` — field order on the edit page: Name → Device/Package/Value → Category → Description → Fusion Library → Image), `PartAssetForm` (file, name, description), `PartSourceForm` (`supplier_name`, `supplier_sku`, `url`, `manufacturer_sku`, `packaging`, `stock` — all rendered as small Bootstrap form controls for inline use in the part edit page), `BomExclusionRuleForm` (`library`, `device`, `package`, `value` — `clean()` requires at least one field set, since an all-blank rule would exclude every imported row), `BomEquivalenceRuleForm` (From/To pairs in field order `from_library`/`to_library`, `from_device`/`to_device`, `from_package`/`to_package`, `from_value`/`to_value` — `clean()` requires at least one "from" field and at least one "to" field set), `BomLibrarySettingForm` (`library`, `ignore_device`, `ignore_package`, `ignore_value` checkboxes). The `_get_descendant_pks(all_items, root_pk)` helper is generic: it accepts any list of objects with a `parent_id` attribute and returns the set of all descendant PKs via iterative BFS.
- **[admin.py](pyproj/erp/admin.py)** — registers `Location`, `PartCategory` (both: list display name/parent/description, `list_select_related`, `search_fields`), `Part` (list display name/category/value/package/device/fusion_library, `list_select_related`, search; with inline `PartAsset` and `PartSource` editors), `ProductionStage`, `ProductionStageTemplate` (with an inline `ProductionStageTemplateStep` editor), `Batch` (with an inline `BatchProductionStage` editor), `BomLibrarySetting`, `BomExclusionRule`, and `BomEquivalenceRule` (each: list display of its fields, `search_fields`, no inlines).
- **Drag-and-drop reordering**: the Production Stages list, the Production Stage Templates list, the steps list on the Template edit page, and the Production Stages list on the Edit Batch page all support drag-and-drop reordering via [SortableJS](https://github.com/SortableJS/Sortable) (loaded from CDN in each template's `extra_js` block) plus the shared `initSortableReorder(tbodyId)` helper in [static/js/script.js](pyproj/static/js/script.js). Each draggable `<tbody>` has an `id` and `data-reorder-url="..."`; each `<tr>` has `data-stage-id="{{ pk }}"`; a `bi-grip-vertical` icon in the first column is the drag handle. On drop, the new row order is POSTed as JSON to the corresponding `*_reorder` view. The old up/down move buttons and `*_move` views have been removed.
- **Batch production stage status**: on the Edit Batch page, each `BatchProductionStage`'s status is shown as 4 icon buttons (`bi-circle` Not Started, `bi-play-circle` In Progress, `bi-pause-circle` On Hold, `bi-check-circle` Done) instead of a dropdown; the current status is shown as a solid (filled) button, others as outline. Clicking a button calls `initStatusButtons(tbodyId)` (also in `static/js/script.js`), which POSTs to `batch_production_stage_set_status` and updates the button highlighting, row colour, and Completion Date field in place — no page reload.
- `static/js/script.js` also provides a shared `getCookie(name)` helper (used to read the `csrftoken` cookie for the `X-CSRFToken` header on the AJAX `fetch()` calls above).
- Sidebar: staff users see a "Batches" link (`erp:batch_list`) above "Boards", a "Parts" link (`erp:part_list`) between "Organisations" and "Settings", and a "Settings" link (`erp:settings_index`). Active-state detection uses `url_name` prefix slicing: Parts is active when `url_name` starts with `"part_"` but not `"part_c"` (which is `part_category_*`, a Settings URL) and is not `"part_import_filter_list"` (the merged Part Import Filters page, also a Settings URL); Settings uses an `{% elif %}` chain to re-include `part_category_*` and `part_import_filter_list` after the `"part_"` exclusion. The Design detail page has an "Add New Batch" button (staff only) linking to `erp:batch_add` with `?design=<id>`, which pre-selects that design in the `BatchForm`.

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
- **[management/commands/import-xlsx.py](pyproj/device/management/commands/import-xlsx.py)** — Bulk import from Excel; requires sheets `Devices` and `DeviceTypes` (any additional sheets such as Queue or Patched Boards are ignored).
- **[management/commands/export_data.py](pyproj/device/management/commands/export_data.py)** — Exports all `crm`, `device`, and `erp` records plus `MEDIA_ROOT` files (excluding thumbnail cache) to a self-contained ZIP archive. User accounts are not included. Run with `python manage.py export_data [output.zip]`.
- **[management/commands/import_data.py](pyproj/device/management/commands/import_data.py)** — Imports a ZIP produced by `export_data`, performing a clean-slate replace (deletes all existing app data first). The database flush and load run inside a single transaction so a failure rolls back cleanly. Run with `python manage.py import_data archive.zip [--yes]`. Run as a different user than the one that owns existing `MEDIA_ROOT` files (e.g. running manually as a login user while uWSGI writes as `uwsgi`), this can fail with `PermissionError` deleting old media files — the production uWSGI vassal template sets `umask = 002` so new uploads stay group-writable, but pre-existing files/dirs created before that setting was added may still need `chmod -R g+w` on `MEDIA_ROOT` once.

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
| `DIGIKEY_CLIENT_ID` | DigiKey OAuth2 client ID (from developer.digikey.com) |
| `DIGIKEY_CLIENT_SECRET` | DigiKey OAuth2 client secret |
| `DIGIKEY_STORAGE_PATH` | Absolute path to directory where the DigiKey OAuth token is stored (e.g. `pyproj/.digikey`) |
| `DIGIKEY_CLIENT_SANDBOX` | `True` to use the DigiKey sandbox API (`sandbox-api.digikey.com`); `False` for production. Set to `True` only if your DigiKey app is subscribed to sandbox (not Production Information V4) APIs. |
| `MOUSER_API_KEY` | Mouser Search API key (from mouser.com/api-hub) |
| `ELEMENT14_API_KEY` | Element14 / Farnell / Newark API key (from partner.element14.com) |
| `ELEMENT14_STORE_ID` | Regional storefront for Element14 API (e.g. `au.element14.com`, `uk.farnell.com`, `www.newark.com`; defaults to `au.element14.com`) |

## Dashboard

The dashboard (`/`) displays summary statistics (client/design/device counts) and a line chart of boards assembled per month. The display updates periodically via polling `/api/v1/dashboard-stats/` every 30 seconds. The chart only redraws if the underlying board data has changed; on each timed update the chart canvas size is also checked and redrawn if it has changed (handles window resizing). Stat cards briefly pulse green when their data changes. A "clean view" button temporarily hides navigation for use as a status screen display.

Access control: Users see only data for their associated clients (if non-staff). Staff see all data.

## Printable Pages

Pages that need a clean, A4-friendly printout (e.g. handing a Batch's details to production staff) follow a shared pattern rather than adding `@media print` rules to the interactive page:

- **[device/base-print.html](pyproj/device/templates/device/base-print.html)** — minimal HTML shell (no sidebar, nav, or app chrome) that print page templates extend. Loads [static/css/print.css](pyproj/static/css/print.css) and renders a `.no-print` toolbar with a *Print* button (`window.print()`) above the `{% block content %}`.
- **[static/css/print.css](pyproj/static/css/print.css)** — shared stylesheet: sets `@page { size: A4; margin: 15mm; }`, a `.print-document` wrapper, `.print-header` (title + date row with a bottom rule), `table.print-table`/`table.print-fields` (bordered field/data tables), and `.no-print` (hidden via `@media print`) for the toolbar.
- Each printable page gets its own minimal template (e.g. [erp/batch_print.html](pyproj/erp/templates/erp/batch_print.html)) extending `device/base-print.html`, plus a dedicated view/URL (e.g. `batch_print` at `/batches/<id>/print/`) rather than reusing the detail page's view/template — this keeps the print layout free to diverge from the interactive UI (buttons, status icons, sidebar) without fighting it via CSS overrides.
- The source page links to the print page with a print icon button (`<i class="cil-print"></i>`) opening in a new tab (`target="_blank"`) — see the Print button on [erp/batch_edit.html](pyproj/erp/templates/erp/batch_edit.html).

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
- **requests** — used directly (not via any supplier Python library) for DigiKey OAuth token exchange, token refresh, and v4 API calls, for Mouser REST API calls, and for LCSC's unofficial JSON API (`_lcsc_search()` in `erp/views.py` — the `lcsc` PyPI package was dropped because it requires Python >=3.13, which the production/test uWSGI deployment doesn't support)

## Frontend Libraries (CDN)

Loaded in `device/templates/device/base.html` for all pages:

| Library | Version | Purpose |
|---|---|---|
| CoreUI | 4.3.2 | CSS framework, layout, components |
| CoreUI Icons | 3.0.1 | Icon font (`cil-*` classes) used throughout the UI |
| Bootstrap Icons | 1.13.1 | File-type icons (`bi-*` classes) used in the asset list |
| SimpleBar | latest | Custom scrollbar for the sidebar |

Custom icons (SVG files) live in `static/img/filetypes/` and are referenced via `{% static %}` in templates.

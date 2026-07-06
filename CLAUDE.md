# Testomatic Circuit Board Register

A Django application for tracking individual printed circuit boards (PCBs) through production, testing, programming, and shipping. Originally designed to store data from the [Testomatic](https://github.com/superhouse/testomatic) PCB test jig system, but works independently.

## Project Layout

```
register/
├── pyproj/             # Django project root (run everything from here)
│   ├── authuser/       # Custom user model app
│   ├── conf/           # Django settings, URLs, middleware
│   ├── api/            # Django Ninja API app: NinjaAPI instance, shared router, auth
│   ├── crm/            # Org (client/customer) model, organisation + user management views, API endpoints
│   ├── erp/            # ERP app: Settings hub, Production Stages and Production Stage Templates (for future Batch tracking)
│   ├── testing/        # Testers app: Testomatic chassis (Tester) and test module tracking (TestModuleType/TestModule)
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
| `Org` | `crm` | Organisation/customer | `company_name`, `logo`, M2M `users`, `is_client`, `is_manufacturer`, `is_supplier` |
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

The design detail page shows the `PCB_TOP` and `PCB_BOTTOM` files as an image banner immediately below the page title (respects the `internal` flag): if both exist they appear side by side (each capped at `max-width: 400px`); if only one exists it is shown alone. When both exist, staff also see a "Swap" button (`design_swap_pcb_images` view, POST-only, applied immediately with no confirmation prompt) for when FusionExtractor extracts the top/bottom renders the wrong way round — it swaps the two files **on disk** (via a temp-name rename dance) rather than touching the `DesignAsset` rows, so each asset keeps its own pk/name/description/filename and nothing else needs to change its references. Because the filename doesn't change, the banner's two `<img>` tags append `?v={{ asset.file_version }}` (`DesignAsset.file_version`, the file's mtime as an int) to cache-bust browsers that wouldn't otherwise revalidate the image by URL alone; the view also bumps each file's mtime via `os.utime()` after the swap so this token actually changes. The same `?v={{ pcb_top.file_version }}` pattern is applied to the `PCB_TOP` thumbnail `<img>` on the Designs list page ([design_list.html](pyproj/device/templates/device/design_list.html)), which otherwise shows a full-size image shrunk via CSS rather than an `easy_thumbnails`-generated thumbnail. Below that, the **Design Files** table lists all eight types; staff always see all rows (missing types show "Not uploaded"); non-staff only see rows where a file exists. Rows with an uploaded file are fully clickable (downloads the file) with a hover highlight; the filename including extension is shown as plain text (no link styling). The edit/delete action cell has a white background and no row border to visually separate it from the data cells. Each asset type maps to a Bootstrap Icons glyph via `DesignAsset.get_icon_class()`; icon colours are set via `DesignAsset.get_icon_color()` (PCB Design File = `#198754` green, Schematic Design File = `#0d6efd` blue). The `FUSION` type uses a custom SVG at `static/img/filetypes/fusion.svg` rendered as an `<img>` instead of an icon glyph.

Below the Design Files table, the **Attachments** section lists attachment files with a file-type icon, name as a download link, description, and upload date. When a file is selected in the upload form, JavaScript auto-populates the Name field from the filename (extension stripped) and sets the Asset Type and Description based on the file extension: `.f3z` → Fusion / "Fusion project"; `.brd` → PCB Design File / "PCB design file"; `.sch` → Schematic Design File / "Schematic design file"; other extensions leave the type as Attachment.

When a `.f3z` Fusion Electronics Project file is uploaded, `_extract_fusion_assets()` in [views.py](pyproj/device/views.py) automatically extracts and stores the following assets using the `fusionextractor` library: BOM (`.csv`), PCB Design File (`.brd`), Schematic (`.sch`), PCB Top View (3D render via `extract_board_image('pcb_3d_top')`), PCB Bottom View (3D render via `extract_board_image('pcb_3d_bottom')`), and PCB 3D View (thumbnail via `get_previews(include_large_images=False)`, source `'3d_model'`). Each extracted file gets a name suffix to ensure uniqueness (`-top`, `-bottom`, `-3d`). The `.f3d` nested archive inside `.f3z` files uses zstd compression for some entries — `zipfile-zstd` must be installed for the PCB 3D View thumbnail to be extracted.

The Attachments list is client-side sortable: clicking any column header sorts by that column (ascending first); clicking again reverses the order. The active sort column shows a Bootstrap Icons up/down arrow; inactive columns show an invisible placeholder so header widths stay stable. Default sort is Uploaded ascending (oldest first). The Uploaded cell stores `data-sort-value` as a full ISO datetime (`Y-m-d H:i:s`) so items uploaded on the same day are ordered by time; hovering the date shows a tooltip with the full datetime in `j-M-Y H:i:s` format.

## Apps

### `api`

Holds the shared Django Ninja API plumbing, split out of `device.api`.

- **[app.py](pyproj/api/app.py)** — The `NinjaAPI` instance (`api`), with docs gated behind `@staff_member_required`. Mounted at `/api/v1/` in `conf/urls.py`.
- **[routes.py](pyproj/api/routes.py)** — The shared `router` (auth via `AuthByApiKey`), added to `api` via `api.add_router("/", router)`. Endpoint modules (e.g. `device/api.py`) import this `router` and decorate functions on it.
- **[auth.py](pyproj/api/auth.py)** — `AuthByApiKey` (IP-allowlist check, then looks up `authuser.User.objects.filter(api_key=key, is_active=True)` — the auth class used by default on the shared `router`) and `session_or_api_key_auth` (accepts either a Django session or an `X-API-Key` header, resolving to the same `{'auth_type': ..., 'user': <User>}` shape either way; used by endpoints like `dashboard-stats/` that need to support both browser polling and API-key access). API keys are per-`User` (see API Keys below), not per-`Org`.

**Endpoint module registration:** endpoint modules (`device/api.py`, `crm/views/api.py`) only register their routes on the shared `router` when imported, since the `@router.get(...)`/`@router.post(...)` decorators run at import time. `conf/urls.py` imports both modules explicitly (`from device import api as device_api`, `from crm.views import api as crm_api`) purely for that import side effect — removing those imports would silently empty the API of everything except whatever a test happens to import directly.

### `crm`

Organisation (customer/supplier/manufacturer) data, plus staff user management. `crm.views` is a package (not a single module):

- **[models.py](pyproj/crm/models.py)** — `Org` model (formerly `Client` in `device`). Fields: `company_name`, `logo`, M2M `users`, `is_client`, `is_manufacturer`, `is_supplier`.
- **[schema.py](pyproj/crm/schema.py)** — `ClientSchema` (Django Ninja `ModelSchema` over `Org`, fields `id`/`company_name`), used by `views/api.py`'s `get_clients` endpoint.
- **[forms.py](pyproj/crm/forms.py)** — `UserForm`: a `ModelForm` over `authuser.User` (`email`, `full_name`, `preferred_name`, `is_staff`, `is_active`) plus a manually-declared `orgs` `ModelMultipleChoiceField` (since `Org.users` is declared on `Org`, not `User` — `orgs` is initialised from/saved to the reverse `user.org_set` M2M accessor in `__init__`/`save()`). Deliberately excludes `is_superuser` (admin-only) and password (new users get a "set your password" email instead — see API Keys / onboarding below).
- **[views/organisations.py](pyproj/crm/views/organisations.py)** — `organisation_list`, `organisation_detail`, `organisation_edit` (all staff-only); this is what `conf/urls.py` wires up for the `organisation_*` URL names. Templates live in `device/templates/device/` for now. The Designs table on the organisation detail page mirrors the Designs page layout (PCB top-view thumbnail column, same headers, no Organisation column) and includes the same live filter (`q` param, server-side, via `initServerFilter`), shown only when the org has at least one design. Member users in the detail page's Users row link to their `user_edit` page (see below).
- **[views/users.py](pyproj/crm/views/users.py)** — staff-only user management: `user_list` (searchable over `full_name`/`email`, paginated, same shape as `organisation_list`), `user_add` / `user_edit` (share one template, `device/templates/device/user_edit.html` — org membership, staff/active flags, and the user's API key with a Regenerate button), `user_regenerate_key` (POST-only, calls `User.regenerate_api_key()`). `user_add` creates the account with `set_unusable_password()` then sends a "set your password" email via Django's `PasswordResetForm`, reusing the same templates/from-address as `authuser.views.SuperHousePasswordResetView` (see API Keys below) so onboarding emails look identical to a self-service password reset.
- **[views/api.py](pyproj/crm/views/api.py)** — `get_clients` (`GET /api/v1/clients/`), decorated onto the shared `router` imported from `api.routes`; returns every `Org` for staff callers, otherwise only the orgs the calling user belongs to.
- **[views/\_\_init\_\_.py](pyproj/crm/views/__init__.py)** — re-exports the view functions from `organisations.py` and `users.py` by name, so `conf/urls.py`'s `from crm import views as crm_views` keeps working unchanged regardless of which submodule a view actually lives in.
- **[admin.py](pyproj/crm/admin.py)** — Registers `Org` with the Django admin.
- Sidebar: staff users see a "Users" link (`user_list`) directly below "Organisations".

### `erp`

ERP/stock-and-ordering features. Provides the **Settings** hub with **Production Stages**, **Production Stage Templates**, **Locations**, **Part Categories**, and **Part Import Filters**; a **Parts** library; and **Batches** — production runs of a `Design` with an ordered checklist of production stages.

- **[models.py](pyproj/erp/models.py)**:
  - `ProductionStage` — a stage a batch can pass through during production (e.g. "PCBs stocked", "Top SMT complete"). Fields: `name` (unique), `color` (hex string, used to highlight the stage in the UI), `order` (controls display order and the order of choices in the `ProductionStageTemplateStep` dropdown — both use `Meta.ordering = ['order']`).
  - `ProductionStageTemplate` — a named, reusable collection of production stages (e.g. "Double-sided hi-rel load"). Fields: `name` (unique), `description`, `order` (controls display order — `Meta.ordering = ['order', 'name']`). The list page supports drag-and-drop reordering (same pattern as `ProductionStage`).
  - `ProductionStageTemplateStep` — a `ProductionStage` at a position within a `ProductionStageTemplate`. Fields: `template` (FK → `ProductionStageTemplate`, `related_name='steps'`, `CASCADE`), `production_stage` (FK → `ProductionStage`, `PROTECT` — a stage in use by any template cannot be deleted), `order`.
  - `Batch` — a production run of a `Design`. Fields: `design` (FK → `device.Design`, `PROTECT`, `related_name='batches'`), `po` (verbose name "Purchase order"), `quantity`, `notes`, `created_dt` (`Meta.ordering = ['-created_dt']`).
  - `BatchProductionStage` — a production stage on a `Batch`, **snapshotted** from a `ProductionStage` at the time it was added (`name`/`color` copied at apply time, so later edits to the template or `ProductionStage` don't retroactively affect in-progress batches). Fields: `batch` (FK → `Batch`, `CASCADE`, `related_name='production_stages'`), `name`, `color`, `order` (`Meta.ordering = ['order']`), `status` (`NOT_STARTED`/`IN_PROGRESS`/`ON_HOLD`/`DONE`, via `STATUS_CHOICES`), `due_date`, `completion_date` (`DateTimeField`, recorded to the second). `get_bootstrap_table_class()` maps status to a table row class for the batch detail page; `get_status_color_class()` maps status to a Bootstrap background colour class (`bg-secondary`/`bg-info`/`bg-warning`/`bg-success`) for the small coloured-square status indicators on the Batches list page.
  - `Location` — a physical location in a hierarchy (e.g. building › room › shelf). Fields: `parent` (self-referential FK, nullable, `CASCADE` — deleting a parent deletes all descendants), `name`, `description`, `order` (`Meta.ordering = ['order', 'name']`). The `_build_location_tree(all_locations, parent_id, depth)` helper in `views.py` performs a depth-first traversal of a pre-fetched list and returns `[(location, depth), ...]` for template rendering with indentation.
  - `PartCategory` — a category in a hierarchy for classifying parts (e.g. Passives › Resistors › SMD). Fields: `parent` (self-referential FK, nullable, `CASCADE`), `name`, `description`, `order` (`Meta.ordering = ['order', 'name']`, `verbose_name_plural = 'part categories'`). The `_build_part_category_tree(all_categories, parent_id, depth)` helper in `views.py` performs a depth-first traversal, returning `[(category, depth), ...]` for indented rendering — same pattern as `_build_location_tree`.
  - `Part` — a component part. Fields: `name`, `description`, `category` (FK → `PartCategory`, nullable, `SET_NULL` — deleting a category leaves parts uncategorised), `device`, `package`, `value`, `fusion_library`, `stock` (`IntegerField`, nullable — a manually-tracked on-hand count, independent of the supplier-listing stock below), `image` (`ImageField`, stored under `part_images/`), `created_dt` (`Meta.ordering = ['name']`). `__str__` appends the value in parentheses if set. `total_stock` property sums `stock` across all `PartSource` listings (`None` if none have a known level) — shown as "Available" in the Parts list, distinct from the manually-tracked `stock` field above shown as "Stock". `has_stale_source_data` property is `True` if any of the part's `PartSource` listings has `has_stale_variant_data` (see below) — drives a warning icon next to "Available" in the Parts list and Part edit page, and next to "Available" in the Batch detail page's Parts Required section (see `Batch` below), when supplier pricing/stock hasn't been refreshed within `STALE_REFRESH_THRESHOLD` (48 hours) or has never been refreshed at all.
  - `DesignBomEntry` — a single placed component on a `Design`'s BOM (e.g. RefDes `R3` = a 10k resistor `Part`); one row per physical placement rather than a collapsed line item with a quantity, so placement data can support pick-and-place/AOI use cases later. Fields: `design` (FK → `device.Design`, `CASCADE`, `related_name='bom_entries'`), `part` (FK → `Part`, `PROTECT`, `related_name='design_bom_entries'`), `reference` (the reference designator, e.g. `"R3"`), `pos_x`/`pos_y` (`DecimalField`, 9/4, nullable), `rotation` (`DecimalField`, 6/2, nullable), `side` (`TOP`/`BOTTOM` via `SIDE_CHOICES`, blank). `Meta.ordering = ['reference']`; `unique_together` on `(design, reference)`. `pos_x`/`pos_y`/`rotation`/`side` are never user-editable (`DesignBomEntryForm` only exposes `reference`/`part`) — they're only ever populated from the design's PCB Design File asset by `_apply_brd_placements()` (see `design_bom_populate` below). `reference_sort_key` property splits `reference` into a `(letter prefix, numeric value, remainder)` tuple for natural sorting (so `"R2"` sorts before `"R11"`) — `Meta.ordering`/the DB-level `ORDER BY` is plain string ordering and is left as-is for other consumers (CSV export, admin), so this key is applied explicitly wherever the BOM list needs natural order (currently only `device.views.design_detail`, which `sorted()`s the queryset in Python rather than trying to express natural sort portably at the DB level). Shown on the Design detail page's Bill of Materials table (Reference/Part/Device/Package/Value/Position/Rotation/Side columns; Position shown as "x, y" in mm, blank/`—` fields shown as `—`) as a read-only list — see `design_bom_entry_edit` below for how rows are edited.
  - `PartSource` — a supplier's **listing** for a `Part`: one manufacturer SKU as stocked by one supplier. Fields: `part` (FK, `CASCADE`, `related_name='sources'`), `supplier_name`, `manufacturer_sku`, `stock` (`PositiveIntegerField`, nullable — `None` means unknown). `Meta.ordering = ['supplier_name']`. Stock is held here rather than on `PartSourceVariant` because suppliers such as DigiKey sell the same physical inventory pool under several packaging-specific SKUs (cut tape, tape & reel, Digi-Reel, etc.) that all report the same stock level but different pricing/MOQ — those become separate `PartSourceVariant` rows under one `PartSource`. `has_stale_variant_data` property is `True` if any of this listing's `PartSourceVariant`s has `last_refreshed = None` (never fetched) or older than `STALE_REFRESH_THRESHOLD` (module-level constant, 48 hours) — used both by `Part.has_stale_source_data` above and directly next to each listing's stock figure in the Part edit page's Sources table.
  - `PartSourceVariant` — a specific orderable SKU/packaging option under a `PartSource` listing. Fields: `source` (FK → `PartSource`, `CASCADE`, `related_name='variants'`), `supplier_sku`, `packaging` (e.g. "Tape & Reel (TR)", "Cut Tape (CT)"), `url` (`URLField`), `moq` (`PositiveIntegerField`, nullable — minimum order quantity; `None` means unknown), `last_refreshed` (`DateTimeField`, nullable — when pricing/stock was last fetched from a supplier API via `_refresh_variant()`; `None` means it was only ever added manually via `part_source_add` and has never been fetched). `Meta.ordering = ['supplier_sku']`.
  - `PartPriceBreak` — a quantity-based price break for a `PartSourceVariant` (e.g. qty 1 @ $0.50, qty 10 @ $0.45). Fields: `variant` (FK → `PartSourceVariant`, `CASCADE`, `related_name='price_breaks'`), `quantity`, `price` (`DecimalField`, 12/6), `currency` (ISO code, default `'USD'` — most supplier APIs don't report a currency code at all, so it's stored as an assumption rather than something read from the response; LCSC's API returns a `"$"` symbol rather than an ISO code, so that's normalised to `'USD'` too rather than stored as-is). `Meta.ordering = ['quantity']`, `unique_together = [('variant', 'quantity')]`. `CURRENCY_SYMBOLS` class dict + `symbol` property map the stored ISO code to a display prefix (e.g. `'USD'` → `'$'`); the Part edit page renders breaks as `{{ symbol }}{{ price }} {{ currency }}` (e.g. `$0.5904 USD`).
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
  - `batch_list` / `batch_add` / `batch_edit` / `batch_delete` (`/batches/...`) — CRUD for `Batch`. `batch_edit` is also the detail page, managing the batch's `BatchProductionStage` list and, below it, a read-only **Parts Required** card (Part/Required/Stock/Available columns) built from `_batch_parts_required()` (see below). `batch_add` pre-selects `design` from a `?design=<id>` query param. `batch_list`'s first column is headerless and shows the batch number as `#<pk>` (there's no separate batch-number field — it's just the `Batch` primary key). The Progress column renders one small rounded square per production stage (via `get_status_color_class()`), instead of a "N production stages" count; `production_stages` is `prefetch_related()`d to avoid an N+1 query. The page has a Display button (see Display Mode) and polls `batch_list_data` every 30 seconds to update each row's progress squares in place; if the set of batch ids returned no longer matches what's rendered (a batch was added/deleted elsewhere), the JS calls `reloadPreservingDisplayMode()` to resync the whole table rather than patching it row-by-row.
  - `_batch_parts_required(batch)` — aggregates a batch's required parts: groups the design's `DesignBomEntry` rows by `Part` (via `collections.Counter`, so e.g. two 10k resistors per board collapse to one row), multiplies each part's per-board placement count by `batch.quantity`, and returns one row per distinct part sorted by name. Used by `batch_edit` to render the Parts Required card; rows show the same "no sources" / stale-stock warning icons as the Parts list (see `part_list` below).
  - `batch_list_data` (`/batches/data/`) — JSON endpoint polled by `batch_list.html`: returns each batch's id and its production stages' name/status display/color class, used to refresh the Progress squares without a full page reload.
  - `batch_print` (`/batches/<id>/print/`) — see Printable Pages below.
  - `batch_duplicate` (`/batches/<id>/duplicate/`, POST-only) — creates a new `Batch` with the same `design`/`po`/`quantity` as the source batch (`notes` is deliberately left blank, since notes are typically specific to the original run), and copies its `BatchProductionStage` rows (name/color/order) with `status` reset to `NOT_STARTED` and `due_date`/`completion_date` left unset, so a new batch can be set up from a previous one without carrying over its progress. Redirects to the Batches list (rather than the new batch's edit page) so the new entry is shown alongside the rest. Exposed as a Duplicate button (`cil-copy` icon) on each row of the Batches list and in a toolbar above the Edit Batch form (the latter is a standalone `<form>` outside the page's main edit form, since forms can't nest).
  - `batch_apply_template` — applies a `ProductionStageTemplate` to a batch via `_apply_template_to_batch()`, which snapshots each `ProductionStageTemplateStep`'s stage into a new `BatchProductionStage`, appended after any existing stages. Stages whose `name` already exists on the batch are skipped, so re-applying (or applying a second template) only adds genuinely new stages.
  - `batch_production_stage_add` / `_update` / `_delete` — manage individual `BatchProductionStage` rows on a batch: manual add (snapshots name/color from a chosen `ProductionStage`), inline due-date/completion-date update, delete.
  - `batch_production_stage_reorder` (`/batches/<id>/reorder-production-stages/`) — AJAX endpoint, same `{"order": [...]}` pattern, scoped to one batch's production stages.
  - `batch_production_stage_set_status` (`/batches/production-stage/<id>/set-status/<status>/`) — AJAX endpoint (POST, no body): sets the stage's `status`; if `status == DONE`, also sets `completion_date = timezone.now()`. Returns JSON `{status, table_class, completion_date}` (the latter formatted `Y-m-dTH:i:s` in the active timezone for direct use in a `datetime-local` input).
  - `location_list` (`/settings/locations/`) — renders the full location tree using `_build_location_tree()`. Each row shows the name (indented by depth with a `└` glyph for non-root items), description, and Add Child / Edit / Delete buttons. "Add Child" links to `location_add?parent=<id>`.
  - `location_add` / `location_edit` / `location_delete` (`/settings/locations/...`) — CRUD for `Location`. Add pre-selects the parent from a `?parent=<id>` query param. Edit excludes the location and all its descendants from the parent dropdown to prevent cycles (`_get_descendant_pks()` helper in `forms.py`). Delete shows a cascade warning when the location has children.
  - `part_category_list` (`/settings/part-categories/`) — renders the full category tree using `_build_part_category_tree()`. Same layout as the location list: indented name, description, Add Child / Edit / Delete buttons.
  - `part_category_add` / `part_category_edit` / `part_category_delete` (`/settings/part-categories/...`) — CRUD for `PartCategory`. Same pattern as the location views: `?parent=<id>` pre-selection on add, cycle prevention on edit, cascade warning on delete.
  - `part_list` (`/parts/`) — lists all parts grouped by category, with `table-secondary` sub-heading rows. Uncategorised parts appear first. Uses `Prefetch` (`sources__variants`) to load each category's parts, sources, and variants in one query, and annotates each part with `bom_entry_count` (count of `DesignBomEntry` rows referencing it). Supports server-side filtering via the `q` query param (same `initServerFilter` pattern as the Designs list), filtering across `name`, `value`, `package`, and `device` fields. Includes a "Populate from BOM" button that opens a CoreUI modal for CSV upload. Columns: Name, Value, Package, Device, Stock (`Part.stock`, manually-tracked), Available (`Part.total_stock`, summed from sources), BOM Refs (`bom_entry_count`, shown as `-` when zero) — both Stock and Available show `-` when null. A warning triangle (`bi-exclamation-triangle-fill`) appears before the name if the part has no `PartSource` listings at all, and after the Available value if `Part.has_stale_source_data` is `True`.
  - `part_add` / `part_edit` / `part_delete` (`/parts/...`) — CRUD for `Part`. `part_edit` serves as both the detail and edit page: shows the image (if set) above the form, then a **Sources** card, a **Possible Substitutions** card, a **BOM References** card (staff only, hidden when the part has no `DesignBomEntry` rows), and an **Attachments** card. The form includes `stock` between Fusion Library and Image. Each source listing's stock figure in the Sources table shows the same stale-data warning triangle as the Parts list when `PartSource.has_stale_variant_data` is `True`. Saving a part redirects to `part_list`. Deleting a part also deletes the image file from disk. The BOM References card lists every `Design` that has a `DesignBomEntry` pointing to this part (with a link to the design detail page and the reference designators used); entries are grouped by design in the view via `_by_design` dict built from the prefetched `design_bom_entries__design__client` relation, then sorted by `sku`. Below the table, a **Reparent All** form (`part_reparent`, POST to `/parts/<id>/reparent/`) lets staff reassign every `DesignBomEntry` referencing this part to a different target part in one operation (confirmed via a JS prompt); on success it redirects back to the same part edit page with a count message.
  - `part_reparent` (`/parts/<id>/reparent/`, POST-only) — bulk-updates all `DesignBomEntry` rows with `part=<this part>` to `part=<target>` via a single `.update()` call. Uses `PartReparentForm` for validation; redirects back to `erp:part_edit` in all cases.
  - `part_asset_add` / `part_asset_delete` (`/parts/<id>/add-asset/`, `/parts/asset/<id>/delete/`) — manage `PartAsset` attachments on a part; delete also removes the file from disk. The attachment upload row auto-populates the Name field from the selected filename via JavaScript.
  - `_get_or_create_supplier_listing(part, supplier_name, manufacturer_sku, stock)` — finds or creates the `PartSource` listing a new variant should be filed under. Only merges into an existing listing when `manufacturer_sku` is non-blank (case-insensitive match on `supplier_name`+`manufacturer_sku`) — a blank SKU never merges, since two listings both missing a manufacturer SKU aren't necessarily the same part. Used by `part_source_add` and all four `part_source_fetch_*` views below.
  - `_save_price_breaks(variant, price_breaks)` — replaces all `PartPriceBreak`s for a `PartSourceVariant` with the supplied list of `{quantity, price, currency}` dicts.
  - `part_source_add` (`/parts/<id>/add-source/`) — POST form; `PartSourceForm` is a plain `Form` (not a `ModelForm`, since it spans both `PartSource` and `PartSourceVariant`) with fields `supplier_name`, `supplier_sku`, `url`, `manufacturer_sku`, `packaging`, `moq`, `stock`. Get-or-creates the listing via `_get_or_create_supplier_listing()`, then always creates a new `PartSourceVariant` — so adding a second SKU with a manufacturer SKU that's already on file for that supplier groups it under the same listing (and shares its stock) instead of creating a duplicate listing.
  - `part_source_delete` (`/parts/source/<id>/delete/`) — deletes a whole `PartSource` listing (cascades to its variants and their price breaks).
  - `part_source_variant_delete` (`/parts/source/variant/<id>/delete/`) — deletes a single `PartSourceVariant`; if that was the listing's last variant, deletes the now-empty listing too.
  - `_refresh_variant(variant)` — does the actual supplier-API fetch-and-save work for one `PartSourceVariant`: branches on `variant.source.supplier_name` (supports `'lcsc'`, `'digikey'` or any name containing `"digikey"`, `'mouser'`, and any name containing `"element14"`/`"farnell"`/`"newark"`), updates `manufacturer_sku`/`stock` on the parent listing and `packaging`/`url`/`moq` on the variant (only overwriting `moq` when the branch actually reported a value, so refreshing an Element14 source doesn't wipe out a manually-entered MOQ), fills `part.description` if empty, and saves a product image to the part if none exists. The LCSC, DigiKey, and Mouser branches also save price breaks via `_save_price_breaks()` (Element14 doesn't return price-break data). Returns `{'ok': True}` or `{'ok': False, 'error': '...'}` — never raises, and never touches `last_refreshed` itself. Shared by the `part_source_refresh` view below and the `refresh_part_sources` management command (see below) so the fetch logic only exists once.
  - `part_source_refresh` (`/parts/source/variant/<id>/refresh/`) — POST-only AJAX endpoint: thin wrapper around `_refresh_variant()` that also stamps `variant.last_refreshed = timezone.now()` regardless of success/failure. Returns `_refresh_variant()`'s result as JSON; JS reloads the page on `{"ok": true}`.
  - `part_source_fetch_lcsc` (`/parts/source/fetch-lcsc/`) — POST-only AJAX endpoint: accepts JSON `{"sku": "...", "part_id": N}`. Uses `_lcsc_search()` (direct `requests` calls to LCSC's unofficial JSON API at `wmsc.lcsc.com`, replicating the relevant part of the `lcsc` PyPI client's behaviour without that package's Python >=3.13 requirement) to look up the SKU; also returns `price_breaks` (from `productPriceList`, currency always normalised to `'USD'`) and `moq` (from `minBuyNumber`, verified live). Get-or-creates the listing (supplier `'LCSC'`) via `_get_or_create_supplier_listing()` if no variant exists for that SKU yet; populates the new variant's `packaging` from `product_arrange`, `url` constructed from `product_code`, `moq`, and price breaks via `_save_price_breaks()`. Fills `part.description` from `product_intro_en` if empty. Saves first product image to the part if the part has no image. Returns JSON including `source_saved` (bool); JS reloads on `source_saved`, otherwise pre-fills the add-source form.
  - `_digikey_price_breaks(variation)` — extracts price breaks from a DigiKey `ProductVariation`'s `StandardPricing` list (`BreakQuantity`/`UnitPrice`, currency always `'USD'` — DigiKey's v4 API doesn't return a per-tier currency code).
  - `_propagate_digikey_sibling_data(listing, variations)` — DigiKey's `productdetails` response includes **every** packaging variation's pricing and MOQ (`MinimumOrderQuantity`) in one call, not just the SKU that was looked up. This matches each existing `PartSourceVariant` under `listing` against the response's `ProductVariations` (by `DigiKeyProductNumber` == `supplier_sku`) and saves price breaks + `moq` for every match — so refreshing or fetching *any one* DigiKey SKU backfills pricing/MOQ for its sibling SKUs (different packaging of the same manufacturer part) too, without a separate API call per SKU.
  - `part_source_fetch_digikey` (`/parts/source/fetch-digikey/`) — POST-only AJAX endpoint: same contract as `fetch_lcsc` but uses the DigiKey API v4 (`GET /products/v4/search/{sku}/productdetails`). Calls `_get_digikey_access_token()` to obtain a valid Bearer token (refreshing from `token_storage.json` if expired). Extracts `packaging` from `ProductVariations` by matching `DigiKeyProductNumber` to the requested SKU; get-or-creates the listing (supplier `'DigiKey'`) and creates the new variant, then calls `_propagate_digikey_sibling_data()` to backfill pricing/MOQ for it and any existing sibling variants under the same listing. Fills `part.description` from `Description.DetailedDescription`. Saves `PhotoUrl` as the part image if none exists.
  - `_mouser_price_breaks(p)` — extracts price breaks from a Mouser Part's `PriceBreaks` list. Unlike DigiKey/LCSC, Mouser's `Price` field is a string with a currency symbol prefix (e.g. `"$0.3600"`), so it's stripped to digits/decimal point before storage; `Currency` is taken from the response (defaulting to `'USD'` if absent).
  - `part_source_fetch_mouser` (`/parts/source/fetch-mouser/`) — POST-only AJAX endpoint: same contract. Uses `POST /api/v1/search/partnumber?apiKey={key}` with `MOUSER_API_KEY`. Extracts `packaging` from `ProductAttributes` by finding an attribute whose name contains `"packag"`; `moq` from the `Min` field (verified live); price breaks via `_mouser_price_breaks()` and `_save_price_breaks()`. Fills `part.description` from the `Description` field. Saves `ImagePath` as the part image if none exists.
  - `part_source_fetch_element14` (`/parts/source/fetch-element14/`) — POST-only AJAX endpoint: same contract. Uses `GET https://api.element14.com/catalog/products` with `ELEMENT14_API_KEY` and `ELEMENT14_STORE_ID` (regional storefront, e.g. `au.element14.com`). Searches by `term=sku:{sku}` with `resultsSettings.responseGroup=large`. Extracts `manufacturerPartNumberList[0]` for manufacturer SKU; packaging from `attributes[]` (attribute label containing "packag") or falls back to `packSize` formatted as "Pack of N"; stock from `stock`; image from `imageList.image[0].url` (protocol-relative URLs are prefixed with `https:`). The refresh view matches on supplier names containing `"element14"`, `"farnell"`, or `"newark"`. **TODO:** unlike LCSC/DigiKey/Mouser, this endpoint does not populate `PartSourceVariant.moq` — no `ELEMENT14_API_KEY` was configured at the time MOQ support was added, so the response's MOQ field name couldn't be verified live. Once a working key is available, check a live response for the MOQ field (candidates seen in other Element14/Farnell API versions: `translatedMinimumOrderQuanity`, `minimumOrderQuantity`) and wire it up the same way as the other suppliers.
  - `_digikey_base_url()` — helper that returns `https://sandbox-api.digikey.com` or `https://api.digikey.com` based on the `DIGIKEY_CLIENT_SANDBOX` env var. Used by all DigiKey OAuth and API calls so that sandbox/production is switched in one place.
  - `_get_digikey_access_token()` — helper that reads `{DIGIKEY_STORAGE_PATH}/token_storage.json`, refreshes the access token via `POST /v1/oauth2/token` if the `expires` timestamp has passed, saves the refreshed token back to the file, and returns `(client_id, access_token)`. Raises `RuntimeError` on missing config or failed refresh.
  - `digikey_connect` (`/parts/source/digikey-connect/`) — redirects to the DigiKey OAuth authorisation URL (using `_digikey_base_url()`). Staff-only.
  - `digikey_callback` (`/parts/source/digikey-callback/`) — receives the OAuth authorisation code from DigiKey, exchanges it for a token via `POST /v1/oauth2/token`, and saves the token JSON (with an added `expires` epoch timestamp) to `token_storage.json`. The token is saved in the format `_get_digikey_access_token()` expects.
  - `part_import_bom` (`/parts/import-bom/`) — POST-only; reads a CSV file (`utf-8-sig` encoding) with columns `reference`, `device`, `package`, `value`, `library`. Each row is resolved via the shared `_resolve_bom_csv_row()` helper (see below) and reports added/skipped/excluded counts via messages.
  - `_resolve_bom_csv_row(row, exclusion_rules, equivalence_rules, library_settings_by_name)` — shared per-row BOM CSV resolution, used by both `part_import_bom` above and `design_bom_populate` below. In order: skips the row if it matches a `BomExclusionRule` (`_bom_row_is_excluded()`); applies the first matching `BomEquivalenceRule` to remap `library`/`device`/`package`/`value` (`_bom_apply_equivalence()`); applies the row's `BomLibrarySetting` (if any, looked up by the post-transformation library) to blank out `device`/`package`/`value` per its `ignore_*` flags; then checks for an existing `Part` matching `device`, `package`, and `value` (case-insensitive `__iexact`; `fusion_library` is intentionally excluded so the same physical part from different Fusion libraries is not duplicated), otherwise creates a new part with `name = " ".join([value, package, device.capitalize()])` and `fusion_library` set to the (possibly remapped) library. Returns `(reference, part, created)`, or `None` if excluded. `_bom_field_matches(rule_value, row_value)` is the shared "blank rule field matches anything" comparison helper used by both rule types.
  - `design_bom_populate` (`/design-bom/<design_id>/populate/`, POST-only) — seeds a `Design`'s `DesignBomEntry` rows from its uploaded BOM CSV `DesignAsset`, via `_resolve_bom_csv_row()`. Rows whose `reference` is already present on the design are skipped, so re-running after manual edits never duplicates or overwrites them. Also calls `_apply_brd_placements()` (see below) to backfill `pos_x`/`pos_y`/`rotation`/`side` on every entry — new and pre-existing — from the design's PCB Design File asset. The success message reports added/skipped/excluded counts plus, when applicable, how many new `Part`s were created in the Parts library and how many entries' positions were updated from the PCB design file. Exposed as a "Populate from BOM" button on the Design detail page's Bill of Materials section (staff only).
  - `design_bom_entry_add` (`/design-bom/<design_id>/add/`, POST-only) — adds a new `DesignBomEntry` via the inline add row at the bottom of the Design detail page's Bill of Materials table (staff only), using `DesignBomEntryForm` (`reference`/`part` only).
  - `design_bom_entry_edit` (`/design-bom/entry/<entry_id>/edit/`) — GET renders a dedicated edit page ([erp/design_bom_entry_edit.html](pyproj/erp/templates/erp/design_bom_entry_edit.html), staff only) with `DesignBomEntryForm` pre-filled for the entry; POST validates and saves, then redirects back to the Design detail page at its `#bom` anchor. The Bill of Materials table itself is read-only — each row is the whole `<tr>` (`clickable-row` class, same pattern as the Design Files/Attachments tables) linking to this edit page rather than holding inline form fields, since editing every row's `part` field inline meant rendering a full `Part` dropdown (`Part.objects.all()`, default queryset) once per row — an N+1 query and an O(rows × parts) HTML cost that was the main cause of the Design detail page being slow once the BOM list and Parts library both grew.
  - `design_bom_entry_delete` (`/design-bom/entry/<entry_id>/delete/`, POST-only) — deletes a `DesignBomEntry`. Its row's delete button (`cil-trash`) sits in a cell with `onclick="event.stopPropagation()"` so clicking it doesn't also trigger the row's navigation to the edit page.
  - `_parse_brd_placements(brd_path)` — parses a Fusion-exported EAGLE `.brd` XML file's `drawing/board/elements/element` entries into `{reference designator: {pos_x, pos_y, rotation, side}}`. Joins on the reference designator (matches the BOM CSV's `reference` column exactly, since both are generated from the same board) rather than library/device/package/value, which don't line up reliably between the two exports. An element's `rot` attribute (e.g. `R90`, `MR180`) is parsed into a plain degree value plus a `TOP`/`BOTTOM` side — an `M` prefix means mirrored, i.e. a bottom-side placement.
  - `_apply_brd_placements(design)` — looks up the design's `PCB_DESIGN` (PCB Design File) `DesignAsset`, parses it via `_parse_brd_placements()`, and `bulk_update()`s `pos_x`/`pos_y`/`rotation`/`side` on every matching `DesignBomEntry`. Returns `None` if the design has no PCB Design File asset, otherwise the number of entries updated. Called by `design_bom_populate` above.
  - `part_import_filter_list` (`/settings/part-import-filters/`) — the merged "Part Import Filters" settings page: renders `BomExclusionRule`, `BomEquivalenceRule`, and `BomLibrarySetting` as three sections on one page, in the order they're applied in `part_import_bom`. `_part_import_filter_context()` builds the shared context (querysets + a form per section) reused by this view and by each rule type's `_add` view below.
  - `bom_exclusion_rule_add` / `bom_exclusion_rule_edit` / `bom_exclusion_rule_delete` (`/settings/bom-exclusion-rules/...`) — CRUD for `BomExclusionRule`. `_add` is POST-only (GET redirects to `part_import_filter_list`); on validation failure it re-renders the merged page via `_part_import_filter_context()` with the invalid bound form swapped in for that section, so errors show inline without a dedicated list page.
  - `bom_equivalence_rule_add` / `bom_equivalence_rule_edit` / `bom_equivalence_rule_delete` (`/settings/bom-equivalence-rules/...`) — CRUD for `BomEquivalenceRule`, same `_add`-redirect/re-render pattern as exclusion rules.
  - `bom_library_setting_add` / `bom_library_setting_edit` / `bom_library_setting_delete` (`/settings/bom-library-settings/...`) — CRUD for `BomLibrarySetting`, same pattern.
- **[management/commands/refresh_part_sources.py](pyproj/erp/management/commands/refresh_part_sources.py)** — `python manage.py refresh_part_sources` refreshes `PartSourceVariant`s due for an update (via `_refresh_variant()`) in a bounded, oldest-first batch per invocation, rather than all at once. "Due" means `last_refreshed` is `None` or older than 24h. Batch size is `max(1, ceil(total_variant_count / 24))`, capped by `--max-per-run` (default 50) so a backlog (e.g. after a missed run) can't burst every supplier at once. Within a run, a per-supplier minimum delay (`SUPPLIER_MIN_INTERVAL`, keyed by the same supplier grouping `_refresh_variant()` uses — LCSC is the most conservative since it's an unofficial API) is enforced between consecutive calls to the same supplier. `last_refreshed` is stamped after every attempt, success or failure, so a persistently-failing variant (e.g. delisted SKU) is only retried about once a day rather than monopolising every run — failures are still logged per-variant via `self.stderr`. `--dry-run` lists what would be refreshed without calling any API. Not invoked by the app itself — intended to be run hourly via a server crontab entry (documented in [SETUP.md](SETUP.md)), so a day's worth of refreshes is spread across 24 runs instead of one nightly burst.
- **[forms.py](pyproj/erp/forms.py)** — `ProductionStageForm` (name + colour picker), `ProductionStageTemplateForm` (name + description), `ProductionStageTemplateStepForm` (production stage select, ordered per `ProductionStage.Meta.ordering`), `BatchForm` (design/po/quantity/notes — uses `DesignChoiceField`, a `ModelChoiceField` subclass that labels each option as `"{org} {sku}: {name} v{version}"` and orders by org → SKU → name → version), `BatchApplyTemplateForm` (template select, ordered per `ProductionStageTemplate.Meta.ordering`), `BatchProductionStageAddForm` (production stage select, for manual add), `BatchProductionStageUpdateForm` (due_date/completion_date only — status is no longer part of this form, see below), `LocationForm` (parent dropdown with `empty_label='(top level)'`, name, description — uses `_get_descendant_pks()` to filter invalid parent choices when editing), `PartCategoryForm` (same structure as `LocationForm` — parent dropdown, name, description — also uses `_get_descendant_pks()` for cycle prevention), `PartForm` (`name`, `description`, `category` dropdown with `empty_label='(uncategorised)'`, `device`, `package`, `value`, `fusion_library`, `stock`, `image` `ClearableFileInput` — field order on the edit page: Name → Device/Package/Value → Category → Description → Fusion Library → Stock → Image), `PartAssetForm` (file, name, description), `PartSourceForm` (a plain `Form`, not a `ModelForm` — see `part_source_add` above for why — with `supplier_name`, `supplier_sku`, `url`, `manufacturer_sku`, `packaging`, `moq`, `stock`, all rendered as small Bootstrap form controls for inline use in the part edit page), `PartReparentForm` (a plain `Form` with a single `target_part` `ChoiceField`; excludes uncategorised parts and groups the dropdown into `<optgroup>` sections by category — built as grouped `(category_name, [(pk, label)])` tuples so Django's `Select` widget renders optgroups natively; `clean_target_part()` converts the submitted pk string to a `Part` object), `BomExclusionRuleForm` (`library`, `device`, `package`, `value` — `clean()` requires at least one field set, since an all-blank rule would exclude every imported row), `BomEquivalenceRuleForm` (From/To pairs in field order `from_library`/`to_library`, `from_device`/`to_device`, `from_package`/`to_package`, `from_value`/`to_value` — `clean()` requires at least one "from" field and at least one "to" field set), `BomLibrarySettingForm` (`library`, `ignore_device`, `ignore_package`, `ignore_value` checkboxes). The `_get_descendant_pks(all_items, root_pk)` helper is generic: it accepts any list of objects with a `parent_id` attribute and returns the set of all descendant PKs via iterative BFS.
- **[admin.py](pyproj/erp/admin.py)** — registers `Location`, `PartCategory` (both: list display name/parent/description, `list_select_related`, `search_fields`), `Part` (list display name/category/value/package/device/fusion_library, `list_select_related`, search; with inline `PartAsset` and `PartSource` editors — the `PartSource` inline shows the listing level only, not its variants), `PartSource` (registered separately too: list display part/supplier_name/manufacturer_sku/stock, `list_select_related`, search; with an inline `PartSourceVariant` editor for managing SKUs/packaging/MOQ directly), `ProductionStage`, `ProductionStageTemplate` (with an inline `ProductionStageTemplateStep` editor), `Batch` (with an inline `BatchProductionStage` editor), `BomLibrarySetting`, `BomExclusionRule`, and `BomEquivalenceRule` (each: list display of its fields, `search_fields`, no inlines).
- **Drag-and-drop reordering**: the Production Stages list, the Production Stage Templates list, the steps list on the Template edit page, and the Production Stages list on the Edit Batch page all support drag-and-drop reordering via [SortableJS](https://github.com/SortableJS/Sortable) (loaded from CDN in each template's `extra_js` block) plus the shared `initSortableReorder(tbodyId)` helper in [static/js/script.js](pyproj/static/js/script.js). Each draggable `<tbody>` has an `id` and `data-reorder-url="..."`; each `<tr>` has `data-stage-id="{{ pk }}"`; a `bi-grip-vertical` icon in the first column is the drag handle. On drop, the new row order is POSTed as JSON to the corresponding `*_reorder` view. The old up/down move buttons and `*_move` views have been removed.
- **Batch production stage status**: on the Edit Batch page, each `BatchProductionStage`'s status is shown as 4 icon buttons (`bi-circle` Not Started, `bi-play-circle` In Progress, `bi-pause-circle` On Hold, `bi-check-circle` Done) instead of a dropdown; the current status is shown as a solid (filled) button, others as outline. Clicking a button calls `initStatusButtons(tbodyId)` (also in `static/js/script.js`), which POSTs to `batch_production_stage_set_status` and updates the button highlighting, row colour, and Completion Date field in place — no page reload.
- `static/js/script.js` also provides a shared `getCookie(name)` helper (used to read the `csrftoken` cookie for the `X-CSRFToken` header on the AJAX `fetch()` calls above).
- Sidebar: staff users see a "Batches" link (`erp:batch_list`) above "Boards", a "Parts" link (`erp:part_list`) between "Organisations" and "Settings", and a "Settings" link (`erp:settings_index`). Active-state detection uses `url_name` prefix slicing: Parts is active when `url_name` starts with `"part_"` but not `"part_c"` (which is `part_category_*`, a Settings URL) and is not `"part_import_filter_list"` (the merged Part Import Filters page, also a Settings URL); Settings uses an `{% elif %}` chain to re-include `part_category_*` and `part_import_filter_list` after the `"part_"` exclusion. The Design detail page has an "Add New Batch" button (staff only) linking to `erp:batch_add` with `?design=<id>`, which pre-selects that design in the `BatchForm`.

### `testing`

Test equipment tracking: **Testers** (physical Testomatic chassis that can be set up to test different board types) and **Test Modules** (inserted into a chassis to customise it for a specific target Device Under Test). The section is reached via a staff-only top-level "Testers" sidebar link (`testing:tester_list`, active when `app_name == 'testing'`); all views are `@staff_member_required`. URLs are mounted at the site root under `testers/...` (`app_name = 'testing'`, included from `conf/urls.py` like `erp.urls`).

- **[models.py](pyproj/testing/models.py)**:
  - `Tester` — a physical chassis. Fields: `name`, `version` (blank allowed), `notes`. IDs are the auto PK, displayed as `#<pk>` (same convention as Batches). Will later grow API-key/self-identification fields for uploading test results.
  - `TestModuleType` — an abstract definition of a test module: `name`, `version`, and `compatible_designs` (M2M → `device.Design`, `related_name='test_module_types'` — one module type may suit multiple designs, e.g. a revised design with unchanged test points). Equivalence between module types is **not** modelled explicitly; it's implicit via shared compatible designs.
  - `TestModule` — a physical module: `module_type` (FK → `TestModuleType`, `PROTECT`, `related_name='modules'`) plus `notes`. Its displayed name/version come from the type.
- **[views.py](pyproj/testing/views.py)** / **[urls.py](pyproj/testing/urls.py)** — `tester_list` (`/testers/`) is the main page: three cards (Testers, Test Modules, Test Module Types) each with an inline add row. Because three add forms share the page, the list view is GET-only and each inline row POSTs to a dedicated POST-only add view (`tester_add`, `test_module_add`, `test_module_type_add`), and each form uses a distinct prefix (`tester`/`module`/`module_type`) to avoid duplicate field ids. `test_module_type_add` redirects to the new type's edit page so compatible designs can be added immediately; the other add views redirect back to the list. Standard edit/delete views per model; `test_module_type_delete` guards `ProtectedError` (type in use by physical modules). `test_module_type_edit` also manages the `compatible_designs` M2M (add via dropdown using `CompatibleDesignAddForm`, which excludes already-added and obsolete designs; remove via per-row POST forms — `test_module_type_design_add`/`_remove`) and lists the type's physical modules.
- **[forms.py](pyproj/testing/forms.py)** — `TesterForm`, `TestModuleTypeForm` (name/version only — the M2M is managed via the dedicated views), `TestModuleForm`, `CompatibleDesignAddForm` (single `DesignChoiceField` — a local copy of erp's, labelling options `"{org} {sku}: {name} v{version}"`).
- **[admin.py](pyproj/testing/admin.py)** — registers all three models; `TestModuleTypeAdmin` uses `filter_horizontal` for `compatible_designs` and an inline `TestModule` editor.
- Included in `export_data`/`import_data` (see `device` management commands below); in `_flush_app_data()` the testing models are deleted first (`TestModule` before `TestModuleType` because of PROTECT).

### `pcba`

Placeholder app, plus a `pcba.designs` sub-app (also in `INSTALLED_APPS`) containing a parallel, **not-yet-wired-up** redesign of the PCB design data model:

- **[designs/models.py](pyproj/pcba/designs/models.py)** — New `Design` / `DesignVersion` / `DesignAsset` models. `Design` now holds only `name`, `sku`, `description`, and `owner` (FK → `crm.Org`); per-revision fields (`hw_version`, `price`, `DesignAsset`s) move to `DesignVersion`. `DesignAsset` here is a near-copy of `device.DesignAsset` but FKs to `DesignVersion` instead of `Design`.
- **[designs/admin.py](pyproj/pcba/designs/admin.py)** — Admin registrations for the above (`DesignVersionAdmin` with inline `DesignAsset`, `DesignAdmin` with inline `DesignVersion`).
- No views, URLs, or templates reference `pcba.designs` yet — the live Design/DesignAsset models are still `device.models.Design` / `device.models.DesignAsset`.

### `device` (main app)

All PCB business logic lives here.

- **[models.py](pyproj/device/models.py)** — All device models, plus the still-current `Design`/`DesignAsset` (see `pcba` above for their planned eventual replacements). `get_dt_as_string()` suppresses time display when stored with the sentinel `witching_hour` (3:14:15 AM local time), used for date-only imports.
- **[views.py](pyproj/device/views.py)** — Django views. Non-staff users only see data belonging to their associated `Org`(s). List pages (Boards, Designs) use server-side filtering (not client-side) so filtering works correctly with pagination. Designs list is paginated. Device asset views (`device_asset_add`, `device_asset_edit`, `device_asset_delete`) mirror the design asset views.
- **[api.py](pyproj/device/api.py)** — Device/design/test-record API endpoints, decorated onto the shared `router` imported from `api.routes`. See the `api` app above for the router/auth setup. `add_device_image` checks access via org membership (`device.design.client.users.filter(pk=request.auth.pk).exists()`) rather than a single-org equality check, since a user can belong to more than one `Org`.
- **[schemas.py](pyproj/device/schemas.py)** — Pydantic schemas for the device API endpoints.
- **[admin.py](pyproj/device/admin.py)** — Django admin config at `/office/`.
- **[urls.py](pyproj/device/urls.py)** — URL patterns under `/device/`. Note: design and organisation URLs are in `conf/urls.py`, not here.
- **[context_processor.py](pyproj/device/context_processor.py)** — Context processors: `background_processor` (deploy-type background), `demo_processor` (demo mode vars), `version_processor` (injects `app_version` from `settings.VERSION`).
- **[management/commands/import-xlsx.py](pyproj/device/management/commands/import-xlsx.py)** — Bulk import from Excel; requires sheets `Devices` and `DeviceTypes` (any additional sheets such as Queue or Patched Boards are ignored).
- **[management/commands/export_data.py](pyproj/device/management/commands/export_data.py)** — Exports all `crm`, `device`, `erp`, and `testing` records plus `MEDIA_ROOT` files (excluding thumbnail cache) to a self-contained ZIP archive. User accounts are not included. Run with `python manage.py export_data [output.zip]`.
- **[management/commands/import_data.py](pyproj/device/management/commands/import_data.py)** — Imports a ZIP produced by `export_data`, performing a clean-slate replace (deletes all existing app data first). The database flush and load run inside a single transaction so a failure rolls back cleanly. Run with `python manage.py import_data archive.zip [--yes]`. Run as a different user than the one that owns existing `MEDIA_ROOT` files (e.g. running manually as a login user while uWSGI writes as `uwsgi`), this can fail with `PermissionError` deleting old media files — the production uWSGI vassal template sets `umask = 002` so new uploads stay group-writable, but pre-existing files/dirs created before that setting was added may still need `chmod -R g+w` on `MEDIA_ROOT` once.

### `authuser`

Custom user model using **email as username** instead of a username field. Users have `full_name`, `preferred_name`, `avatar_type` (initials or Gravatar), and `api_key` (see API Keys below).

- **[models.py](pyproj/authuser/models.py)** — `User` extends `AbstractBaseUser`. Get it via `from django.contrib.auth import get_user_model`. `api_key` is a unique, nullable `CharField`; `regenerate_api_key()` sets it to `secrets.token_urlsafe(32)`, saves, and returns the new key — the single place both the self-service and staff-side regenerate actions call, so key generation logic isn't duplicated.
- **[views.py](pyproj/authuser/views.py)** / **[urls.py](pyproj/authuser/urls.py)** — alongside the existing `user_settings` page (`/accounts/settings/`), `user_settings_regenerate_key` (`/accounts/settings/regenerate-key/`, POST-only) lets a user regenerate their own API key from their settings page. Named distinctly from `crm.views.users.user_regenerate_key` (the staff-side equivalent) since neither app namespaces its URLs.

### `conf`

Django project configuration.

- **[settings.py](pyproj/conf/settings.py)** — Main settings. Database config is in `local_settings.py`.
- **[local_settings.py](pyproj/conf/local_settings.py)** — Machine-specific overrides (gitignored in prod). Sets `DEBUG`, database, `API_ALLOW_IPV4_SUBNET`, `MEDIA_ROOT`.
- **[middleware.py](pyproj/conf/middleware.py)** — `TimezoneMiddleware` activates the configured timezone per request.
- **[urls.py](pyproj/conf/urls.py)** — Root URL configuration.

## REST API

Base URL: `/api/v1/` — implemented with [Django Ninja](https://django-ninja.dev/).

**Authentication:** `X-API-Key: <key>` header OR Django session cookies. Keys are stored per-`User` (`authuser.User.api_key`), not per-`Org` — see API Keys below. API key requests are restricted by IP (localhost always allowed; configure `API_ALLOW_IPV4_SUBNET` for other subnets).

Key endpoints:

| Method | URL | Description | Auth |
|---|---|---|---|
| GET | `/api/v1/clients/` | List clients (scoped to the caller's orgs unless staff) | API key |
| GET | `/api/v1/designs/` | List designs (scoped to the caller's orgs unless staff; filter further with `?client_pk=`) | API key |
| POST | `/api/v1/device/add/` | Create or update a device (design, and existing device if updating, must belong to a caller's org unless staff) | API key |
| GET | `/api/v1/device/{pk}/` | Get device details (device must belong to a caller's org unless staff) | API key |
| POST | `/api/v1/device/{pk}/program/` | Record firmware version (device must belong to a caller's org unless staff) | API key |
| POST | `/api/v1/device/{pk}/add-tr/` | Add test record (device must belong to a caller's org unless staff) | API key |
| POST | `/api/v1/device/{tr_pk}/add-image/` | Upload test image (multipart; the test record's device must belong to a caller's org unless staff) | API key |
| POST | `/api/v1/device/{pk}/add-device-image/` | Upload device image (multipart, device must belong to a caller's org unless staff) | API key |
| GET | `/api/v1/dashboard-stats/` | Dashboard statistics (client/design/device/part counts + chart data) | Session or API key |

Full documentation in [API.md](API.md).

**Org-scoping helpers:** `device/api.py` has two small helpers, `_user_can_access_design(user, design)` (`user.is_staff or design.client.users.filter(pk=user.pk).exists()`) and `_user_can_access_device(user, device)` (delegates to the design check via `device.design`), used by every device/design/test-record endpoint above except `get_clients`/`get_designs` (which filter querysets directly instead, since they return lists rather than a single object) to return `403, {'message': ...}` when the calling user's org membership doesn't cover the target. Added because API keys are now self-service per-user (see API Keys below) rather than admin-issued per-org, so any ordinary user can mint a key — these checks stop one org's key from reading or writing another org's devices/designs.

## Access Control

- **Staff users** see all data across all organisations.
- **Non-staff users** only see `Org`, `Design`, and `Device` objects associated with their user account via the `Org.users` M2M relationship.
- Internal `DeviceEvent` records (`internal=True`) are hidden from non-staff users.
- All views require login (enforced by `login_required` middleware).
- **API endpoints:** Traditional API endpoints require `X-API-Key` header + IP allowlist, resolved to a `User` (see API Keys below); inactive users' keys stop working immediately. Every endpoint that reads or writes a specific client/design/device scopes to the caller's orgs unless they're staff (see org-scoping helpers above), returning `403` if the target is outside the caller's orgs. The dashboard stats endpoint (`/api/v1/dashboard-stats/`) accepts either API key auth or Django session cookies (for browser-based polling) and scopes results to that user's orgs unless they're staff.
- Internal `DesignAsset` and `DeviceAsset` records (`internal=True`) are hidden from non-staff users.

## API Keys

API keys are per-`User` (`authuser.User.api_key`), not per-`Org` as in earlier versions of this app — a key authenticates as a specific user and is scoped to that user's orgs (or all orgs, if they're staff), rather than a single fixed org. Keys are **display + regenerate only**, never free text: `User.regenerate_api_key()` is the only way a key gets a value, so neither staff nor users can set a weak or guessable key by hand.

- **Self-service**: the user's own settings page (`/accounts/settings/`, `authuser.views.user_settings`) shows their current key and a "Regenerate" button.
- **Staff, on behalf of another user**: the Users management page (`/users/<id>/`, `crm.views.users.user_edit`) shows the same thing for any user.
- **Onboarding**: staff-created users (`crm.views.users.user_add`) get an unusable password and an emailed "set your password" link (reusing `authuser.views.SuperHousePasswordResetView`'s templates/from-address) rather than a key being set up front — they'd regenerate their own key from settings once they're logged in, if they need API access.

## Configuration / Environment

Environment variables are loaded from `pyproj/.env` (see `.env.template`):

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEPLOY_TYPE` | `dev`, `test`, or `prod` — controls background colour/image in the UI |
| `DEMO_MODE` | `True` hides sensitive data in the UI |
| `API_ALLOW_IPV4_SUBNET` | Additional IPv4 CIDR block allowed to use the API (e.g. `10.0.0.0/24`) |
| `ENABLE_GRAVATAR` | `True` to allow Gravatar avatars |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | SMTP settings for password reset and onboarding emails |
| `EMAIL_USE_TLS` / `EMAIL_USE_SSL` | `True`/`False` to select TLS vs SSL for the SMTP connection (default TLS on, SSL off). Must use these exact Django setting names — `EMAIL_TLS`/`EMAIL_SSL` are not real settings and are silently ignored. |
| `DIGIKEY_CLIENT_ID` | DigiKey OAuth2 client ID (from developer.digikey.com) |
| `DIGIKEY_CLIENT_SECRET` | DigiKey OAuth2 client secret |
| `DIGIKEY_STORAGE_PATH` | Absolute path to directory where the DigiKey OAuth token is stored (e.g. `pyproj/.digikey`) |
| `DIGIKEY_CLIENT_SANDBOX` | `True` to use the DigiKey sandbox API (`sandbox-api.digikey.com`); `False` for production. Set to `True` only if your DigiKey app is subscribed to sandbox (not Production Information V4) APIs. |
| `MOUSER_API_KEY` | Mouser Search API key (from mouser.com/api-hub) |
| `ELEMENT14_API_KEY` | Element14 / Farnell / Newark API key (from partner.element14.com) |
| `ELEMENT14_STORE_ID` | Regional storefront for Element14 API (e.g. `au.element14.com`, `uk.farnell.com`, `www.newark.com`; defaults to `au.element14.com`) |

## Dashboard

The dashboard (`/`) displays summary statistics (client/design/device counts, plus a staff-only Parts count card linking to `erp:part_list` — `erp.Part` isn't org-scoped, so it's hidden for non-staff rather than shown with a misleading global total) and a line chart of boards assembled per month. The display updates periodically via polling `/api/v1/dashboard-stats/` every 30 seconds. The chart only redraws if the underlying board data has changed; on each timed update the chart canvas size is also checked and redrawn if it has changed (handles window resizing). Stat cards briefly pulse green when their data changes (`flashUpdate()` no-ops if its target element doesn't exist, e.g. the Parts card for a non-staff viewer). A Display button (see Display Mode below) temporarily hides navigation for use as a status screen display.

Access control: Users see only data for their associated clients (if non-staff). Staff see all data, plus the Parts count card.

## Display Mode

Pages that benefit from a clean, kiosk-style view (e.g. a status board on a shop-floor screen) can offer a "Display" button that hides the sidebar, header, footer, and page heading, leaving only the page's own content. First built for the Dashboard, the mechanism is shared (in [static/js/script.js](pyproj/static/js/script.js) and [static/css/style.css](pyproj/static/css/style.css)) rather than duplicated per page, and is also used on the Batches list (`erp:batch_list`):

- A `<button id="display-mode-btn" onclick="enterDisplayMode()">` toggles it on; `enterDisplayMode()` adds a `display-mode` class to `<body>`. CSS rules scoped to `body.display-mode` hide `aside#sidebar`, `header.header`, `footer.footer`, `h1.h3`, and `#display-mode-btn` itself.
- Page-specific elements that should also disappear (e.g. an "Add" button) get the `hide-in-display-mode` class instead of a bespoke per-page rule.
- Exiting requires reloading the page **without** a `?display=1` query parameter — there's no explicit "Exit" button.
- `reloadPreservingDisplayMode()` (also in `script.js`) is for any page whose own polling needs to force a full reload (e.g. to resync added/removed rows, like the Batches list) without silently kicking the user out of display mode: it reloads with `?display=1` appended if display mode is currently active, and a `DOMContentLoaded` listener re-applies `enterDisplayMode()` whenever that marker is present. A plain manual reload (no marker) still exits display mode as before.

## Mobile Navigation

Below the `lg` breakpoint (991.98px), the sidebar becomes an off-canvas drawer instead of the persistent desktop sidebar. [partial-topnav.html](pyproj/device/templates/device/partial-topnav.html)'s hamburger button (`.header-toggler`) toggles a `sidebar-show` class on `#sidebar` — handled entirely by a click listener in [static/js/script.js](pyproj/static/js/script.js), not CoreUI's own `data-coreui-toggle` JS (those attributes are stripped from the button at `DOMContentLoaded` so the two mechanisms can't fight over the same click). Opening the drawer also inserts a `#sidebar-backdrop` overlay; tapping it, or the toggler again, closes the drawer.

The drawer's open/closed state is driven purely by `transform: translateX(...)` in [static/css/style.css](pyproj/static/css/style.css). CoreUI's bundled CSS has its own competing rule that hides the sidebar via `margin-left`, scoped to CoreUI's own `max-width: 767.98px` breakpoint, which only lifts when the sidebar carries CoreUI's `.show` class — a class this app's drawer never adds. `#sidebar.sidebar-fixed` therefore pins `margin-left: 0` inside the mobile media query so that CoreUI rule can't override the transform on phone-width viewports.

There is no separate mobile bottom navigation bar — the full sidebar (including staff-only items) is reached via the hamburger drawer at every screen size.

## Printable Pages

Pages that need a clean, A4-friendly printout (e.g. handing a Batch's details to production staff) follow a shared pattern rather than adding `@media print` rules to the interactive page:

- **[device/base-print.html](pyproj/device/templates/device/base-print.html)** — minimal HTML shell (no sidebar, nav, or app chrome) that print page templates extend. Loads [static/css/print.css](pyproj/static/css/print.css) and renders a `.no-print` toolbar with a *Print* button (`window.print()`) above the `{% block content %}`.
- **[static/css/print.css](pyproj/static/css/print.css)** — shared stylesheet: sets `@page { size: A4; margin: 15mm; }`, a `.print-document` wrapper, `.print-header` (heading + date on the left, logo + QR code on the right, with a bottom rule), `table.print-table`/`table.print-fields` (bordered field/data tables), and `.no-print` (hidden via `@media print`) for the toolbar.
- Each printable page gets its own minimal template (e.g. [erp/batch_print.html](pyproj/erp/templates/erp/batch_print.html)) extending `device/base-print.html`, plus a dedicated view/URL (e.g. `batch_print` at `/batches/<id>/print/`) rather than reusing the detail page's view/template — this keeps the print layout free to diverge from the interactive UI (buttons, status icons, sidebar) without fighting it via CSS overrides.
- The source page links to the print page with a print icon button (`<i class="cil-print"></i>`) opening in a new tab (`target="_blank"`) — see the Print button on [erp/batch_edit.html](pyproj/erp/templates/erp/batch_edit.html).
- Printable pages include a QR code (see below) of the *originating* page's URL (not the `/print/` URL), so a printed copy can be scanned to jump straight back to the live record — the print view builds this with `request.build_absolute_uri(reverse(...))` to the normal detail view, not `request.path`.

## QR Codes

`qrcode` (PyPI, uses Pillow — already a dependency) generates QR codes **server-side**, not via a JS library, so the generated `<img>` is plain HTML by the time a page is printed or exported to PDF — no dependency on a browser finishing a canvas render before `window.print()` fires, and it works in non-browser contexts too (future PDF export, label-printing management commands).

- **[device/qr.py](pyproj/device/qr.py)** — `generate_qr_data_uri(value, *, box_size=8, border=2)`: renders any string (a URL or other value) to a QR code PNG and returns it as a `data:image/png;base64,...` URI, ready to drop straight into an `<img src="...">` with no extra view, endpoint, or static file.
- **[device/templatetags/qr_tags.py](pyproj/device/templatetags/qr_tags.py)** — `{% load qr_tags %}` then `{{ value|qr_code }}` wraps `generate_qr_data_uri()` as a template filter; returns `''` for a falsy value.
- First use: the Batch print page (see Printable Pages above) renders a QR code of the batch's own detail-page URL in the header.

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
- **qrcode** — generates QR codes server-side (see QR Codes above), using Pillow as its image backend

## Frontend Libraries (CDN)

Loaded in `device/templates/device/base.html` for all pages:

| Library | Version | Purpose |
|---|---|---|
| CoreUI | 4.3.2 | CSS framework, layout, components |
| CoreUI Icons | 3.0.1 | Icon font (`cil-*` classes) used throughout the UI |
| Bootstrap Icons | 1.13.1 | File-type icons (`bi-*` classes) used in the asset list |
| SimpleBar | latest | Custom scrollbar for the sidebar |

Custom icons (SVG files) live in `static/img/filetypes/` and are referenced via `{% static %}` in templates.

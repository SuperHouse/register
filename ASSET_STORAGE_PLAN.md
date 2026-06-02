# Asset Storage Plan

## Question

This project needs to be able to store assets such as design files, images, text files, and other resources related to specific records including designs and devices. Without making any changes or writing any code, describe a plan for how these sorts of assets should be stored within the project (ideally not within the database) and linked to the relevant records.

## Response

### Core principle

Follow the existing `DeviceImage` pattern exactly: files live on disk under `MEDIA_ROOT`, only file path + metadata go in the database. Django's `FileField` (unlike `ImageField`) accepts any file type, so the same approach covers everything — Gerbers, PDFs, KiCad files, text logs, images.

---

### Two new models

**`DesignAsset`** — attached to a `Design` (board type / revision):
- `design` — FK to Design
- `file` — FileField, path `design_assets/{design_id}/{filename}`
- `name` — CharField (human-readable label, separate from filename)
- `description` — TextField (optional)
- `asset_type` — CharField with choices: `FUSION` (Fusion Electronics Project), `BOM` (Bill of Materials), `FIRMWARE` (Firmware Binary), `IMAGE`, `DOC` (Document), `OTHER`
- `uploaded_dt` — DateTimeField (auto-set on upload)
- `internal` — BooleanField (mirrors `DeviceEvent.internal` — hides asset from non-staff/clients)

**`DeviceAsset`** — attached to a specific `Device` instance (individual board by serial):
- `device` — FK to Device
- Same fields as above, but `asset_type` choices suit per-unit files: `TEST_REPORT`, `CERTIFICATE`, `PHOTO`, `CONFIG`, `OTHER`
- `internal` — same flag, same meaning

The existing `DeviceImage` and `TestImage` models stay as-is. Those are specialized image models with thumbnail support via `easy_thumbnails`; the new models are for arbitrary file types and don't need thumbnailing.

---

### Filesystem layout

```
MEDIA_ROOT/
  clients/              ← existing (client logos)
  test_images/          ← existing (TestImage)
  device_images/        ← existing (DeviceImage)
  design_assets/
    {design_id}/
      {filename}
  device_assets/
    {device_serial}/    ← serial number = Device PK, consistent with device_images path
      {filename}
```

---

### Access control

The same pattern the rest of the app uses:
- Non-staff users only see `DesignAsset` records for `Design` objects belonging to their associated `Client`(s).
- Non-staff users only see `DeviceAsset` records for `Device` objects belonging to their `Design`→`Client`.
- `internal=True` assets are hidden from non-staff in both views and API, exactly like `DeviceEvent.internal`.

For file serving: in dev, Django's `static.serve` handles media. In production, nginx serves `MEDIA_ROOT` directly. For truly sensitive files you could add a thin authenticated Django view that checks permissions before proxying the file response, but for most use cases the existing nginx media-serving approach is fine since URLs aren't guessable.

---

### Admin

- `DesignAssetInline` added to `Design` admin — allows staff to attach files directly from the design admin page.
- `DeviceAssetInline` added to `Device` admin — same for individual boards.

---

### API

Extend the existing API pattern:
- `POST /api/v1/design/{design_pk}/add-asset/` — multipart upload (mirrors existing `add-device-image`)
- `POST /api/v1/device/{pk}/add-asset/` — same for device assets
- `GET /api/v1/design/{design_pk}/assets/` and `GET /api/v1/device/{pk}/assets/` — list assets for a record

---

### Future scalability

`FileField` abstracts the storage backend. If you later need S3, Backblaze B2, or another object store, adding `django-storages` and changing `DEFAULT_FILE_STORAGE` in settings is sufficient — no model changes needed, and existing file paths can be migrated without touching application code.

---

### What about the `resources/` directory?

There's an untracked `resources/` directory at the project root (visible in git status). If that's meant for static reference material rather than per-record attachments, it makes sense as a separate concern — checked in to the repo for things like documentation assets, template files, or reference data used at import time. It's a different category from runtime-uploaded per-record assets and shouldn't be under `MEDIA_ROOT`.

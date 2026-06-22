# Data Export & Import

All application data — database records and uploaded media files — can be exported to a self-contained ZIP archive and imported into another installation. This is useful for backups, migrating to a new server, or seeding a test environment.

## Exporting

```bash
cd pyproj
source venv/bin/activate
python manage.py export_data [output.zip]
```

If no output path is given, the archive is written to the current directory as `register-export-YYYY-MM-DD.zip`.

The archive contains:

| File | Contents |
|---|---|
| `manifest.json` | Export timestamp, app version, record counts |
| `data.json` | All records from the `crm`, `device`, and `erp` apps |
| `media/` | All uploaded files (design assets, images, part assets, etc.) |

**User accounts are not included.** Users must be re-created on the target installation manually. Thumbnail cache files are also excluded — they regenerate automatically on first access.

## Importing

```bash
cd pyproj
source venv/bin/activate
python manage.py import_data export.zip
```

The command shows a summary from the archive manifest and asks for confirmation before making any changes. To skip the prompt (e.g. in a script):

```bash
python manage.py import_data export.zip --yes
```

!!! warning
    **The import permanently deletes all existing application data before loading the archive.** This is a clean-slate replace, not a merge. Ensure you have a backup of the target installation's data before proceeding.

The database load runs inside a single transaction: if it fails for any reason, the database rolls back to its state before the import. Media file restoration happens after the database is committed and is not transactional; if interrupted, re-running the import from the same archive will restore a consistent state.

## Permissions

If running `import_data` as a different user than the one uWSGI writes files as, you may encounter a `PermissionError` when deleting old media files. The uWSGI vassal template sets `umask = 002` so new uploads are group-writable, but files created before that setting was added may need:

```bash
sudo chmod -R g+w /path/to/MEDIA_ROOT
```

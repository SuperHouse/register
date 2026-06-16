# Testomatic Circuit Board Register

This Register provides a central location for storing production and testing 
data related to printed circuit board assembly (PCBA) services. It was 
created for storing data produced by the [Testomatic](https://github.com/superhouse/testomatic) 
PCB test jig system, but it doesn't require Testomatic to operate. You can 
use this Register independently, even without a PCB testing system at all. Its 
job is simply to store and report information about individual PCBs 
regardless of how the data is obtained.

It includes:

 * A database for storage of information relating to individual boards
 * Image storage to associate images with test records or boards
 * File asset storage to associate design files, BOMs, firmware binaries, and other documents with board designs
 * An internal web UI for managing records of boards and tests
 * An external web UI for customers to look up details of specific boards
 * An API for updating data stored in the system
 * Supporting scripts to process photos of PCBs, extract serial numbers from barcodes, and store them

Data is stored in a hierarchical manner:

**Organisations** can represent customers such as companies that have 
purchased or commissioned the assembly of boards.

**Users** have access to the system through a username and password, and 
are associated with one or more organisations.

**Designs** represent a type of circuit board, and are associated with an 
organisation. Design files, BOMs, firmware binaries, and other assets can 
be attached directly to a design for easy reference.

**Boards** represent individual circuit boards with a serial number 
assigned, which are an embodiment of a design.

![](images/register-device-details.png)

It's written as a Django + React application and can use either SQLite 
or MariaDB / MySQL.

## Data Export and Import

All application data (database records and uploaded media files) can be exported
to a self-contained ZIP archive and imported into another installation.

### Exporting

```bash
cd pyproj
python manage.py export_data [output.zip]
```

If no output path is given, the archive is written to the current directory as
`register-export-YYYY-MM-DD.zip`.

The archive contains:
- `manifest.json` — export timestamp, app version, record count
- `data.json` — all records from the `crm`, `device`, and `erp` apps
- `media/` — all uploaded files (design assets, device assets, images, etc.)

User accounts are **not** included; users must be re-created on the target
installation manually. Thumbnail cache files are also excluded — they regenerate
on first access.

### Importing

```bash
cd pyproj
python manage.py import_data export.zip
```

The command shows details from the archive and asks for confirmation before
making any changes. To skip the prompt (e.g. in a script), pass `--yes`:

```bash
python manage.py import_data export.zip --yes
```

**The import permanently deletes all existing application data before loading
the archive.** This is a clean-slate replace, not a merge. Make sure you have
your own export or backup before running this on an installation with data you
want to keep.

The import is database-transactional: if loading the records fails for any
reason, the database is rolled back to its state before the import started.
Media file restoration happens after the database is committed and is not
transactional; if it is interrupted, re-running the import from the same
archive will restore a consistent state.

## License

Copyright (C) 2026 SuperHouse Automation Pty Ltd

This program is free software: you can redistribute it and/or modify it under the terms of the [GNU Affero General Public License](LICENSE) as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

Because this software is licensed under the AGPL, if you run a modified version as a network service, you must make the corresponding source code available to users of that service. The source code for this project is available at [https://github.com/SuperHouse/register](https://github.com/SuperHouse/register).
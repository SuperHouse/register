# Designs

A Design represents a type of circuit board — a specific SKU and hardware version belonging to an Organisation.

## Design list

The Designs page (`/design/`) lists all designs with their organisation, SKU, hardware version, and a thumbnail of the PCB top view. Use the search box to filter by name, SKU, or organisation.

## Design detail

The design detail page shows:

- A banner with the **PCB top and bottom view images** (if uploaded), side by side
- A **Design Files** table listing the eight core asset types
- An **Attachments** section for additional files

### Design Files

Each design can have one file of each core type. Uploading a new file of the same type automatically replaces the previous one.

| Type | Description |
|---|---|
| PCB 3D View | 3D render of the assembled board |
| PCB Top View | Top-side image |
| PCB Bottom View | Bottom-side image |
| CAD Project | The CAD tool's own project file: a `.f3z` from Autodesk Fusion, or a `.zip` of a KiCAD project folder. Shown as "Fusion Electronics Project" or "KiCAD Project" to match the design's CAD Tool |
| Schematic Design File | Schematic source file |
| PCB Design File | PCB layout source file |
| Bill of Materials | BOM in any format |
| Firmware Binary | Compiled firmware image |

Staff can upload, replace, and delete design files from the detail page. Non-staff users see only rows where a file exists, and only non-internal files.

### Changing CAD tool

Register knows which CAD tool a design uses from its CAD Project file, so there is nothing to set. If a design moves to another tool, upload the new project file in the CAD Project row. It replaces the old project file, and its extracted files replace the old extracted files.

### Autodesk Fusion auto-extraction

When a `.f3z` file is uploaded as the CAD Project, the system automatically extracts and stores:

- Bill of Materials (`.csv`)
- PCB Design File (`.brd`)
- Schematic (`.sch`)
- PCB Top View render (3D image)
- PCB Bottom View render (3D image)
- PCB 3D View thumbnail

This means uploading a single `.f3z` file can populate most of the Design Files table automatically.

### KiCAD auto-extraction

KiCAD keeps a project in several files, so upload the project as one `.zip`:

1. In Finder (or your file manager), find the folder that holds the `.kicad_pro` file.
2. Compress that folder into a `.zip`. Include any project-specific symbol and footprint libraries in it. KiCad's `-backups` folder can stay in, because Register ignores it.
3. In the CAD Project row of the Design Files table, upload the `.zip`.

The system then extracts and stores:

- PCB Design File (`.kicad_pcb`)
- Schematic (the root `.kicad_sch`; any sub-sheets stay in the uploaded `.zip`)
- Bill of Materials (`.csv`, one row per part, in the same columns as a Fusion BOM)
- PCB Top View and PCB Bottom View renders
- PCB 3D View (an angled render)

Parts whose footprints have no 3D model appear in the renders as bare pads.

The project must be from KiCad 6 or later. To use a KiCad 5 project, open it in a newer KiCad and save it first. A `.zip` must hold exactly one KiCAD project. If it holds none, Register stores the file without extracting anything.

### Attachments

Arbitrary files (extra firmware images, inspection photos, notes PDFs, etc.) can be added in the Attachments section. These don't replace each other — any number can be attached.

When selecting a file to attach, the Name field is auto-populated from the filename. A `.f3z` uploaded as an attachment is stored as-is and is not extracted; upload it in the CAD Project row of the Design Files table instead.

### Boards for this design

The design detail page also lists all boards registered against this design, with their serial numbers, creation dates, and test results.

### Production batches

Staff can start a new production batch for a design using the **Add New Batch** button. See [Production Batches](batches.md).

### Test Suite

The **Test Suite** tab lists the Test Steps and Manual Checks a tester system runs against boards
of this design. See [Test Suites](test-suites.md).

## Creating and editing designs

Staff can create and edit designs from the Designs list page. Each design requires a name, SKU, hardware version, and an associated organisation.

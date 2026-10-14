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
| CAD Project | The CAD tool's own project file, e.g. a `.f3z` from Autodesk Fusion. Shown as "Fusion Electronics Project" when the design's CAD Tool is Autodesk Fusion |
| Schematic Design File | Schematic source file |
| PCB Design File | PCB layout source file |
| Bill of Materials | BOM in any format |
| Firmware Binary | Compiled firmware image |

Staff can upload, replace, and delete design files from the detail page. Non-staff users see only rows where a file exists, and only non-internal files.

### CAD Tool

Each design records the **CAD Tool** it is drawn in, in the design details card. Only Autodesk Fusion is supported at the moment; KiCAD support is planned. Leave it blank if you don't know.

You don't normally need to set it by hand. Uploading a project file for a design with no CAD Tool sets it automatically. A design uses one CAD tool, so Register refuses a project file from a different tool than the one recorded. If a design really has moved to another tool, change its CAD Tool first, then upload.

### Autodesk Fusion auto-extraction

When a `.f3z` file is uploaded as the CAD Project, the system automatically extracts and stores:

- Bill of Materials (`.csv`)
- PCB Design File (`.brd`)
- Schematic (`.sch`)
- PCB Top View render (3D image)
- PCB Bottom View render (3D image)
- PCB 3D View thumbnail

This means uploading a single `.f3z` file can populate most of the Design Files table automatically.

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

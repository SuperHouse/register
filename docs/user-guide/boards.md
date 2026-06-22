# Boards

Boards (internally called Devices) represent individual PCBs, each identified by a unique serial number.

## Board list

The Boards page (`/device/`) lists all boards with their design, creation date, and most recent test result. Use the search box to filter by serial number, design name, or notes. The list paginates automatically.

Non-staff users see only boards belonging to their organisation.

## Board detail

Click a serial number to open the board detail page. It shows:

- **Design** — which board type this is
- **Creation date** — when the board was registered
- **Invoice / PO** — optional purchase order reference
- **Notes** — free-text notes on the board

### Test records

Each test run is shown chronologically. Results are colour-coded:

| Result | Meaning |
|---|---|
| `NEW` | Test started; result not yet recorded |
| `PASS` | Board passed all tests |
| `FAIL` | Board failed one or more tests |
| `HUH?` | Inconclusive result |

Test images (photos taken during testing) are shown under each test record.

### Events

Events record significant moments in a board's life. Types include:

- **Note** — a free-text note
- **Software version** — firmware programmed onto the board
- **Shipping** — the board was shipped

Staff users can see internal events (marked with a lock icon). Non-staff users see only non-internal events.

### Images

Photos of the board (not tied to a specific test run) appear in the Images section. Staff can upload new images directly from this page.

### Attachments

Files attached specifically to this board (data logs, custom reports, etc.) appear in the Attachments section. Staff can upload, rename, and delete attachments.

## Adding a board

Boards are typically created via the [API](../api/reference.md) by automated test equipment or programming jigs. Staff can also create them manually via the admin interface at `/office/`.

## Board serial numbers

Each board's primary key is its hardware serial number (an integer). This is the number stored in the barcode or programmed into the device by manufacturing equipment.

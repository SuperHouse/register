# Parts Library

The Parts library stores a catalogue of electronic components used in your designs. For each part you can record sourcing information, price breaks, possible substitutions, and datasheets.

## Parts list

The Parts page (`/parts/`) groups parts by category. Use the search box to filter across name, value, package, and device fields. A **Populate from BOM** button lets you import parts from a BOM CSV file.

## Part detail

Click a part name to open its detail/edit page. Each part has:

- **Name** — a human-readable label (e.g. "10k 0402 Resistor")
- **Device** — component identifier from the schematic tool
- **Package** — footprint (e.g. `0402`, `SOT-23`)
- **Value** — component value (e.g. `10k`, `100nF`)
- **Category** — optional hierarchical category
- **Description** — free-text description
- **Fusion Library** — the Fusion Electronics library this part came from
- **Image** — product photo (can be auto-populated from supplier lookups)

## Sources

Each part can have multiple supplier sources. A source records:

- Supplier name, supplier SKU, manufacturer SKU
- Packaging type (e.g. Tape & Reel, Cut Tape)
- Stock level
- URL

### Automatic lookup

The **Supplier SKU** field has fetch buttons for supported suppliers:

| Button | Supplier |
|---|---|
| LCSC | LCSC (no API key needed) |
| DK | DigiKey (requires OAuth setup — see [Supplier API Setup](../admin/supplier-apis.md)) |
| Mouser | Mouser (requires API key) |
| E14 | Element14 / Farnell / Newark (requires API key) |

Enter a supplier SKU and click the appropriate button to auto-populate the source fields. If a source doesn't yet exist for that SKU, it will be created automatically; if a product image doesn't exist yet for the part, one will be saved from the supplier.

The **refresh** button (↻) on an existing source re-fetches all fields from the supplier to update stock and pricing.

### Price breaks

When a source is fetched or refreshed from a supported supplier, quantity-based price breaks are stored automatically. The **Price** column in the sources table shows the price at the lowest quantity. Hover over it to see the full price ladder (all quantity/price tiers).

## Possible Substitutions

The **Possible Substitutions** card lists other parts that can be used in place of this one (e.g. a higher-tolerance resistor substituting for a lower-tolerance but otherwise equivalent part). Click a substitution's name to navigate directly to that part.

To add a substitution, select the replacement part from the dropdown and click **Add**.

## Attachments

Files such as datasheets, application notes, and specifications can be attached to a part. The Name field is auto-populated from the selected filename.

## BOM import

The **Populate from BOM** button on the Parts list page accepts a CSV file exported from Autodesk Fusion Electronics. The columns expected are `reference`, `device`, `package`, `value`, and `library`.

For each row the importer:

1. Checks **Exclusion Rules** — rows matching any rule are skipped entirely
2. Applies **Transformation Rules** — remaps library/device/package/value tuples before the duplicate check
3. Applies **Library Settings** — blanks out specified fields for rows from a given library
4. Checks for a duplicate part (matching device, package, and value) — if found, skips the row
5. Creates a new part if none of the above caused a skip

Counts of added, skipped, and excluded rows are shown after the import.

### BOM import rules

Import rules are configured under **Settings → Part Import Filters**:

- **Exclusion Rules** — skip rows entirely (e.g. skip all mounting holes from the `hardware` library)
- **Transformation Rules** — remap a tuple to a canonical equivalent before duplicate detection (e.g. map a generic resistor device name to a standard one)
- **Library Settings** — ignore specified fields (device, package, or value) for rows from a particular library

## Categories

Parts can be organised into a hierarchical category tree (e.g. Passives → Resistors → SMD). Categories are managed under **Settings → Part Categories**.

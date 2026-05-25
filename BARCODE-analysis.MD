# Barcode Scheme Analysis

Review of the ideas in BARCODES.md, with problems identified and industry best practices recommended.

---

## What's Good

**Prefix-per-type scheme** is the right instinct. Every major barcode-driven system (GS1, most WMS platforms) uses structured identifiers so a scanner can immediately know what it's looking at without ambiguous context.

**Command/action barcodes** (`Cxxxx`) are a well-established pattern in warehouse management — scanners in a pick-and-pack station often have a laminated card of "function barcodes" to switch modes without touching a keyboard. This is worth keeping.

**License plating for reels/bags** (the `Gxxxx` roll-of-stickers idea, stored as an attribute rather than PK) is exactly the right approach. Physical labels get damaged and replaced; the label is a pointer to the record, not the identity of it.

---

## Problems to Fix

**1. Raw numbers for board serials is an antipattern.**
The document says board serial numbers have no prefix. This means a scanner cannot distinguish `12345` (a board) from `12345` (anything else — a stray label, a supplier barcode, a typo). Every type should have a prefix, including boards. The `S` prefix is right there in the proposed list — just make it mandatory.

**2. Using database PKs as the barcode number is fragile.**
`Device.pk` is the current serial number. If you encode that as `S1042`, that works — but it exposes record counts, is guessable, and creates a hard coupling between the barcode and the database row. Better practice is a separate, stable `barcode` or `serial_number` field that you control independently. This also matters for the ERP extension: part records deleted and recreated shouldn't reuse IDs that are already printed on labels in the field.

**3. No check digit mentioned.**
1D barcodes (Code 128, Code 39) can be misread. A single transposed digit on a board serial is a production defect you won't catch until it causes a problem downstream. GS1 mandates check digits on all their identifiers. At minimum, apply a Luhn check or similar to the numeric suffix. Many barcode generators do this automatically if you choose the right symbology.

**4. The O/0 ambiguity problem.**
`Oxxxx` for Organisation — in most barcode fonts and on printed labels, `O` and `0` are indistinguishable without careful font selection. If you use Code 39 the character set is limited; if you use Code 128 you have the full ASCII range, but humans reading labels will still confuse them. Consider `X` for Organisation, or better, use a two-letter prefix scheme to give yourself more namespace and sidestep single-character ambiguity entirely (e.g. `SN`, `DS`, `OR`, `LC`, `BT`, `US`, `CM`, `PT`, `GP`).

**5. `Bxxxx` for batch collides conceptually with `Bin` in location contexts.**
If you later add bin locations within a shelf (standard in WMS), `B` is already taken. Location hierarchies typically need: building → room → shelf → bay → bin. Plan for that.

---

## Industry Best Practice Recommendations

**GS1 Application Identifiers (AIs) — worth understanding even if you don't adopt them fully.**
GS1 is the global standard used by virtually every supply chain. Their key insight is encoding multiple data fields in a single barcode using `(AI)value` pairs:
- `(01)` = GTIN (product type)
- `(10)` = Batch/lot number
- `(21)` = Serial number
- `(30)` = Quantity

If any of your clients are large enough to require GS1-compliant labels on shipped boards, you'll need a GS1 Company Prefix (purchased from GS1). Designing with this in mind now avoids painful migrations. Even if you don't go full GS1, borrowing the concept of structured field identifiers within a single barcode is useful.

**Barcode symbology: 1D vs 2D.**
The document doesn't specify which barcode format to use. Recommendations by use case:

| Use case | Recommended symbology |
|---|---|
| Board serial on PCB | **DataMatrix** — very small, excellent error correction, standard for direct part marking (IPC/EIA use it), can survive harsh environments |
| Reel/bag/bin labels | **Code 128** — compact, alphanumeric, readable by almost every scanner |
| Component reels (supplier labels) | Already have barcodes — scan and map to internal records rather than relabeling |
| Command/action cards | **QR or Code 128** — easily printable |

For PCB manufacturing specifically, **DataMatrix** is the dominant format for board-level marking. If Testomatic ever marks boards directly (laser etching, inkjet), DataMatrix is the default choice.

**Capture supplier barcodes, don't replace them.**
Component reels from LCSC, Digi-Key, Mouser etc. already carry barcodes (often EIA-3007 or a vendor-specific format). Rather than replacing these with `Gxxxx` stickers, the better workflow is: scan the supplier barcode to create a reel record, then optionally add a `Gxxxx` license-plate sticker for internal use. This lets you trace a component back to its exact supplier order and lot.

**Separate "part number" (type) from "lot" from "physical unit".**
The `P` / `G` split hints at this but it maps better to the standard three-level ERP model:
- **Part** (`Pxxxx`) — the component type (e.g. "0402 10kΩ 1% resistor, LCSC C25900")
- **Lot/Batch** (`Bxxxx`) — a specific incoming delivery of that part (ties to purchase order, has quantity, supplier lot number)
- **Physical unit** (`Gxxxx`) — a specific reel, bag, or cut tape from that lot (has remaining quantity, physical location)

This three-level structure is how every serious ERP (SAP, NetSuite, Odoo) models it, and it directly supports traceability: "which boards were built using parts from the suspect lot?"

**Workflow barcodes need visual differentiation.**
Operationally, if a `Cxxxx` command barcode looks identical to a `Sxxxx` serial barcode, operators will accidentally scan the wrong one. Industry practice is to print command barcodes on distinctly coloured card stock (red for destructive operations, yellow for mode changes) with large human-readable text. This is a UX consideration, not just a schema one.

---

## Summary: Concrete Changes to Make

1. **Require a prefix for all types** — including boards (`S` is fine), no raw numbers
2. **Store barcodes as separate fields**, not derived from database PKs
3. **Add check digits** to catch scan errors
4. **Consider a two-letter prefix scheme** to avoid O/0 ambiguity and give room to grow
5. **Adopt the three-level Part → Lot → Physical Unit model** for component tracking
6. **Plan to capture supplier barcodes** and map them to internal records rather than relabeling
7. **Choose DataMatrix for board marking**, Code 128 for shelf/bin/reel labels

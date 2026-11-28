# Identifiers Plan

**Status: agreed, not built (2026-11-28).** Only part references are still open, and they are
deferred. Build order step 1 is next. This plan sets one scheme for the identifiers
that people read, type, say and scan, for every kind of record in Register. It replaces the open
questions in [BARCODES.md](BARCODES.md) and [BARCODE-analysis.MD](BARCODE-analysis.MD), and it
decides the "separate serial field" question in [DEVICE_GENERATION_PLAN.md](DEVICE_GENERATION_PLAN.md):
there is no separate field, and the serial stays the `pk`.
Projects (register#159) are the first new user: they need a code that does not leak the total
number of projects to a client.

## What needs an identifier

| Thing             | Physical label?               | Client sees it? | Identifier today                                   |
|-------------------|-------------------------------|-----------------|----------------------------------------------------|
| Board (`Device`)  | Yes: QR and Code 128 sticker  | Yes             | `pk`, one global sequence, 1 to 7488 (local copy)  |
| Batch             | Printed docket                | Yes (#95)       | `#pk`, one global sequence                         |
| Project           | No                            | Yes             | `P-YYYY-NNN`, one global sequence per year         |
| Design            | Silkscreen (SKU, version)     | Yes             | SKU + hardware version, chosen by a person         |
| Organisation      | No                            | Own name only   | `pk`, not shown                                    |
| Part              | Later: bin labels             | No              | `pk`                                               |
| Reel, bag, tape   | Later: licence-plate sticker  | No              | Does not exist yet                                 |
| Location          | Later: shelf and bin labels   | No              | `pk`                                               |
| Tester, module    | Later: asset labels           | No              | `pk`                                               |
| Command card      | Later: printed card           | No              | Does not exist yet                                 |
| Parts order       | Supplier's label              | No              | The supplier's order number                        |

## Three different things, which BARCODES.md mixes together

1. **Record key.** The database `pk`. Register uses it in URLs and foreign keys. Nobody needs to
   read it.
2. **Reference.** The text that a person reads, types, says on the phone, or puts in an email or
   a file name. Each kind of record has its own form of reference.
3. **Scan payload.** The data in a barcode or QR code. This can be different from the reference.
   Boards already show this: the QR code holds `https://d.superlab.au/7488`, but a person reads
   `7488`.

When these three are kept apart, most of the concerns in BARCODE-analysis.MD go away:

- **Type of a scanned code.** The scan payload carries the type, so the reference does not need
  a prefix for that reason alone. PhotoBox and `find_barcodes.py` already reject any QR code that
  does not start with a known host. That check stops false reads from the other codes on a board.
- **Check digits.** QR, Data Matrix and Code 128 all have error detection built in. Code 128 has
  a mandatory mod-103 check character. A separate Luhn digit only helps with references that
  people type, and the lookup catches most typing errors because an unknown reference finds no
  record.
- **O and 0.** Use letters only in letter positions and digits only in digit positions. Then a
  reader can tell from the position which character it is.

## The leak

A reference numbered from one counter for all clients tells each client how much work there is
in total. `P-2026-014` says "at least 14 projects this year". Batch `#301` and board `7488` do the
same thing for batches and boards. Using the organisation `pk` instead (`P-2026-11-1`) leaks the
number of organisations, and it looks like a date.

## Proposal

### Rule 1: the `pk` is never a reference for a new kind of record

Each new kind of record that needs a reference gets its own stored `ref` field. Register sets it
when it creates the record, and it never changes after that. A change to the scheme later does
not change any reference that is already printed or written down.

**Boards are the exception: the serial stays the `pk`.** Board serials are printed on about
7,500 boards, and the serial is the `pk`. No separate serial field is needed (Jon, 2026-11-28).
The reasons for a separate field in BARCODE-analysis.MD are a prefix, a check digit and a hidden
count, and this plan does not want any of them for boards. When "Generate Devices" makes serials
in Register, check that the database's auto-increment counter is above the highest serial in
use. SQLite and MySQL do this by themselves. Postgres needs its sequence reset once, after
imports that set the `pk` directly (see DEVICE_GENERATION_PLAN.md).
This is a short-term risk. The spreadsheet is being phased out, so in the end every serial will
come from the `pk`.

A possible future need, not planned (Jon, 2026-11-28): T-Rex gives boards their own serials after
they receive them and build them into a larger system. It may become useful to store that
client serial in Register. If it does, it is an extra field for the client's number. It does not
replace the `pk` as the SuperHouse serial. This applies to one client only, so nothing is built
for it now.

### Rule 2: what a reference looks like depends on who sees it

- **Client work (Project, Batch, and later Quote):** `<client code>-<type letter><number>`,
  numbered separately for each client. For example, the first Centreline project is `CLA-P001`
  and its third batch is `CLA-B003`.
  - The client code is the client's one abbreviation, for use everywhere: Register, stencil
    labels, file names. It is exactly 3 capital letters, unique, and set by staff on the
    Organisation edit page. Register asks for one before the first project or batch of that
    client. Jon's examples (2026-11-26): `VRP` Vending Repairs, `TRX` T-Rex, `CLA` Centreline
    Automation, `BBP` Bubblepay, `SHA` SuperHouse Automation. These replace the earlier ad-hoc
    abbreviations, such as `V-Rep` on stencil labels.
  - The number has at least 3 digits and continues past 999. It has no year, so it does not look
    like a date and does not start again each year.
  - A client sees only its own count, which it knows already.
  - The reference is stored, so a later change to a client code does not change old references.
- **Boards:** the serial stays a number from one global sequence. Code 128 and QR labels stay as
  they are.
- **Physical assets (testers, test modules, stencils, reels, jigs, tools):** one generic asset
  tag, `AS-<number>`, for example `AS-0042`. The tag does not tell the type. Register holds a
  list of asset categories, and each asset has one. A wrong category is corrected in Register,
  with no new label.
  - The tag is an attribute of the record, not its `pk` (the "licence plate" idea in
    BARCODES.md).
  - Jon prints labels with a Brother label printer that numbers them automatically, the same way
    as board labels. So Register must **accept a tag number from a scan**, not only make one. A
    likely first use: print 20 or 50 tags, stick them on things, then scan each one to add it.
    Tags are unique, so a second scan of the same number is refused.
  - Testers and test modules already have their own tables. They keep those tables and get an
    asset tag field. Things with no table yet (stencils, reels) start as rows in a general asset
    list with a category.
- **Other internal records:** a two-letter prefix only where it is useful:
  - `CM-` for command cards. These are fixed actions, not records, so a scanner must act on them
    with no lookup.
  - Part bin labels name a part type, not one physical item, so they carry the part's own
    reference, not an asset tag. The form of that reference is not decided.
  - `LC-` for locations (see Decision 4).

  Two-letter internal prefixes and three-letter client codes can never be the same text.

### Rule 3: one scan payload form for everything

The board short link already exists: `/<number>/` redirects to the board (`device_detail_short`
in `conf/urls.py`). Extend the same path to every reference:

- Digits only: a board serial. This is how it works now.
- `<three letters>-<letter><digits>`, for example `CLA-P001`: client work. The letter tells the
  type.
- `<two letters>-<digits>`, for example `AS-0042`: an internal record. The prefix tells which
  table to look in.

The three forms cannot be confused, so one resolver can handle them all. A QR code holds
`https://d.superlab.au/<reference>`. A phone camera opens the record, and a scanner app gets the
type from the record it finds. A Code 128 label holds the plain reference. Normal access rules
apply: a client who scans another client's reference gets a 404.

## Decisions

1. **Board serials: decided (Jon, 2026-11-26).** Keep the one global sequence. A serial can show
   roughly how many boards SuperHouse has built, and that is acceptable. The serial stays the
   `pk`, with no separate field (Jon, 2026-11-28).
2. **Batches: decided (Jon, 2026-11-26).** Change to the `CLA-B003` form, as separate work after
   projects. Existing batches get references in creation order for each client. The old `#pk`
   stays searchable, so that old dockets still lead to the right batch.
3. **Client codes: decided (Jon, 2026-11-26 and 2026-11-28).** One consistent abbreviation for
   each client, used in every context. It is always exactly 3 capital letters. It replaces the
   ad-hoc abbreviations.
4. **Asset tags and locations: decided (Jon, 2026-11-26 and 2026-11-28).** Generic `AS-` tags with
   a category in Register, not one prefix for each type. A prefix is only worth having if it
   tells you something useful. Printing is not a factor: the Brother app prints any prefix just
   as easily. **Locations get their own prefix, `LC-`** (for example `LC-0104`). A location is a
   more abstract thing than an asset: an asset is a distinct physical object, and it *has* a
   location.
5. **Planning stack item #4: lost (Jon, 2026-11-28).** Nobody can remember what it was, and no
   record of it was found. [PLANNING_STACK.md](PLANNING_STACK.md) now says so.

## Still to discuss

- The form of a part's reference, for part bin labels. Deferred (Jon, 2026-11-28): not needed
  yet.

## Build order

1. `Org.code` (client code), and `Project.ref` in the `CLA-P001` form. This replaces `P-YYYY-NNN`.
   No projects are in production yet, so nothing needs renumbering there.
2. The short-link resolver in `conf/urls.py`, extended to project references.
3. Batch references (Decision 2).
4. Asset categories with `AS-` tags, and `LC-` location labels, when a feature first needs them.

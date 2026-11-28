# Device Generation / Serial Number Plan

**Status: parked.** Surfaced as a side-issue while refining
[BATCH_STATUS_PLAN.md](BATCH_STATUS_PLAN.md) — specifically, the open question of whether a
`Device` should be linkable to a `DRAFT` batch led to the bigger question of how `Device`s (and
their serial numbers) get created at all. Discussing this then surfaced a further piece of work
the user wants to complete first, before returning here. See [PLANNING_STACK.md](PLANNING_STACK.md)
for the full chain and where to resume.

## Question

Register currently only creates `Device` records via spreadsheet import. The user wants to remove
the external spreadsheet entirely and create serial numbers from within Register instead — e.g. a
"Generate Devices" button on the Batch interface. Consider how this fits into the current
planning (register#129 stock consumption, and the batch status plan above).

## Response

### What exists today

`Device.pk` is a plain Django `BigAutoField` ([device/models.py:126](pyproj/device/models.py#L126))
— not a custom serial field. **Every existing path that creates a `Device` requires the caller to
already know the serial**: `import-xlsx` ([import-xlsx.py:154](pyproj/device/management/commands/import-xlsx.py#L154))
and the `device/add/` API ([device/api.py:98](pyproj/device/api.py#L98)) both explicitly pass
`pk=<serial from the caller>`. `Device.first_free_serial()` exists but is only ever used by test
fixtures — nothing in production code mints a new serial today. So "Generate Devices" is genuinely
new ground, not a refactor of something that half-exists.

### This directly intersects prior art already in the repo

[BARCODES.md](BARCODES.md) and [BARCODE-analysis.MD](BARCODE-analysis.MD) are already in this
repo, and the analysis doc's point #2 is exactly on point:

> **Using database PKs as the barcode number is fragile.** `Device.pk` is the current serial
> number... Better practice is a separate, stable `barcode`/`serial_number` field that you control
> independently.

That critique was written as forward-looking advice while `pk`-as-serial was a quiet side-effect of
spreadsheet import. It stops being a minor note the moment Register itself starts minting serials
on demand via a button — that's the point where this stops being "fix eventually" and becomes
"about to be baked in further, or fixed now." This is a real fork, not a detail:

- **Keep `pk == serial`** — simplest, zero migration. "Generate Devices" is just
  `Device.objects.create(design=batch.design, batch=batch)` × N, Django hands out sequential
  serials for free. Keeps the existing antipattern (no prefix, no check digit, exposes row counts,
  couples the barcode to the DB row).
- **Add a separate `serial_number` field now**, decoupled from `pk`, per the analysis doc's
  recommendation — lets a structured scheme (prefix, check digit, DataMatrix-friendly) be adopted
  later without ever renumbering anything already printed on a board. Real cost: a migration, and
  touching every place that currently treats `pk` as "the serial."

**Resolved 2026-11-28 (see [IDENTIFIERS_PLAN.md](IDENTIFIERS_PLAN.md)): keep `pk == serial`.**
Jon decided board serials stay one global number, with no prefix and no separate field. The
sequence check under "Sequence/pk collision risk" below still applies.

**Original note — this is a decision about the physical labeling process, not something inferable
from the code.** Lean recorded above (favour the separate field, given this feature is about to
make serial-minting routine rather than a one-off import artifact), but it's the user's call.

### How it resolves the open question from the batch status plan

*Should a `Device` be linkable to a `DRAFT` batch?* Answered by this: "Generate Devices" is the
concrete action that needs gating, so the rule falls out cleanly — only enabled once
`batch.status` is `READY` or `IN_PROGRESS` (nothing committed yet in `DRAFT`; nothing left to
generate once `COMPLETE`/`CANCELLED`).

### How it reshapes the stock-consumption plan (register#129) — the bigger one

[STOCK_CONSUMPTION_PLAN.md](STOCK_CONSUMPTION_PLAN.md) deliberately deferred per-`Device`
consumption, reasoning that `Device` creation happens through too many disconnected paths to wire
up for a v1. **That reasoning weakens once "Generate Devices" exists as the one intended in-app
path going forward.** Rather than building two disconnected actions (a bare-quantity "Consume
Stock" button, and a separate "Generate Devices" button), they should probably be *the same
action* — generating N devices for a batch is the literal, physical event the issue describes
("attached to a Device as part of the assembly process"), so it's the natural place to decrement
`PartAllocation`/`Part.stock` in the same transaction.

**Done (2026-10-13):** `STOCK_CONSUMPTION_PLAN.md` has been amended to adopt this. Its Workflow
step 4 defines `_consume_batch_stock(batch, units)`, which the Generate Devices view calls inside
its own `transaction.atomic()` after creating the Device rows. Its "Consume Stock" button is now
marked superseded. That plan also lists the open questions this creates (deleting a generated
Device, Devices created by other paths). When building Generate Devices, build that call in
alongside it.

### Design questions specific to "Generate Devices"

- **Pre-allocate-ahead-of-build vs. confirm-after-build.** Does clicking the button mean "mint N
  serials now so labels can be printed before assembly," or "record that N boards have just been
  physically completed"? These push `creation_dt` and stock-consumption timing in different
  directions — `creation_dt` is documented as the real assembly date (`import-xlsx` skips a row
  entirely if `Assembled` is blank), so stamping it at generation time is only correct under the
  second reading. Default recommendation: the second (generation = confirmation of build,
  `creation_dt = now()`, stock consumed in the same transaction) — simpler single-step flow,
  matches the issue's wording. Revisit if boards genuinely need a serial label attached *before*
  physical assembly in this shop's actual process. **Stock consumption depends on this answer**:
  `STOCK_CONSUMPTION_PLAN.md` consumes stock at generation time on the assumption that it means
  "just built". If the answer flips, consumption needs a separate "mark built" event instead.
- **Quantity**: default to `batch.quantity` minus however many `Device`s already exist for the
  batch, but don't hard-block generating more — over-building for scrap replacement happens.
- **Sequence/pk collision risk**: if the production DB is Postgres, its auto-increment sequence
  does **not** auto-advance when `import-xlsx` inserts an explicit `pk=` — years of spreadsheet
  imports may have left the sequence counter well behind the highest serial actually in use.
  Letting Django auto-assign a pk for the first "Generate Devices" click without checking this
  first risks silently colliding with an already-printed serial. (SQLite's `INTEGER PRIMARY KEY`
  recomputes `max(rowid)+1` on every insert and is self-healing here — this risk is backend-
  specific.) Cheap to verify (advance the sequence to the current max) before this ships, wherever
  it's deployed.
- **Coexistence with `import-xlsx`**: no forced migration needed — both paths write the same
  `Device` model, so spreadsheet import can keep working for as long as it's still needed while
  new batches move to "Generate Devices," as long as the sequence check above is sound.

### Suggested build order across all three plans

**Batch status → Device generation → stock consumption wired to generation** (rather than stock
consumption's own standalone "Consume Stock" button). Batch status gates Device generation; Device
generation becomes the chokepoint stock consumption needed all along.

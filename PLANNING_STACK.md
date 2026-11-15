# Planning Stack

A running record of the plan docs spawned from register#129, in the order they were discovered —
each one surfaced while drilling into the one before it. Kept separate from the plans themselves
so there's one place to see the whole chain and which end to resume from.

**To resume work: start from the bottom (most recently discovered, most blocking) and work
upward.** Each plan is parked until the one below it in this list is resolved.

| # | Plan | Discovered while... | Status |
|---|---|---|---|
| 1 | [STOCK_CONSUMPTION_PLAN.md](STOCK_CONSUMPTION_PLAN.md) — register#129, stock consumption/allocation | the original ask | Parked — blocked by #2 |
| 2 | [BATCH_STATUS_PLAN.md](BATCH_STATUS_PLAN.md) — `Batch.status` (Draft/Ready/In Progress/Complete/On Hold/Cancelled) | designing #1's "batch cancelled → release allocations" step and finding `Batch` has no status field | Parked — blocked by #3 |
| 3 | [DEVICE_GENERATION_PLAN.md](DEVICE_GENERATION_PLAN.md) — in-app Device/serial-number generation, replacing spreadsheet import | refining #2's "should a Device be linkable to a Draft batch" question | Parked — blocked by #4 |
| 4 | *(not yet named)* | refining #3 — the user identified another piece of work to complete first | **Awaiting description — resume here** |

**Amended 2026-10-13:** decisions reached further down the chain (#2 and #3) have been folded back
into #1, so `STOCK_CONSUMPTION_PLAN.md`'s body now describes the current design rather than its
first draft. In short: stock is reserved on release from Draft, released on cancel, and consumed
inside "Generate Devices" (no separate "Consume Stock" button). Its open questions are listed in
that file.

## Why this order, working backwards

- #4 blocks #3 because the user wants it done before returning to Device Generation.
- #3 blocks #2 in practice (not strictly — #2 could ship alone) but #3's answer to "can a Device
  attach to a Draft batch" and its reshaping of #1's stock-consumption trigger make more sense
  once #2 exists, so finishing #2 before #3 avoids rework.
- #2 blocks #1 because #1's "batch cancelled" workflow step was written assuming a real
  `Batch.status` exists.

## Convention

Each plan file uses the `<NAME>_PLAN.md` naming already established by
[ASSET_STORAGE_PLAN.md](ASSET_STORAGE_PLAN.md), with a **Status** line at the top stating whether
it's parked (and on what) or active, and a pointer back to this file. When a plan is actually
implemented, update its Status line to say so (and update this table) rather than deleting the
file — same "keep as a historical record" convention `ASSET_STORAGE_PLAN.md` already set.

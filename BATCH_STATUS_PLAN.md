# Batch Status Plan

**Status: parked.** Surfaced as a side-issue while planning [STOCK_CONSUMPTION_PLAN.md](STOCK_CONSUMPTION_PLAN.md)
(register#129) — that plan's "batch cancelled" step needed a real status to key off, and `Batch`
didn't have one. Refining this plan then surfaced its own side-issue —
[DEVICE_GENERATION_PLAN.md](DEVICE_GENERATION_PLAN.md) (device/serial-number creation) — which in
turn surfaced a further piece of work the user wants to complete first. See
[PLANNING_STACK.md](PLANNING_STACK.md) for the full chain and where to resume.

## Question

register#129 planning revealed that `Batch` has no overall status field — only
`BatchProductionStage`'s per-stage statuses, from which `Batch.progress_category` derives a
New/In Progress/Complete grouping for the Batches list. Suggest a structure for a real `Batch`
status, including whether a pre-release "Draft"/"Pending" state belongs at the front of it.

## Response

### What exists today

`Batch.progress_category` ([erp/models.py:82](pyproj/erp/models.py#L82)) is a **computed, not
stored** property — "complete" if every `BatchProductionStage` is `DONE`, "new" if every stage is
`NOT_STARTED`, "in_progress" otherwise. `batch_list` groups by it
([erp/views.py:3859](pyproj/erp/views.py#L3859)), and `batch_list.html` duplicates the same
derivation in JS (`batchCategory()`) so the 30-second poll can tell when a batch needs to be
reloaded into a different section. Two independent implementations of one rule, and no room for
"On Hold" or "Cancelled" — those aren't progress states, they're overrides of progress.

### The real distinction: automatic vs. manual

New/In Progress/Complete are **derived facts** about stage progress — no one should have to
remember to flip a separate switch when the last stage finishes. On Hold/Cancelled are
**decisions** a person makes that have nothing to do with how many stages are done. Conflating the
two (forcing a human to maintain Complete/In Progress by hand) would let the field drift out of
sync with the stages that already track that precisely — the same staleness this codebase already
avoids elsewhere (`incoming_stock`, `pcb_stock` are both live-computed for the same reason).

A plain stored `CharField`, not a property — same pattern as `TestSuite.status`/
`BatchProductionStage.status` already in this codebase — not a computed property, because the
manual states (`ON_HOLD`/`CANCELLED`, and `DRAFT` below) are irreducibly manual facts that can't be
derived from anything else, and storing it means `status` becomes DB-filterable/exportable/API-able
for free.

### Should there be a pre-release "Draft" state?

Yes. `TestSuite.status` (DRAFT/SAVED — [testing/models.py](pyproj/testing/models.py)) is exactly
this split already, elsewhere in this app: a draft isn't yet the thing a real consumer would act
on, and "Save as New Version" is the one explicit action that promotes it. Reusing **"Draft"** for
`Batch` (rather than "Pending") means staff who've learned "Draft = don't act on this yet" from
Test Suites get that meaning for free here too.

One difference worth being explicit about so it's never assumed wrongly: `TestSuite.DRAFT` locks
nothing structurally (steps are just rows being edited). `Batch.DRAFT`'s job isn't to lock
data-shape, it's to gate **whether anyone should act on it physically** (stage work) or
**systemically** (stock reservation, once register#129 lands) — `Batch`'s own fields
(PO/quantity/notes) stay editable throughout, draft or not.

### Final status vocabulary and order

```
DRAFT → READY → IN_PROGRESS → COMPLETE
          ↕ (manual)              ↑
       ON_HOLD                 (terminal)
          ↕
      [any of DRAFT/READY/IN_PROGRESS/ON_HOLD] → CANCELLED (terminal)
```

| Status | Meaning | How it's reached |
|---|---|---|
| `DRAFT` | Recorded, but not committed — don't start work, don't reserve stock | Default on creation |
| `READY` | Released for assembly to begin; nothing's started yet | Manual: **Release to Production** |
| `IN_PROGRESS` | At least one stage underway | Automatic (stage statuses) |
| `COMPLETE` | Every stage `DONE` | Automatic (stage statuses) |
| `ON_HOLD` | Paused mid-flight | Manual: **Put On Hold** / **Resume** |
| `CANCELLED` | Abandoned | Manual: **Cancel** |

**Naming note:** "Ready" was chosen over "Queued" — "Queued" implies a strict ordering/single lane
that may not reflect how batches actually move through production (often several in parallel); 
"Ready" just says "cleared to start whenever capacity allows." Reconsider if this shop genuinely
does run one batch at a time through a single lane.

### Field and transition methods

```python
class Batch(models.Model):
    DRAFT = 'DRAFT'
    READY = 'READY'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETE = 'COMPLETE'
    ON_HOLD = 'ON_HOLD'
    CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (DRAFT, 'Draft'),
        (READY, 'Ready'),
        (IN_PROGRESS, 'In Progress'),
        (COMPLETE, 'Complete'),
        (ON_HOLD, 'On Hold'),
        (CANCELLED, 'Cancelled'),
    ]
    AUTO_STATUSES = {READY, IN_PROGRESS, COMPLETE}  # recompute_status() only touches these

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)

    def _derive_auto_status(self):
        stages = list(self.production_stages.all())
        if stages and all(s.status == BatchProductionStage.DONE for s in stages):
            return self.COMPLETE
        if all(s.status == BatchProductionStage.NOT_STARTED for s in stages):
            return self.READY
        return self.IN_PROGRESS

    def recompute_status(self):
        """Called whenever a BatchProductionStage changes. No-ops if the batch is
        currently a manual override (DRAFT/ON_HOLD/CANCELLED) — those are sticky
        until a person explicitly releases/reactivates."""
        if self.status in self.AUTO_STATUSES:
            self._set_status(self._derive_auto_status())

    def release(self):
        """Move a Draft batch into production-ready state. Manual only — Draft is
        never auto-promoted; its whole purpose is 'don't start yet.'"""
        if self.status == self.DRAFT:
            self._set_status(self._derive_auto_status())

    def put_on_hold(self):
        self._set_status(self.ON_HOLD)

    def cancel(self):
        self._set_status(self.CANCELLED)

    def reactivate(self):
        """Clear a manual ON_HOLD/CANCELLED override, resuming automatic tracking."""
        self._set_status(self._derive_auto_status())

    def _set_status(self, new_status):
        if new_status != self.status:
            self.status = new_status
            self.save(update_fields=['status'])
```

`recompute_status()` gets called from every place a `BatchProductionStage` status changes:
`batch_production_stage_set_status`, `batch_production_stage_add`/`_delete`,
`_apply_template_to_batch`.

### Guards

- `put_on_hold()` is **not offered from `DRAFT`** — "pause" means nothing for work that hasn't
  started.
- `cancel()` **is offered from `DRAFT`** — abandoning an idea before release is normal. (Plain
  `batch_delete` is still fine for a Draft that was a pure data-entry mistake, since nothing of
  consequence — stock, devices, history — exists yet.)
- Neither `put_on_hold()` nor `cancel()` should be offered from `COMPLETE` — nothing left to
  pause/stop.
- `reactivate()` is only offered from `ON_HOLD`/`CANCELLED`.

### UI: Batches list

Replace the `progress_category` groupby with `status` directly:

```python
groups = {status: [] for status, _ in Batch.STATUS_CHOICES}
for batch in batches:
    groups[batch.status].append(batch)
```

Suggested section order: **Draft → Ready → In Progress → On Hold → Complete → Cancelled**. Consider
defaulting Complete/Cancelled to collapsed sections (reusing the Parts list's
`initCategoryCollapse()` pattern) once volume makes that worthwhile.

Storing the field (rather than leaving it computed-in-view) also lets `batch_list_data()`'s JSON
include `batch.status`/`get_status_display()` per batch directly, so `batch_list.html`'s whole
`batchCategory()` re-derivation function in JS goes away — the poll just compares
`data.batches[i].status` to `row.dataset.status`.

### Migration plan

1. Add `status` field, `default=DRAFT`.
2. Data migration backfilling every *existing* batch's `status` using today's exact
   `progress_category` logic, landing in `READY`/`IN_PROGRESS`/`COMPLETE` only (no existing batch
   becomes `DRAFT` retroactively — they're all already real, committed batches). `ON_HOLD`/
   `CANCELLED` are never inferred; a human flags those after the fact where true.
3. Wire `recompute_status()` into the stage-mutating call sites above.
4. Add Release/Put On Hold/Cancel/Reactivate buttons to `batch_edit`, a Status row to
   `batch_print`, and update `batch_list`/`batch_list_data`/`batch_list.html`.
5. Remove `progress_category` — nothing should need it once `status` exists.

### Feeds back into register#129 (stock consumption)

`Batch.cancel()` becomes the real hook for releasing `PartAllocation` rows — cleaner than tying
release to `batch_delete`, since cancelling no longer destroys the row/history, just stops it
consuming further stock. `_sync_batch_part_allocations()` should only run once a batch leaves
`DRAFT` (on `release()`, and on subsequent quantity edits while `READY`/`IN_PROGRESS`) — a batch
still being sized up in Draft should never reserve stock another, real batch might need.

`STOCK_CONSUMPTION_PLAN.md` (amended 2026-10-13) now spells out the full set of hooks it needs
from this plan: `release()` creates allocations, `cancel()` deletes outstanding ones,
`reactivate()` from `CANCELLED` re-creates them for unbuilt units (from `ON_HOLD` it does nothing —
On Hold keeps its reservation), and the transition to `COMPLETE` releases leftovers from an
under-built batch. When implementing `_set_status()` here, leave a clear place for those calls.

### Side-issue discovered while refining this plan

Should a `Device` be linkable to a `DRAFT` batch? Working through that question led to
[DEVICE_GENERATION_PLAN.md](DEVICE_GENERATION_PLAN.md) — see that plan for the answer (gate
"Generate Devices" to `READY`/`IN_PROGRESS` only) and for the bigger side-topic it opened up
(serial number generation from within Register).

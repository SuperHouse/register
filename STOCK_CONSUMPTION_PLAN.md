# Stock Consumption Plan (register#129)

**Status: parked.** Drafting this surfaced a side-issue — `Batch` has no overall status field at
all today (just per-`BatchProductionStage` statuses, and no distinct "cancelled" state) — which
the workflow below leans on. This is the first entry in a chain of parked plans; see
[PLANNING_STACK.md](PLANNING_STACK.md) for the full sequence and where to resume. Short version:
implement [BATCH_STATUS_PLAN.md](BATCH_STATUS_PLAN.md) and
[DEVICE_GENERATION_PLAN.md](DEVICE_GENERATION_PLAN.md) first, then come back and implement this.

**Amended 2026-10-13** to fold in decisions made later in the planning chain, which had only been
recorded in the downstream plans and in this file's Next Steps. The Workflow, out-of-scope,
open-questions and Touch Points sections below now describe the **current** design:

- Stock is **reserved when a batch is released** out of `DRAFT` (per `BATCH_STATUS_PLAN.md`), not
  when the `Batch` row is created.
- Stock is **released by `Batch.cancel()`**, not by deleting the batch.
- Stock is **consumed inside "Generate Devices"** (per `DEVICE_GENERATION_PLAN.md`), one board's
  worth per Device generated. The standalone "Consume Stock" button from the first draft is
  superseded and kept below only as a fallback (see "Superseded: standalone Consume Stock
  button").

The model (`PartAllocation`) and the `Part` changes are unchanged from the first draft.

## Question

[register#129](https://github.com/SuperHouse/register/issues/129) — "Consume stock as batches are
produced." Read the issue and suggest a data model and workflow for implementing stock consumption
management.

## Issue body (as filed)

> We need to be able to track these stock numbers:
>
> 1. Incoming stock. This is now being tracked.
> 2. Stock on hand that has not yet been physically attached to a Device in an irreversible way.
>    This is now being stored.
> 3. Stock that has been assigned, but not yet consumed (attached to a Device as part of the
>    assembly process)
>
> When a batch is created, the stock required to assemble it should be marked as assigned,
> reserved, or committed (whichever terminology is best). When the batch is assembled, the stock
> should be removed entirely.
>
> An unresolved question is whether this can be done by deducting the stock numbers dynamically,
> or whether creation of a batch should add an "assigned" entry. My initial assessment is that we
> should have an "assigned stock" database table that includes an FK to a Part, an FK to a Batch,
> and a count. When displaying a list of parts or part details, the Stock number would have the
> sum of relevant entries subtracted from it. Then when the batch has been assembled these
> "assigned stock" entries could be either deleted or flagged as complete, and the actual number
> deducted from the stock number.
>
> This way if a batch is cancelled, all the assigned stock can be released by removing the
> associated assigned-stock table entries. It also means that stock can be over-assigned and go
> negative, and a determination can be made about which batches should use the stock if this
> occurs.
>
> I don't have a clear model for how this should work so this needs some planning.

## Response

### Why a stored ledger, not a live computation

`Part.incoming_stock` ([erp/models.py:232](pyproj/erp/models.py#L232)) *is* computed live — but
that works because "quantity on an unreceived order line" never needs to be frozen; an order
line's quantity doesn't silently change out from under it.

A batch's required-parts figure is different: it's derived from `Design.bom_entries` via
`_batch_parts_required()` ([erp/views.py](pyproj/erp/views.py)), and a Design's BOM is editable at
any time (`design_bom_entry_edit`). If "committed stock" were computed live from the current BOM ×
batch quantity, editing a Design's BOM after a batch is already mid-production would retroactively
change what's reserved for it — silently freeing or over-committing stock with no record of what
actually happened. That's exactly the kind of problem `BatchProductionStage` already solved for
production stages, by **snapshotting** `ProductionStage.name`/`color` onto the batch at the time
it's applied rather than reading the live `ProductionStage` ("later edits to the template... don't
retroactively affect in-progress batches"). Stock allocation needs the same snapshot discipline.

So: a stored table, following the `BatchProductionStage` snapshot pattern — confirming the issue's
own initial assessment.

### Proposed model: `erp.PartAllocation`

```python
class PartAllocation(models.Model):
    """Stock committed to a Batch's production run, not yet physically consumed.

    per_unit_quantity is snapshotted from Design.bom_part_counts() at allocation
    time — a later BOM edit must not retroactively change what's already reserved
    for an in-progress batch (same reasoning as BatchProductionStage snapshotting
    ProductionStage.name/color).
    """
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='part_allocations')
    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name='allocations')
    per_unit_quantity = models.PositiveIntegerField(help_text='BOM quantity per board, snapshotted at allocation time')
    quantity = models.PositiveIntegerField(help_text='Outstanding reserved quantity (decremented as units are consumed)')
    created_dt = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [('batch', 'part')]
```

- `on_delete=CASCADE` from `batch` means **deleting a batch automatically releases its
  allocations** — nothing to roll back, since `Part.stock` was never touched by a reservation,
  only by consumption. Cancelling is no longer a deletion once `Batch.status` exists, so
  `Batch.cancel()` deletes the outstanding allocation rows explicitly (see Workflow step 5) — same
  end effect. Either way this answers the issue's "if a batch is cancelled, all the assigned stock
  can be released by removing the associated assigned-stock table entries."
- `on_delete=PROTECT` from `part` matches `DesignBomEntry.part` — a part reserved against an open
  batch shouldn't be deletable out from under it.
- `quantity` is allowed to produce a negative *free stock* figure elsewhere (see below) — the row
  itself never goes negative, `Part.stock` does. That's the issue's explicit ask: "stock can be
  over-assigned and go negative, and a determination can be made about which batches should use
  the stock."

### `Part` changes

`Part.committed_stock` ([erp/models.py:185](pyproj/erp/models.py#L185)) already exists today as a
**manual, never-automated** `IntegerField` (issue #89) — this issue is literally the automation of
that field the docstring already flags as outstanding. Replace it with a computed property, the
same way `incoming_stock` replaced its old stored/recomputed predecessor:

```python
@property
def committed_stock(self):
    """Sum of outstanding PartAllocation quantities across all batches."""
    return self.allocations.aggregate(total=models.Sum('quantity'))['total'] or 0

@property
def free_stock(self):
    """Stock on hand minus everything committed to open batches. Can go negative —
    that's a deliberate signal that something is over-assigned, not an error state."""
    return (self.stock or 0) - self.committed_stock
```

**Naming collision to watch:** the Parts list already shows a column called "Available" for
`Part.total_stock` (summed *supplier* stock — a completely different concept). Don't reuse
"Available" for `free_stock`; call the new columns **Committed** and **Free** (or similar) on the
Parts list, Part edit page, and the Batch detail page's Parts Required card, so the three numbers
(Stock / Committed / Free) sit next to the existing (unrelated) Available/supplier figure without
ambiguity.

### Workflow

Each step is keyed to an explicit event: a `Batch.status` transition from
[BATCH_STATUS_PLAN.md](BATCH_STATUS_PLAN.md), or a "Generate Devices" click from
[DEVICE_GENERATION_PLAN.md](DEVICE_GENERATION_PLAN.md).

**1. Batch created** (`batch_add`) — **no allocation.** A new batch starts in `DRAFT` ("recorded,
but not committed — don't start work, don't reserve stock"). A batch still being sized up must not
reserve stock that another, real batch might need.

**2. Batch released** (`Batch.release()`, `DRAFT` → `READY`) — call a new
`_sync_batch_part_allocations(batch)` that reuses the existing `_batch_parts_required(batch)`
helper: for each part with `required > 0` (respecting `no_stock_required`, same filter already
applied elsewhere), create a `PartAllocation(batch=batch, part=part, per_unit_quantity=per_board,
quantity=required)`. This is the moment the BOM gets snapshotted.

**3. Batch quantity edited** (`batch_edit`, while `READY`/`IN_PROGRESS`/`ON_HOLD`) — re-run the
same sync, but **only if no consumption has started yet** for that batch (every allocation's
`quantity == per_unit_quantity * old batch.quantity`, untouched — this check stays correct whatever
path created any Devices). If any allocation has already been partly consumed, block the resize
with a warning rather than guessing how to redistribute it — ambiguous enough that it should be a
human decision, not silent logic. In `DRAFT` there are no allocations, so edits need no sync.

**4. Devices generated** ("Generate Devices", gated to `READY`/`IN_PROGRESS`) — consume stock in
the **same transaction** that creates the `Device` rows. Generating N devices is the physical event
the issue describes ("attached to a Device as part of the assembly process"), so there is no
separate consumption action.

```python
def _consume_batch_stock(batch, units):
    """Called inside Generate Devices' transaction.atomic(), after the Device rows are
    created. units = number of Devices just generated."""
    deltas = {}
    for alloc in batch.part_allocations.select_for_update():
        used = units * alloc.per_unit_quantity
        # Stock drops by the full amount physically used, even past the reservation
        # (over-building for scrap replacement is allowed, per DEVICE_GENERATION_PLAN.md).
        deltas[alloc.part_id] = deltas.get(alloc.part_id, 0) - used
        alloc.quantity -= min(used, alloc.quantity)
        if alloc.quantity == 0:
            alloc.delete()
        else:
            alloc.save(update_fields=['quantity'])
    _apply_part_stock_deltas(deltas)   # already exists — erp/views.py
```

Differences from the first draft's `batch_consume_stock`:

- `units` is the number of Devices generated, not a free-typed quantity.
- Over-building beyond the reservation now still deducts `Part.stock` for the extra boards. The
  first draft capped consumption at the reserved amount, which would have under-counted parts
  that were physically used.
- Consumption reads `per_unit_quantity` from the allocation snapshot, not the live BOM, so a BOM
  edit after release still can't change what a board "costs" in stock.

It still reuses `_apply_part_stock_deltas()` ([erp/views.py](pyproj/erp/views.py)) unchanged. That
helper already does the `Coalesce(F('stock'), 0) + delta` pattern and already allows negative
deltas, which is the "allowed to go negative" behaviour the issue wants. `Part.save()`'s existing
`PartStockHistory` logging means consumption shows up on the Stock History chart with no new
history table.

**5. Batch cancelled** (`Batch.cancel()`) — delete the batch's remaining `PartAllocation` rows.
Stock already consumed by generated Devices is **not** returned: those parts are soldered onto
boards.

**6. Batch reactivated** (`Batch.reactivate()`) —
- From `CANCELLED`: re-run `_sync_batch_part_allocations()` for the units not yet built
  (`batch.quantity` minus Devices already linked to the batch), re-snapshotting the current BOM.
- From `ON_HOLD`: nothing to do. **On Hold keeps its reservation** — a paused batch is still
  expected to finish, so its stock should not be handed to another batch.

**7. Batch completes** (status becomes `COMPLETE`) — release any allocation still outstanding.
That's the under-built case (fewer Devices than `batch.quantity`): without this, leftover
reservations would stay stuck forever on a finished batch. See open question below.

### Superseded: standalone Consume Stock button

The first draft had an explicit **"Consume Stock"** button on the Batch detail page with a
free-typed unit count, independent of Device creation. Superseded by step 4 above. Keep it in mind
only as a fallback: if "Generate Devices" is dropped or delayed, this button is the smallest way to
ship stock consumption on its own. It would then also need its own `Batch.status` gate (e.g.
`READY`/`IN_PROGRESS` only).

### Open questions to settle when resuming

- **Release leftovers on `COMPLETE`, or not?** Step 7 recommends releasing automatically. The
  alternative is to keep leftovers visible until someone acts, which surfaces an under-built batch
  but needs a manual "release remaining stock" control. `COMPLETE` is set automatically from stage
  statuses, so the hook would live in `Batch._set_status()`.
- **Deleting a generated Device.** If a Device was generated by mistake and then deleted, should
  its board's worth of stock go back to `Part.stock` (and to the allocation)? The simplest v1 is
  "no — correct `Part.stock` by hand". Revisit if mistakes are common.
- **Depends on Device Generation's "confirm after build" reading.** Step 4 assumes clicking
  "Generate Devices" means "these boards were just built", which is that plan's default
  recommendation. If the shop instead needs serials minted *before* assembly (to print labels
  first), consumption must move to a separate "mark built" event, and the superseded button above
  comes back in some form.
- **Devices created by other paths don't consume stock.** `import-xlsx`, the `device/add/` API and
  the admin all create Devices without going through Generate Devices. Accepted as a known gap,
  since Generate Devices is the intended path going forward and both are expected to coexist only
  during the transition. Batches still using the spreadsheet during that period need `Part.stock`
  corrected by hand.

### Deliberately out of scope for a first version

- **~~Per-`Device` consumption.~~** Now **in scope** — see step 4. The first draft deferred it
  because `Device` creation happened through several disconnected paths. "Generate Devices" gives
  one in-app path that is the natural place for it; the other paths are the known gap above.
- **`PartSubstitution`-aware allocation.** If a part is short, there's no logic here for
  allocating against a substitute instead — flagging as future work, not blocking this.
- **Backfilling allocations for already-in-progress batches.** `PartAllocation` rows only start
  existing going forward from whenever this ships. Once `BATCH_STATUS_PLAN.md`'s migration has
  backfilled existing batches to `READY`/`IN_PROGRESS`/`COMPLETE`, a one-off data migration could
  create allocations for the `READY`/`IN_PROGRESS` ones, for `batch.quantity` minus Devices
  already linked. That's a call for whoever picks this back up, not assumed here.

### Touch points

- **Model:** new `PartAllocation` in [erp/models.py](pyproj/erp/models.py), registered in
  `erp/admin.py` (plain CRUD, for manual correction when something's gone sideways).
- **Status hooks:** `Batch.release()`, `cancel()`, `reactivate()` and the transition to `COMPLETE`
  (in `_set_status()`) call into the allocation helpers (steps 2, 5, 6, 7).
- **Views:** `_sync_batch_part_allocations()` and `_consume_batch_stock()` in
  [erp/views.py](pyproj/erp/views.py). The sync is called from the release action and from
  `batch_edit`'s quantity change. `_consume_batch_stock()` is called from the Generate Devices
  view (see `DEVICE_GENERATION_PLAN.md`), not from a view of its own.
- **UI:** Parts list, Part edit page and the Batch detail page's Parts Required card gain
  Committed/Free columns, replacing the manual `committed_stock` field. No "Consume Stock" button.
- **Export/import:** `PartAllocation` needs adding to `export_data`/`import_data`'s model list and
  `_flush_app_data()`'s delete order (before `Batch`/`Part`, same as every other FK'd model there).

## Next steps

See [PLANNING_STACK.md](PLANNING_STACK.md) for the current full queue (as of this writing: an
unnamed piece of work discovered while refining Device Generation, which blocks
[DEVICE_GENERATION_PLAN.md](DEVICE_GENERATION_PLAN.md), which blocks
[BATCH_STATUS_PLAN.md](BATCH_STATUS_PLAN.md), which blocks this plan). Once that chain clears:

1. Implement `BATCH_STATUS_PLAN.md`'s `Batch.status` field and transitions.
2. Implement `DEVICE_GENERATION_PLAN.md`'s "Generate Devices" action, gated to
   `READY`/`IN_PROGRESS` batches.
3. Implement this plan as written above: `PartAllocation`, the status hooks, and
   `_consume_batch_stock()` called from Generate Devices. Settle the open questions first.

Steps 2 and 3 can reasonably ship together, since step 3's consumption lives inside step 2's
transaction.

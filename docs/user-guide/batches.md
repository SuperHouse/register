# Production Batches

A Batch tracks a production run of a Design through an ordered checklist of production stages (e.g. "PCBs stocked", "Top SMT complete", "Programming", "Final inspection").

## Batch list

The Batches page (`/batches/`) lists all production runs, most recent first. Each row shows the design, an optional purchase order number, and the quantity of boards in the run.

## Creating a batch

Click **Add Batch** or use the **Add New Batch** button on a Design's detail page (which pre-selects the design). Each batch requires:

- **Design** — which board type is being produced
- **Quantity** — how many boards in this run
- **Purchase Order** — optional purchase order number
- **Notes** — optional free-text notes

## Production stages

The batch detail page shows the ordered list of production stages. Each stage has:

- **Name** and **colour** (inherited from the ProductionStage definition at the time the stage was added)
- **Status** — one of Not Started, In Progress, On Hold, or Done
- **Due date** and **Completion date/time**

### Setting status

Click the status icon buttons on each row to change a stage's status. The row colour updates immediately:

| Status | Icon | Row colour |
|---|---|---|
| Not Started | ○ | (none) |
| In Progress | ▷ | Blue |
| On Hold | ⏸ | Yellow |
| Done | ✓ | Green |

Marking a stage as **Done** automatically records the current date and time as the completion date.

### Reordering stages

Drag rows by the grip handle (⠿) on the left to reorder production stages within a batch.

## Applying a template

If you have defined Production Stage Templates (under **Settings → Production Stage Templates**), click **Apply Template** to append the template's stages to the batch. Stages whose name already exists in the batch are skipped, so re-applying a template or applying a second template is safe.

## Adding individual stages

Stages can also be added one at a time using the **Add Stage** dropdown at the bottom of the stage list.

## Production Stage Templates

Templates are reusable named collections of production stages. For example, a "Double-sided SMT" template might include:

1. PCBs stocked
2. Top SMT complete
3. Top reflow complete
4. Bottom SMT complete
5. Bottom reflow complete
6. Inspection
7. Programming
8. Final test

Templates are managed under **Settings → Production Stage Templates**. Like stages themselves, the order within a template can be adjusted by dragging.

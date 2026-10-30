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

- **Name**, **colour** and **icon** — from the stage's definition under **Settings → Production Stages**. If the definition is edited later, every batch that uses the stage shows the change.
- **Status** — one of Not Started, In Progress, On Hold, or Done
- **Due date** and **Completion date/time**

### Stage explanations

If a stage has an explanation, an info icon (ⓘ) appears next to its name. Click it to see what happens in that stage. The explanation can be text, an image, a YouTube video, or a mix. Clients who can see the batch can open explanations too.

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

If you have defined Production Stage Templates (under **Settings → Production Stage Templates**), click **Apply Template** to append the template's stages to the batch. Stages already in the batch are skipped, so re-applying a template or applying a second template is safe. Inactive stages are skipped too (see below).

## Adding individual stages

Stages can also be added one at a time using the **Add Stage** dropdown at the bottom of the stage list.

## Defining production stages

Production stages are defined under **Settings → Production Stages**. Click a stage's edit button to set:

- **Name** and **colour**.
- **Icon** — a [Bootstrap Icons](https://icons.getbootstrap.com/) name such as `bi-truck`, or a [CoreUI Icons](https://coreui.io/icons/free/) name such as `cil-puzzle`. The icon is drawn in white or dark, whichever is easier to read on the colour.
- **Active** — untick this to retire a stage. An inactive stage can't be added to batches or templates, but still shows on batches that already use it. A stage that any batch or template uses can't be deleted, so retire it instead.
- **Explanation** — optional text, image, and YouTube video link shown when someone clicks the stage's info icon on a batch. Unlisted YouTube videos work. Tick **Play as a looping clip** to play a short video silently on a loop with no controls, like a GIF.

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

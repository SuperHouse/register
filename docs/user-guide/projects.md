# Projects

A Project records a piece of client work before and around production: the first enquiry, the quote, the design work, the prototypes, and the handover to production. Production runs themselves are [Batches](batches.md).

## What a project holds

| Field | Meaning |
|---|---|
| **Code** | Set by Register when the project is added, for example `P-2026-014`. Numbering starts again at 001 each year. The code never changes, so you can use it as a reference with the client. |
| **Organisation** | The client the work is for. Only organisations with the **Client** flag are offered. |
| **Name** and **Description** | The client sees both. Keep internal notes out of them. |
| **Phase** | Where the work is: Enquiry, Quoting, Quoted, Design, Prototyping, Pre-production or Production. |
| **Status** | Whether the work is moving: Active, On hold, Closed or Declined. The status is separate from the phase, so a project on hold still shows the phase it stopped in. |
| **Start date** and **Target date** | Optional. The target date cannot be before the start date. |
| **Designs** | The designs made or changed for the project. |

## Project list

The Projects page (`/projects/`) lists projects with their code, phase, status, target date and number of designs. Click a row to open the project.

By default the list shows only open projects (Active or On hold). Use the filters to choose a phase or a status, or **All statuses** to see every project. The search box finds text in the code, name or description. If you can see projects of more than one organisation, you can also filter by organisation.

## Project page

The project page shows the project's details and two lists:

- **Designs**: the designs linked to the project. Click a design to open it.
- **Builds**: every batch of those designs, newest first, with its quantity, purchase order, due date and progress. Click a batch to open it.

A design can be part of more than one project, for example when a later project adds features to an existing design. Its batches then show on each of those projects.

The Design page also lists the projects that use the design, on its **Details** tab.

## What clients see

Users of an organisation see the Projects page with that organisation's projects only, read-only. They see the code, name, description, phase, status, dates, designs and builds. They do not see the Add, Edit, Link Design or Unlink buttons, and another organisation's project does not exist for them.

## Managing projects (staff)

### Add a project

1. On the Projects page, click **Add**.
2. Choose the organisation, and type a name.
3. Optionally, fill in the description, phase, status and dates. A new project starts in the Enquiry phase with the Active status.
4. Click **Add Project**. Register opens the new project's page.

### Edit a project

1. Open the project and click **Edit**.
2. Change the fields, and click **Save Changes**.

You cannot move a project to a different organisation while it has designs of the current organisation. Unlink those designs first.

### Link or unlink a design

- To link a design, choose it in the list under **Designs** and click **Link Design**. The list offers only the designs of the project's organisation.
- To unlink a design, click the unlink button on its row. This changes only the project. The design and its boards and batches stay as they are.

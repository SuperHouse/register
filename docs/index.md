# Testomatic Register

The Testomatic Register is a web application for tracking individual printed circuit boards (PCBs) through production, testing, programming, and shipping.

It was originally designed to work with the [Testomatic](https://github.com/superhouse/testomatic) PCB test jig system, but it operates independently and can be used without any automated test equipment.

## What it does

Data is organised in a hierarchy:

**Organisations** represent customers or companies whose boards are being assembled. Each organisation has its own users who can log in and view data for their boards only.

**Designs** represent a type of circuit board — a specific SKU and hardware version. Design files, BOMs, firmware binaries, schematics, and other assets can be attached directly to a design for easy reference.

**Boards** (also called Devices) represent individual circuit boards identified by serial number. Each board is an instance of a Design and accumulates test records, programming events, images, and notes over its lifetime.

**Parts** are a component library that stores sourcing information, price breaks, datasheets, and possible substitutions for each component used in your designs.

**Batches** track production runs of a Design through an ordered checklist of production stages (SMT, reflow, inspection, programming, etc.).

## Access control

Staff users see all data across all organisations. Non-staff users log in and see only data belonging to their associated organisation. Internal notes, events, and assets are hidden from non-staff users.

## Getting started

- [Development setup](admin/setup.md) — run the application locally
- [Production deployment](admin/deployment.md) — serve the application with uWSGI
- [Configuration reference](admin/configuration.md) — environment variables
- [User guide](user-guide/index.md) — how to use the web interface
- [API reference](api/reference.md) — integrate external systems

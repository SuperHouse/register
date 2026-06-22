# Organisations

Organisations represent companies or entities associated with boards in the system — typically the customer who commissioned or purchased the assembly.

## Organisation types

Each organisation can hold one or more roles:

| Role | Meaning |
|---|---|
| Client | Commissions or purchases assembled boards |
| Manufacturer | Assembles boards |
| Supplier | Supplies components |

## Organisation list

The Organisations page (`/organisation/`) lists all organisations with their company name and logo. Staff only.

## Organisation detail

The detail page shows the organisation's logo (if set), associated users, and the designs belonging to that organisation. The designs table supports live filtering.

## Managing users

Users are associated with organisations via the admin interface at `/office/`. A user can belong to multiple organisations; they will see data from all of them when logged in.

## API keys

Each organisation has an API key used to authenticate automated requests. The key is shown on the organisation detail page and is used as the `X-API-Key` header value in all API calls. See [API Reference](../api/reference.md).

## Creating and editing organisations

Staff can create, edit, and view organisations from the Organisations list. The logo is displayed in the sidebar for non-staff users logged in to that organisation.

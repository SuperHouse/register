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

Staff can create, edit, and view organisations from the Organisations list. The organisation's logo is shown on its own pages. To show a client's logo in the sidebar, use branding (below).

## Branding

A client can have their own hostname, for example `serials.example.com`, and use it in the QR codes on their boards. When the site is opened through that hostname, it shows the client's branding instead of the Testomatic defaults:

- their logo at the top of the sidebar, including on the login page, linked to a page of their choice
- their name in browser tab titles, in password reset pages, and in password reset emails
- optionally, their own favicon (the icon in the browser tab)
- optionally, their colours for the sidebar background and for buttons, links and table headers
- their logo on printed batch sheets

Branding changes only how the site looks. It never changes what data a user can see.

No organisation is special. A hostname without branding shows the Testomatic name, logo and favicon. This includes SuperHouse's own hostnames: to show the SuperHouse logo on them, add branding for each one to the SuperHouse organisation, the same as for any client.

### Add branding for a hostname

1. Open the organisation and click **Edit**.
2. In the **Branding** card, click **Add Hostname**.
3. Fill in the form:
    - **Hostname**: the hostname only, for example `serials.example.com`. Do not include `https://`, a path, or a port number.
    - **Display name**: shown in titles and emails. The organisation's name is filled in for you.
    - **Logo**: required. The logo can be seen by anyone, including people who are not logged in, because the login page shows it.
    - **Favicon**: optional. The icon in the browser tab, and on a phone's home screen. Use a square image if you can: other shapes are padded with transparency, not cropped. It is resized to 192 × 192 pixels. Like the logo, anyone can see it. If you leave it empty, the Testomatic icon is used. To go back to the Testomatic icon later, edit the branding and select **Remove favicon**.
    - **Logo link**: where clicking the logo goes, for example the client's website. If you leave it empty, the logo goes to the dashboard.
    - **Sidebar colour** and **Accent colour**: type a colour such as `#3c4b64`, or use the colour picker. Leave a colour empty to use the default. The text colour on the sidebar and on buttons is chosen automatically, so that it can be read. Links use a darker version of a light accent colour, so that they can be read on a white page.
4. Click **Save**.

The hostname must also be set up on the server before anyone can use it: see [Adding a vanity hostname](../admin/deployment.md#adding-a-vanity-hostname). If the hostname is not yet in the server's `ALLOWED_HOSTS`, the Branding card shows **Not in ALLOWED_HOSTS** next to it.

To change or remove branding, click the hostname in the Branding card, or click its delete button.

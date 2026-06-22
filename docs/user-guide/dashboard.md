# Dashboard

The dashboard (`/`) gives a live overview of the system.

## Summary cards

The top row shows counts for:

- **Clients** — number of organisations in the system
- **Designs** — number of board types
- **Boards** — total number of individual boards registered

Cards briefly pulse green when their value changes. Non-staff users see counts filtered to their organisation.

## Assembly chart

Below the cards, a line chart shows the number of boards assembled per month. The chart polls the API every 30 seconds and redraws only if the underlying data has changed. It also re-scales automatically if the browser window is resized.

## Clean view

The **Clean view** button (top right) hides the navigation sidebar and header, leaving just the stats and chart visible. This is useful when using the dashboard as a status screen display. Click the button again to restore the normal layout.

# ConcertSync Textual Frontend

This folder contains a terminal user interface (TUI) built with Textual to interact with the existing ConcertSync TCP server.

## Features

- Connect to any ConcertSync server (`host:port`).
- Reserve a single seat.
- Reserve multiple seats atomically (`RESERVE_BATCH`).
- Confirm and cancel transactions.
- Transaction usability helpers:
  - the Transaction ID input is auto-filled after each reserve
  - Use Last TX button
  - Use Last ACTIVE button
- Live section availability dashboard (`QUERY` polling every second).
- Visual seat map per section with live color updates:
  - **Clickable seats** - click any seat in the map to auto-fill row/column fields
  - Column numbers displayed at the top (0–9 repeating)
  - Row numbers on the left (00–19)
  - section selector (VIP / PREFERENTIAL / GENERAL)
  - green dot (`·`) = AVAILABLE
  - yellow `R` = RESERVED
  - red `X` = SOLD
- Local transaction tracking with real-time TTL countdown.
- Live event stream panel.
- Lightweight performance charts:
  - requests per tick
  - THREAD events from `logs/system.log`
  - ERROR events from `logs/system.log`

## Start the TUI

From the repository root:

```bash
nix develop -c python -m frontend_tui
```

If you are not using Nix, make sure `textual` is installed and run:

```bash
python -m frontend_tui
```

## How to Use Clickable Seat Map

The seat map in the **Visual seat map** panel is fully interactive:

1. **View seats**: Use the section selector dropdown to switch between VIP, PREFERENTIAL, or GENERAL
2. **Click a seat**: Click on any colored symbol (·, R, or X) in the seat grid
   - The **Row** and **Column** fields on the left panel will auto-fill with that seat's coordinates
   - The section selector will update to match your click
   - Status bar will show the selected seat and its current state (AVAILABLE, RESERVED, or SOLD)
3. **Reserve**: After clicking a seat, press **Reserve Seat** button

**Seat Map Layout:**
```
     0 1 2 3 4 5 6 7 8 9 10 11 ...  (Column numbers - actual seat indices)
00 | · · R X · · · R X · ·  ·  ...
01 | R X · · · · · · · · ·  ·  ...
02 | · · · · · X R · · · ·  ·  ...
...
```

**Seat Map Legend:**
```
·  (green)  = AVAILABLE (click to reserve)
R  (yellow) = RESERVED (another user's pending reservation)
X  (red)    = SOLD (confirmed reservation)
```

## Batch Reservation Input Format

Use this format in the batch input field:

```text
VIP:0:0,VIP:0:1,GENERAL:2:3
```

Each item is `SECTION:ROW:COL`.

## Notes

- The TUI keeps transaction TTL counters client-side based on the server response `ttl`.
- Thread/performance charts are driven by local metrics and log tailing; if your log path differs, update it in the UI.
- This frontend does not change server behavior; it only consumes the existing client-server protocol.

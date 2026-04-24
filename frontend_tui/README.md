# ConcertSync Textual Frontend

This folder contains a terminal user interface (TUI) built with Textual to interact with the existing ConcertSync TCP server.

## Features

- Connect to any ConcertSync server (`host:port`).
- Reserve a single seat.
- Reserve multiple seats atomically (`RESERVE_BATCH`).
- Confirm and cancel transactions.
- Live section availability dashboard (`QUERY` polling every second).
- Visual seat map per section with live color updates:
  - green = AVAILABLE
  - yellow = RESERVED
  - red = SOLD
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

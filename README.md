# ConcertSync

TCP-based concurrent seat reservation system. A Python server manages seat state
across three sections (VIP, PREFERENTIAL, GENERAL) using threading, lock hierarchies,
and semaphores. Includes a **PySide6 desktop GUI** with push notifications and
automatic ticket generation.

## Quick Start

```bash
# Terminal 1: start server
python main.py

# Terminal 2: start client GUI
python -m frontend_pyside6 --mode client

# Or: server + client in one command
./scripts/run.sh both
```

Port **9999** must be available.

## Requirements

| Setup | Command |
|---|---|
| Nix | `nix develop` |
| uv | `uv sync --group dev` |
| pip | `pip install pyside6` |

## Usage

1. Start the server (`python main.py`).
2. Launch the GUI (`python -m frontend_pyside6`).
3. Enter a **User ID** (or leave blank for auto-generated).
4. Click **Connect**.
5. Click an **AVAILABLE** seat (green) to reserve it — it turns blue.
6. **Confirm** to finalize (seat turns red, ticket generated in `tickets/`).
7. **Cancel** to release the seat.
8. Switch sections with the **VIP / Preferential / General** buttons.
9. Reservations expire after **300 seconds** — TTL countdown shown in the panel.

### Dashboard Mode

Monitor server state in real time:

```bash
python -m frontend_pyside6 --mode dashboard
```

## Seats

| Section | Size | Capacity |
|---|---|---|
| VIP | 5 × 10 | 50 |
| PREFERENTIAL | 10 × 15 | 150 |
| GENERAL | 20 × 20 | 400 |

**Colors:** Green = Available, Blue = Yours, Orange = Reserved, Red = Sold, Purple = Pending.

## Build Standalone Executables

```bash
# macOS ARM (Apple Silicon)
bash scripts/build_mac.sh

# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File scripts/build_windows_exe.ps1
```

Output: `dist/ConcertSync` (macOS) or `dist/ConcertSync.exe` (Windows).

## Multi-User Demo

1. Start the server on your machine (`python main.py`).
2. Share your LAN IP with others.
3. They connect using the GUI — set **Host** to your IP and click **Connect**.
4. Everyone sees the seat map updating live.

## Load Generator

```bash
# Slow: 1 request every 0.5s
python tests/load_generator.py --requests 50 --delay 0.5

# Fast: all at once, targeting same seats
python tests/load_generator.py --requests 100 --conflicts
```

| Flag | Default | Description |
|---|---|---|
| `--requests N` | 100 | Number of concurrent requests |
| `--delay N` | 0 | Seconds between requests |
| `--conflicts` | off | Multiple threads target same seats |

## Notifications

Clients can subscribe to real-time push notifications via a long-lived TCP
connection (`SUBSCRIBE_NOTIFICATIONS` action). Events: TTL warnings,
confirmations, expiry notifications, and seat availability alerts.

## Tickets

Every CONFIRM generates a ticket file in `tickets/` with seat, zone, date,
and transaction information.

## Reset

```bash
rm data/concert_sync.db
```

## Tests

```bash
python -m pytest tests/ -x -v
```

## Project Structure

```
main.py                          # Server entry point
src/
  server/                        # TCP server, threading, request dispatch
  client/                        # TCP client with typed exceptions
  shared_resources/              # Seat matrix, semaphores, SQLite persistence
  synchronization/               # Lock hierarchy (deadlock prevention)
  utils/                         # Config, enums, protocol validation
frontend_pyside6/                # PySide6 desktop GUI
tests/                           # 217+ tests — protocol, concurrency, persistence
scripts/                         # Build & run helpers
```

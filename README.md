# ConcertSync

TCP-based concurrent seat reservation system for a concert venue. Python server
manages seat state across three sections (VIP, PREFERENTIAL, GENERAL) using
threading, lock hierarchies, and semaphores. Two frontends available: a **PySide6
desktop GUI** (recommended) and a **Textual terminal TUI** (legacy).

Features **async push notifications** (TTL warnings, confirmations, expiry) and
**automatic QR ticket generation** for every confirmed purchase.

## Quick Start

```bash
# Option A: Server + GUI in one command
python desktop_launcher.py

# Option B: Server + TUI in one command (Nix)
nix develop --command python desktop_launcher.py --mode tui

# Option C: Separate processes
python main.py                          # Terminal 1: start server
python -m frontend_pyside6              # Terminal 2: start GUI
```

## Requirements

| Setup | Command |
|---|---|
| Nix (recommended) | `nix develop` — enters shell with all deps |
| uv | `uv sync --group pyside6 --group tickets` |
| pip | `pip install pyside6 qrcode pillow` |

Port **9999** must be available.

## Running

### PySide6 Desktop GUI

```bash
# Server + GUI (one process)
python desktop_launcher.py

# Server only
python desktop_launcher.py --mode server

# GUI only (connect to existing server)
python desktop_launcher.py --mode client
python -m frontend_pyside6 --mode client

# Server monitoring dashboard
python desktop_launcher.py --mode dashboard
python -m frontend_pyside6 --mode dashboard
```

### Using the GUI

1. Click **Connect** in the left panel (enter a user ID or leave blank for auto-generated).
2. Click an **AVAILABLE** seat (green) to reserve it immediately — it turns blue.
3. The **Transaction ID** auto-populates in the input field.
4. Click **Confirm** to finalize the purchase (seat turns red — SOLD). A **QR ticket** is generated in `tickets/`.
5. Click **Cancel** to release the seat.
6. Switch sections with the **VIP / Preferential / General** buttons.
7. Click **Activity Center** to see event logs, active sessions, and stats.
8. Reservations expire after **300 seconds** (5 min) — TTL countdown shown in the panel. You'll receive a **TTL warning notification** 30s before expiry.

### Textual TUI (Legacy)

```bash
nix develop --command python -m frontend_tui
```

### Nix

```bash
nix develop
python main.py                    # start server
python -m frontend_pyside6        # start GUI
```

## Seats

| Section | Size | Capacity |
|---|---|---|
| VIP | 5 × 10 | 50 |
| PREFERENTIAL | 10 × 15 | 150 |
| GENERAL | 20 × 20 | 400 |

**Colors (GUI):** Green = Available, Blue = Yours, Orange = Reserved (other user), Red = Sold, Purple = Pending.

## Load Generator (Demo para profesora)

Genera requests concurrentes para llenar asientos en vivo mientras se ve en la GUI.

```bash
# Terminal 1: servidor
nix develop --command python main.py

# Terminal 2: GUI
nix develop --command python -m frontend_pyside6 --mode client

# Terminal 3: generador de carga (lento — 1 request cada 0.5s)
nix develop --command python tests/load_generator.py --requests 50 --delay 0.5

# Más lento aún (1 cada 2s)
nix develop --command python tests/load_generator.py --requests 20 --delay 2

# Rápido (todo de golpe, sin delay)
nix develop --command python tests/load_generator.py --requests 100 --conflicts
```

| Flag | Default | Descripción |
|---|---|---|
| `--requests N` | 100 | Cantidad de requests concurrentes |
| `--delay N` | 0 | Segundos de espera entre cada request |
| `--conflicts` | off | Múltiples hilos atacan los mismos asientos |

## Notifications

Clients can subscribe to real-time push notifications via a long-lived TCP connection:

```bash
python3 -c "
import socket, json
s = socket.socket()
s.connect(('localhost', 9999))
req = json.dumps({'action': 'SUBSCRIBE_NOTIFICATIONS', 'user_id': 'my_user'})
s.sendall(req.encode())
print(s.recv(4096).decode())  # SUCCESS response
# Socket stays open — server pushes JSON notification lines
"
```

| Event | Trigger | Message |
|-------|---------|---------|
| `TTL_WARNING` | ~30s before reservation expires | "Su reserva expirará en 30 segundos." |
| `CONFIRMED` | After successful CONFIRM | "Compra confirmada correctamente." |
| `EXPIRED` | Reservation expired, seats released | "Su reserva ha expirado y los asientos fueron liberados." |
| `AVAILABILITY` | Section goes from full to available | "Hay nuevos asientos disponibles en la zona <SECTION>." |

Protocol reference: `docs/protocol-contract-v1.md` §SUBSCRIBE_NOTIFICATIONS.

## QR Tickets

Every CONFIRM generates a scannable QR ticket in `tickets/`:

```
tickets/
├── ticket_tkt-000001.txt   # Human-readable (Unicode box-drawing)
└── ticket_tkt-000001.png   # QR code (scannable by camera apps)
```

The QR contains plain text (no network required): ticket ID, zone, seats, date.  
Ticket generation runs in a background thread — it never delays the CONFIRM response.

## Reset — Limpiar estado guardado

El servidor persiste asientos y sesiones en `data/concert_sync.db`.
Para empezar desde cero:

```bash
# 1. Parar el servidor (Ctrl+C)
# 2. Borrar la base de datos
rm data/concert_sync.db
# 3. Iniciar el servidor de nuevo
nix develop --command python main.py
```

## Tests

```bash
python -m pytest tests/ -x -v      # 217+ tests
nix develop --command pytest tests/ -x -v  # via Nix
```

## Project Structure

```
main.py                          # Server entry point
desktop_launcher.py              # Server + frontend launcher
src/
  server/                        # TCP server, threading, request dispatch
  client/                        # TCP client with typed exceptions
  shared_resources/              # Seat matrix, semaphores, SQLite persistence
  synchronization/               # Lock hierarchy (deadlock prevention)
  utils/                         # Config, enums, protocol validation
frontend_pyside6/                # PySide6 desktop GUI (recommended)
frontend_tui/                    # Textual TUI (legacy)
tests/                           # 217 tests — protocol, notifications, tickets, race conditions
```
docs/
  protocol-contract-v1.md        # JSON-over-TCP protocol specification
```

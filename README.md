# ConcertSync

TCP-based concurrent seat reservation system for a concert venue. Python server
manages seat state across three sections (VIP, PREFERENTIAL, GENERAL) using
threading, lock hierarchies, and semaphores. Two frontends available: a **PySide6
desktop GUI** (recommended) and a **Textual terminal TUI** (legacy).

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
| uv | `uv sync --group pyside6` |
| pip | `pip install pyside6` |

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
4. Click **Confirm** to finalize the purchase (seat turns red — SOLD).
5. Click **Cancel** to release the seat.
6. Switch sections with the **VIP / Preferential / General** buttons.
7. Click **Activity Center** to see event logs, active sessions, and stats.
8. Reservations expire after **300 seconds** (5 min) — TTL countdown shown in the panel.

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
python -m pytest tests/ -x -v
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
tests/                           # 204 tests — protocol, race conditions, concurrency
```

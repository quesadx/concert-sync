# ConcertSync

TCP-based concurrent seat reservation system for a concert venue. Python server
manages seat state across three sections (VIP, PREFERENTIAL, GENERAL) using
threading, lock hierarchies, and semaphores. Two frontends available: a **PySide6
desktop GUI** (recommended) and a **Textual terminal TUI** (legacy).

Features **async push notifications** (TTL warnings, confirmations, expiry) and
**automatic ticket generation** for every confirmed purchase.

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
4. Click **Confirm** to finalize the purchase (seat turns red — SOLD). A **ticket** file is generated in `tickets/`.
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

## Demo Multi-usuario (Defensa)

Para que compañeros se conecten a **tu servidor** desde sus laptops en el mismo laboratorio:

### 1. Obtener tu IP local

```bash
ip addr show | grep 'inet ' | grep -v 127.0.0.1
# Ejemplo: 192.168.1.42
```

### 2. Servidor en tu máquina

```bash
nix develop --command python main.py
# Escucha en 0.0.0.0:9999 — accesible desde toda la red local
```

### 3. Compañeros se conectan desde sus laptops

**Opción A — Script Python (sin instalar nada):** Solo necesitan Python.

```bash
python3 -c "
import socket, json

def cmd(ip, a, s='GENERAL'):
    c = socket.socket(); c.settimeout(5)
    c.connect((ip, 9999))
    c.sendall(json.dumps({'action': a, 'section': s}).encode())
    r = json.loads(c.recv(4096)); c.close(); return r

ip = '192.168.1.42'  # CAMBIAR por tu IP
r = cmd(ip, 'QUERY_SEAT_MAP', 'VIP')
disp = sum(1 for row in r['seat_map'] for s in row if s == 'AVAILABLE')
print(f'VIP: {disp} libres')
r = cmd(ip, 'RESERVE', 'VIP')
if r['status'] == 'SUCCESS':
    tx = r['transaction_id']
    r2 = cmd(ip, 'CONFIRM', 'VIP')
    print(f'Comprada TX:{tx}')
else:
    print(f'Error: {r}')
"
```

**Opción B — Ejecutable con GUI completa (sin Python):** Tus compañeros abren el `.exe`, escriben tu IP y usan el mapa de asientos completo.

```powershell
# En tu máquina Windows, abrí PowerShell como Admin:
py -3 -m venv .venv-build
.venv-build\Scripts\python.exe -m pip install --upgrade pip pyinstaller pyside6
.venv-build\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name "ConcertSync-GUI" --add-data "frontend_pyside6/resources;frontend_pyside6/resources" scripts/pyside6_launcher.py

# Copiás dist/ConcertSync-GUI.exe a un USB
```

Tus compañeros solo hacen doble clic en `ConcertSync-GUI.exe`, ponen tu IP en el campo "Host" y clickean **Connect**. Ven el mapa en vivo, reservan, confirman, ven notificaciones — todo igual que si tuvieran el proyecto instalado.

> ⚠️ **Importante para Windows:**
> 1. **Firewall** — Al iniciar el servidor, Windows preguntará si permitís conexiones entrantes en el puerto 9999. Aceptá.
> 2. **WSL no funciona para esto** — Si ejecutás el servidor desde WSL, tu IP es la de WSL (no visible para los demás). Mejor corré `python main.py` directamente desde **PowerShell o cmd** (con Python instalado en Windows), así escucha en la IP real de tu máquina.
> 3. **Antivirus** — Puede marcar el `.exe` como falso positivo por ser compilado con PyInstaller. Tus compañeros pueden ignorar la advertencia.

### 4. Ver conexiones activas en el servidor

Las conexiones entrantes aparecen en los logs del servidor y en la GUI local. Cada comprador ocupa un asiento real — el sistema maneja concurrencia con locks y semáforos sin race conditions.

> **Tips para la defensa:** Abrí la GUI (`--mode both` o `desktop_launcher.py`) en un proyector para mostrar el mapa actualizándose en vivo mientras compañeros reservan desde sus máquinas.

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

## Tickets

Every CONFIRM generates a ticket file in `tickets/`:

```
tickets/
└── ticket_tkt-000001.txt   # Unicode box-drawing format
```

The ticket file contains seat, zone, date, and transaction information.  
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

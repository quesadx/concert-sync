# ConcertSync

ConcertSync is a small Python project implementing a TCP-based seat reservation server for a concert venue. It uses JSON messages over sockets, threading for concurrent clients, and shared resource management to keep seat states consistent.

## Project Structure

- `main.py`: starts the `ConcertServer` on the configured port.
- `src/server/concert_server.py`: server lifecycle, listener thread, and monitor thread.
- `src/server/listener_thread.py`: accepts incoming connections.
- `src/server/transactional_thread.py`: handles client requests for `RESERVE`, `CONFIRM`, `CANCEL`, and `QUERY`.
- `src/server/monitor_thread.py`: expires timed-out reservations and restores seats.
- `src/client/concert_client.py`: client helper for sending JSON requests to the server.
- `src/shared_resources/seat_matrix.py`: seat matrix state and section locking.
- `src/shared_resources/semaphore_manager.py`: capacity semaphores per section.
- `src/shared_resources/reservation_table.py`: in-memory transaction table with TTL.
- `src/shared_resources/global_log.py`: thread-safe event logging.
- `src/utils/enums.py`: enums for seat states, sections, and reservation statuses.
- `src/utils/config.py`: section dimensions, reservation TTL, and server port.
- `frontend_tui/`: Textual-based terminal frontend (English UI) connected to the same client-server protocol.

## How It Works

1. The server listens for TCP connections on port `9999`.
2. Each client connection is managed by a separate thread.
3. `RESERVE` changes a seat from `AVAILABLE` to `RESERVED`, records a transaction, and reserves section capacity.
4. `CONFIRM` moves reserved seats to `SOLD` and marks the transaction as confirmed.
5. `CANCEL` releases reserved seats and frees the section capacity.
6. `QUERY` returns counts of `available`, `reserved`, and `sold` seats per section.
7. A background monitor thread expires active reservations after `RESERVATION_TTL` seconds and restores seats.

## Configuration

- `src/utils/config.py` defines:
  - `SECTION_CONFIG`: rows and columns for each section
  - `RESERVATION_TTL`: 300 seconds
  - `SERVER_PORT`: 9999

## Running the Server

```bash
python main.py
```

## Running the Textual TUI

```bash
nix develop -c python -m frontend_tui
```

If you are not using Nix:

```bash
python -m frontend_tui
```

## macOS Launcher

For a Mac user, the easiest option is the bundled launcher at [run_concert_sync.command](run_concert_sync.command).

Double-click it in Finder, or run it from Terminal:

```bash
bash run_concert_sync.command
```

By default it starts the server and then opens the TUI in the same Terminal window. It creates a local `.venv` on first run and installs the small Python dependencies it needs.

## Windows Executable

If you want a single `.exe` for a Windows desktop, build it on Windows with [scripts/build_windows_exe.ps1](scripts/build_windows_exe.ps1).

The script creates `dist/ConcertSync.exe`, which starts the server and the TUI together in one console window.

## Using the Client

The client sends JSON requests to the server. Supported actions:

- `RESERVE`: reserve a seat by section, row, and column
- `CONFIRM`: confirm a reservation by transaction ID
- `CANCEL`: cancel a reservation by transaction ID
- `QUERY`: get section seat counts

Example request format:

```json
{
  "action": "RESERVE",
  "section": "VIP",
  "row": 0,
  "col": 0
}
```

## Justification and Quality

### Justificación
- Decisiones técnicas clave:
  - uso de sockets TCP para comunicación cliente-servidor
  - uso de `threading` para cada conexión y un monitor de expiración independiente
  - coordinación de recursos con `mutex` y semáforos por sección
  - controla el estado de cada asiento en `AVAILABLE`, `RESERVED` y `SOLD`
  - protege matriz, tabla de reservas y semáforos para evitar inconsistencias
  - aplica expiración TTL y manejo correcto de confirmaciones/cancelaciones

### Calidad
- Código estructurado y comentado:
  - módulo de sincronización separado (`src/synchronization`)
  - manejo de estados y transacciones en `src/server/transactional_thread.py`
  - recursos compartidos encapsulados en `src/shared_resources`



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

## Notes

- The server is designed for learning and concurrency experimentation rather than production use.
- `src/synchronization/lock_hierarcky.py` and `src/synchronization/mutex_manager.py` are part of the lock orchestration used by transactional operations.
- Logs are written to `logs/system.log`.

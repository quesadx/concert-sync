# ConcertSync — Connection Instructions

## Quick Start

### Start the server:
```bash
# Default (localhost:9999)
bash scripts/deploy.sh server

# Custom host/port
HOST=0.0.0.0 PORT=9999 bash scripts/deploy.sh server

# Background mode (for remote access)
HOST=0.0.0.0 PORT=9999 bash scripts/deploy.sh background
```

### Connect with the PySide6 client:
```bash
uv run python -m frontend_pyside6 --mode client
```

### Running the load generator (for defense):
```bash
# 100 concurrent requests
uv run python tests/load_generator.py --host SERVER_IP --port 9999 --requests 100 --conflicts

# Stress test (500 concurrent requests)
uv run python tests/load_generator.py --host SERVER_IP --port 9999 --requests 500 --conflicts

# Health check
HOST=SERVER_IP bash scripts/deploy.sh health
```

## Remote Access Setup

### Server (on the deployment machine):
```bash
# Allow incoming connections on port 9999
sudo ufw allow 9999/tcp

# Start server listening on all interfaces
HOST=0.0.0.0 PORT=9999 bash scripts/deploy.sh background
```

### Client (from any machine):
```bash
uv run python -m frontend_pyside6 --host SERVER_IP --port 9999
```

## Protocol

The system uses JSON-over-TCP on port 9999.

### Supported actions:
| Action | Description |
|--------|-------------|
| `QUERY` | Get seat availability by section |
| `QUERY_SEAT_MAP` | Get full seat state matrix |
| `RESERVE` | Reserve a single seat |
| `RESERVE_SELECTED` | Reserve batch of seats atomically |
| `CONFIRM` | Confirm reservation (mark SOLD) |
| `CANCEL` | Cancel reservation (mark AVAILABLE) |

### Quick test with netcat:
```bash
# Query seat map
echo '{"action": "QUERY"}' | nc SERVER_IP 9999

# Reserve a seat
echo '{"action": "RESERVE", "section": "VIP", "row": 0, "col": 0, "user_id": "test"}' | nc SERVER_IP 9999
```

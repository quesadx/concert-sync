# Technology Stack

**Analysis Date:** 2026-06-04

## Languages

**Primary:**
- Python 3.14 - Entire codebase (server, client, TUI frontend, tests, scripts)

**Secondary:**
- None - The application is pure Python. (Node.js/pnpm appear in `flake.nix` only as tooling for GSD/OpenCode, not for the application.)

## Runtime

**Environment:**
- Python 3.14 (pinned in `.python-version`)
- Nix flake (`flake.nix`) provides reproducible dev environment with nixpkgs unstable

**Package Manager:**
- uv (primary, lockfile: `uv.lock` committed)
- pip + venv (fallback in `scripts/run.sh`)

## Frameworks

**Core:**
- None — The server uses raw `socket` (TCP) with `threading` for concurrency. No web framework, ASGI, or HTTP layer.

**Frontend (TUI):**
- Textual >= 0.70.0 - Terminal UI for seat reservation client (`frontend_tui/app.py`)
  - Part of the `tui` dependency group (optional, not core)
  - Depends on: `rich` (bundled with Textual for styling)

**Testing:**
- pytest >= 9.0.3 - Test runner and fixture support
  - Config in `pyproject.toml`: `[tool.pytest.ini_options]` sets `pythonpath = ["."]`
  - No plugins detected beyond core pytest

**Build/Dev:**
- black >= 26.3.1 - Code formatter
- flake8 >= 7.3.0 - Linter
- Nix (`flake.nix`) - Reproducible development shells

## Key Dependencies

**Critical (application runtime):**
- *None beyond Python standard library.* The entire server and client use only `socket`, `threading`, `json`, `uuid`, `time`, `dataclasses`, `enum`, `pathlib`, `collections`, `contextlib`, and `typing` from the standard library.

**Infrastructure (dev only):**
- black 26.3.1 - Code formatting enforcement
- flake8 7.3.0 - Python linting
- pytest 9.0.3 - Test framework

**TUI (optional):**
- textual >= 0.70.0 - Terminal user interface framework

## Configuration

**Environment:**
- No `.env` files detected
- All configuration is in-code at `src/utils/config.py`:
  - `SERVER_PORT = 9999` — TCP port for server
  - `RESERVATION_TTL = 300` — Reservation timeout in seconds (5 minutes)
  - `SECTION_CONFIG` — Seat matrix dimensions per section:
    - VIP: 5 rows × 10 cols (50 seats)
    - PREFERENTIAL: 10 rows × 15 cols (150 seats)
    - GENERAL: 20 rows × 20 cols (400 seats)

**Build:**
- `pyproject.toml` — Project metadata, dependency groups, pytest config
- `flake.nix` + `flake.lock` — Nix development environment
- `.python-version` — Python version pin (3.14)
- `.gitignore` — Standard Python gitignore (venv, __pycache__, logs, etc.)

**Platform Specific:**
- `scripts/build_windows_exe.ps1` — Windows packaging (PowerShell)
- `scripts/run.sh` — Cross-platform run script (server, tui, both, test modes)
- `desktop_launcher.py` — Single-process launcher that runs server + TUI together

## Platform Requirements

**Development:**
- Python 3.14 (or 3.13+ likely compatible)
- uv package manager (recommended) or pip + venv
- Optional: Nix with flakes enabled for `nix develop`

**Production:**
- Python 3.14 runtime
- Local filesystem access (for logs at `logs/system.log`)
- No external services required — fully self-contained
- Port 9999 available for TCP

---

*Stack analysis: 2026-06-04*

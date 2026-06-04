# Technology Stack

**Analysis Date:** 2026-06-01

## Languages

**Primary:**
- Python 3.14+ — All application code (server, client, shared resources, utilities, TUI)

**Secondary:**
- Nix expression language — Dev shell in `flake.nix`
- Shell (Bash) — Scripts in `scripts/`

## Runtime

**Environment:**
- Python 3.14 (specified in `.python-version`)
- Requires-python: `>=3.14` (in `uv.lock`)

**Package Manager:**
- [uv](https://docs.astral.sh/uv/) (v1+ based on `uv.lock` revision 3)
- Lockfile: `uv.lock` (committed, revision 3)
- Dependency groups: `dev`, `tui` (in `pyproject.toml`)

## Frameworks

**Core:**
- No web framework — uses raw `socket` library (TCP server)
- No async framework — threading-based concurrency via `threading.Thread`

**TUI:**
- [Textual](https://textual.textualize.io/) >=0.70.0 — Terminal UI framework for the client frontend (`frontend_tui/`)

**Testing:**
- [pytest](https://docs.pytest.org/) >=9.0.3 — Test runner (`tests/`)
- Config: `[tool.pytest.ini_options]` in `pyproject.toml` (pythonpath = ["."])

**Dev/Lint:**
- [black](https://black.readthedocs.io/) >=26.3.1 — Formatter (in dev deps)
- [flake8](https://flake8.pycqa.org/) >=7.3.0 — Linter (in dev deps)

## Key Dependencies

**Critical:**
- `textual>=0.70.0` (`frontend_tui/app.py`) — Provides `App`, `ComposeResult`, `DataTable`, `Input`, `Select`, `Button`, `RichLog`, `Header`, `Footer`, `Static`, `Horizontal`, `Vertical`, `Binding` widgets
- Built-in `socket` — TCP server/client communication
- Built-in `threading` — Concurrency: `Thread`, `Lock`, `RLock`, `Semaphore`, `Condition`, `Barrier`
- Built-in `json` — Protocol serialization
- Built-in `uuid` — Transaction ID generation

**Infrastructure:**
- `dataclasses` (stdlib) — Data models (`Reservation`, `TrackedSession`)
- `enum` (stdlib) — Enums (`Section`, `SeatState`, `ReservationStatus`)
- `contextlib` (stdlib) — `@contextmanager` for lock hierarchy
- `collections.defaultdict` (stdlib) — Thread-local seat grouping
- `pathlib.Path` (stdlib) — File path handling

## Configuration

**Environment:**
- No `.env` files detected — no environment variable configuration
- Server port and seat dimensions hardcoded in `src/utils/config.py`

**Build:**
- `pyproject.toml` — Project metadata, test config, dependency groups
- `uv.lock` — Locked dependency versions
- `flake.nix` / `flake.lock` — Nix dev shell (Python 3.14, uv, pytest, black, flake8, textual, opencode, gsd, pnpm)

## Platform Requirements

**Development:**
- Python 3.14+
- uv package manager (recommended)
- Nix (optional, for `nix develop` dev shell)

**Production:**
- Python 3.14+
- Direct execution via `python main.py` or `python -m frontend_tui`

---

*Stack analysis: 2026-06-01*

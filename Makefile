.PHONY: test build build-server build-client build-all run-server run-client clean

test:
	uv sync --group dev --group pyside6 && uv run pytest tests/

# ── macOS builds (native arm64) ───────────────────────────────────────
build:
	bash scripts/build_mac.sh both

build-server:
	bash scripts/build_mac.sh server

build-client:
	bash scripts/build_mac.sh client

# ── Server build (current platform: Linux/macOS) ─────────────────────
# Uses uv + PyInstaller to produce a standalone binary for this machine.
# For Windows server .exe, run scripts/build_server.bat on a Windows PC.
build-server-local:
	uv sync && uv run pyinstaller concert_sync_server.spec --noconfirm --clean

# ── Client build (current platform: Linux/macOS) ─────────────────────
build-client-local:
	uv sync --group pyside6 && uv run pyinstaller concert_sync.spec --noconfirm --clean

# ── All builds for current platform ──────────────────────────────────
build-all: build-server-local build-client-local

run-server:
	uv run python main.py

run-client:
	uv sync --group pyside6 && uv run python -m frontend_pyside6 --mode client

run-dashboard:
	uv sync --group pyside6 && uv run python -m frontend_pyside6 --mode dashboard

clean:
	rm -rf build/ dist/ .venv-build-mac/

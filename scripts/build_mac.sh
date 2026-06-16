#!/usr/bin/env bash
# ============================================================================
#  ConcertSync — macOS ARM Build Script
#  Builds a standalone ConcertSync Mach-O executable with PyInstaller.
#
#  How to use:
#    1. git pull  (get latest code from repo)
#    2. Run from Terminal:
#         bash scripts/build_mac.sh
#
#  Output: dist/ConcertSync
#
#  The end-user needs nothing — no Python, no PySide6, no dependencies.
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "========================================"
echo " ConcertSync — macOS ARM Build"
echo "========================================"
echo ""
echo "Root: $ROOT"

# ── Step 1: Check for Python ────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python 3 not found."
    echo "Install Python 3.14+ from https://www.python.org/downloads/"
    echo "Or: brew install python@3.14"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[OK] Python $PYTHON_VERSION found."

# ── Check architecture ───────────────────────────────────────────────────────
ARCH=$(uname -m)
if [ "$ARCH" != "arm64" ]; then
    echo "[WARNING] This machine is $ARCH, not arm64."
    echo "The .spec targets arm64 — cross-compilation may not work."
    echo "Build on an Apple Silicon Mac for native arm64 output."
    echo ""
    read -rp "Continue anyway? [y/N] " REPLY
    if [ "$REPLY" != "y" ] && [ "$REPLY" != "Y" ]; then
        exit 1
    fi
fi

# ── Step 2: Create build venv ───────────────────────────────────────────────
if [ ! -d ".venv-build-mac" ]; then
    echo "[BUILD] Creating build venv..."
    python3 -m venv .venv-build-mac
fi

echo "[BUILD] Activating venv and upgrading pip..."
.venv-build-mac/bin/python -m pip install --upgrade pip > /dev/null 2>&1

# ── Step 3: Install build dependencies ──────────────────────────────────────
echo "[BUILD] Installing PyInstaller and PySide6..."
.venv-build-mac/bin/python -m pip install pyinstaller 'pyside6>=6.8'

if [ $? -ne 0 ]; then
    echo "[ERROR] pip install failed."
    exit 1
fi
echo "[OK] Dependencies installed."

# ── Step 4: Build executable ────────────────────────────────────────────────
echo "[BUILD] Running PyInstaller..."
.venv-build-mac/bin/python -m PyInstaller concert_sync_mac.spec --noconfirm --clean

if [ $? -ne 0 ]; then
    echo "[ERROR] PyInstaller build failed."
    exit 1
fi

# ── Done ────────────────────────────────────────────────────────────────────
EXE_PATH="$ROOT/dist/ConcertSync"
if [ -f "$EXE_PATH" ]; then
    SIZE=$(stat -f%z "$EXE_PATH" 2>/dev/null || stat -c%s "$EXE_PATH" 2>/dev/null)
    # Human-readable size
    if [ "$SIZE" -gt 1048576 ]; then
        HR_SIZE="$(echo "scale=1; $SIZE / 1048576" | bc) MB"
    elif [ "$SIZE" -gt 1024 ]; then
        HR_SIZE="$(echo "scale=1; $SIZE / 1024" | bc) KB"
    else
        HR_SIZE="$SIZE bytes"
    fi

    echo ""
    echo "========================================"
    echo "  SUCCESS"
    echo "========================================"
    echo "  Output: $EXE_PATH"
    echo "  Size:   $HR_SIZE ($SIZE bytes)"
    echo ""
    echo "  To distribute: copy dist/ConcertSync to any Apple Silicon Mac."
    echo "  No Python or PySide6 required. Just double-click."
    echo ""
    echo "  First-run note: right-click > Open (Gatekeeper bypass)"
    echo "  Or: xattr -cr dist/ConcertSync && ./dist/ConcertSync"
    echo "========================================"
else
    # macOS onefile with console=False may produce .app bundle as well
    APP_PATH="$ROOT/dist/ConcertSync.app"
    if [ -d "$APP_PATH" ]; then
        echo ""
        echo "========================================"
        echo "  SUCCESS"
        echo "========================================"
        echo "  Output: $APP_PATH"
        echo ""
        echo "  To distribute: copy dist/ConcertSync.app to any Apple Silicon Mac."
        echo "  No Python or PySide6 required. Just double-click."
        echo "========================================"
    else
        echo "[ERROR] Build output not found at $EXE_PATH or $APP_PATH"
        exit 1
    fi
fi

#!/usr/bin/env bash
# ============================================================================
#  ConcertSync — macOS ARM Build Script
#  Builds standalone Mach-O executables with PyInstaller.
#
#  How to use:
#    1. git pull  (get latest code from repo)
#    2. Run from Terminal:
#         bash scripts/build_mac.sh             # build both
#         bash scripts/build_mac.sh server      # server only
#         bash scripts/build_mac.sh client      # client only
#
#  Outputs:
#    dist/ConcertSyncServer    — server CLI executable
#    dist/ConcertSync          — client GUI executable
#
#  The end-user needs nothing — no Python, no PySide6, no dependencies.
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TARGET="${1:-both}"

echo "========================================"
echo " ConcertSync — macOS ARM Build"
echo "========================================"
echo ""
echo "Root:    $ROOT"
echo "Target:  $TARGET"
echo "Arch:    $(uname -m)"
echo ""

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
    echo "The .spec files target arm64 — cross-compilation may not work."
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
echo "[BUILD] Installing PyInstaller..."
.venv-build-mac/bin/python -m pip install pyinstaller

if [ $? -ne 0 ]; then
    echo "[ERROR] pip install failed."
    exit 1
fi

build_server() {
    echo ""
    echo "────────────────────────────────────────"
    echo " Building ConcertSyncServer (CLI)"
    echo "────────────────────────────────────────"
    .venv-build-mac/bin/python -m PyInstaller concert_sync_server_mac.spec --noconfirm --clean

    if [ $? -ne 0 ]; then
        echo "[ERROR] Server build failed."
        exit 1
    fi

    local exe_path="$ROOT/dist/ConcertSyncServer"
    if [ -f "$exe_path" ]; then
        local size
        size=$(stat -f%z "$exe_path" 2>/dev/null || stat -c%s "$exe_path" 2>/dev/null)
        local hr_size
        if [ "$size" -gt 1048576 ]; then
            hr_size="$(echo "scale=1; $size / 1048576" | bc 2>/dev/null || echo "$size") MB"
        elif [ "$size" -gt 1024 ]; then
            hr_size="$(echo "scale=1; $size / 1024" | bc 2>/dev/null || echo "$size") KB"
        else
            hr_size="$size bytes"
        fi
        echo "  [OK] dist/ConcertSyncServer — $hr_size"
    else
        echo "[ERROR] Server build output not found at $exe_path"
        exit 1
    fi
}

build_client() {
    echo ""
    echo "────────────────────────────────────────"
    echo " Building ConcertSync (GUI)"
    echo "────────────────────────────────────────"
    .venv-build-mac/bin/python -m pip install 'pyside6>=6.8'

    if [ $? -ne 0 ]; then
        echo "[ERROR] PySide6 install failed."
        exit 1
    fi

    .venv-build-mac/bin/python -m PyInstaller concert_sync_client_mac.spec --noconfirm --clean

    if [ $? -ne 0 ]; then
        echo "[ERROR] Client build failed."
        exit 1
    fi

    local exe_path="$ROOT/dist/ConcertSync"
    local app_path="$ROOT/dist/ConcertSync.app"
    if [ -f "$exe_path" ]; then
        local size
        size=$(stat -f%z "$exe_path" 2>/dev/null || stat -c%s "$exe_path" 2>/dev/null)
        local hr_size
        if [ "$size" -gt 1048576 ]; then
            hr_size="$(echo "scale=1; $size / 1048576" | bc 2>/dev/null || echo "$size") MB"
        elif [ "$size" -gt 1024 ]; then
            hr_size="$(echo "scale=1; $size / 1024" | bc 2>/dev/null || echo "$size") KB"
        else
            hr_size="$size bytes"
        fi
        echo "  [OK] dist/ConcertSync — $hr_size"
    elif [ -d "$app_path" ]; then
        echo "  [OK] dist/ConcertSync.app"
    else
        echo "[ERROR] Client build output not found at $exe_path or $app_path"
        exit 1
    fi
}

# ── Step 4: Build ───────────────────────────────────────────────────────────
case "$TARGET" in
    server)
        build_server
        ;;
    client)
        build_client
        ;;
    both)
        build_server
        build_client
        ;;
    *)
        echo "Usage: $0 [server|client|both]"
        exit 1
        ;;
esac

# ── Done ────────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  SUCCESS"
echo "========================================"
echo ""
echo "  Outputs:"
for f in dist/ConcertSyncServer dist/ConcertSync dist/ConcertSync.app; do
    if [ -f "$f" ]; then
        echo "    $f"
    elif [ -d "$f" ]; then
        echo "    $f"
    fi
done
echo ""
echo "  Server usage:  ./dist/ConcertSyncServer --port 9999"
echo "  Client usage:  double-click dist/ConcertSync"
echo ""
echo "  First-run note (Gatekeeper bypass):"
echo "    xattr -cr dist/"
echo ""
echo "========================================"

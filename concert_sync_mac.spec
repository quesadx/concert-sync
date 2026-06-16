# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for ConcertSync PySide6 GUI — macOS ARM64
# ===========================================================
# Build command:
#   pyinstaller concert_sync_mac.spec --noconfirm --clean
#
# The output is dist/ConcertSync — a standalone Mach-O executable.
# The end-user needs NOTHING: no Python, no PySide6, no dependencies.
#
# Why a separate .spec for macOS:
#   - target_arch pinned to arm64 for Apple Silicon
#   - no win_* flags (Windows-only)
#   - no .exe extension on output

import sys
from pathlib import Path

sys.setrecursionlimit(5000)

block_cipher = None

# ── Resources to bundle inside the executable ──────────────────────────
datas = [
    ("frontend_pyside6/resources/styles.qss", "frontend_pyside6/resources"),
]

# ── Analysis ───────────────────────────────────────────────────────────
a = Analysis(
    ["scripts/pyside6_entry.py"],
    pathex=[str(Path.cwd())],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
    ],
    excludes=[
        "frontend_tui",
        "textual",
        "tests",
        "tkinter",
        "unittest",
        "PIL",
        "Pillow",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "IPython",
        "setuptools",
        "pip",
    ],
    cipher=block_cipher,
    noarchive=False,
)

# ── Byte-code archive ──────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── Single-file executable (onefile mode) ──────────────────────────────
# console=False means no terminal window on macOS.
# target_arch='arm64' locks the build to Apple Silicon.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ConcertSync",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
    contents_directory=".",
)

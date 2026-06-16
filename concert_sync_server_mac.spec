# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for ConcertSync Server — macOS ARM64
# =======================================================
# Build command:
#   pyinstaller concert_sync_server_mac.spec --noconfirm --clean
#
# The output is dist/ConcertSyncServer — a standalone Mach-O executable.
# The end-user needs NOTHING: no Python, no dependencies.
#
# Why a separate .spec for macOS:
#   - target_arch pinned to arm64 for Apple Silicon
#   - no win_* flags (Windows-only)
#   - console=True (server is a CLI application)

import sys
from pathlib import Path

sys.setrecursionlimit(5000)

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[str(Path.cwd())],
    binaries=[],
    datas=[],
    hiddenimports=[],
    excludes=[
        # GUI frameworks not used by server
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "frontend_pyside6",
        "frontend_tui",
        "textual",
        # Test code
        "tests",
        # Common bloat
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

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ConcertSyncServer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
    contents_directory=".",
)

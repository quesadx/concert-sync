# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for ConcertSync Server — Windows
# ===================================================
# Build command:
#   pyinstaller concert_sync_server.spec --noconfirm --clean
#
# The output is dist/ConcertSyncServer.exe — a standalone executable.
# The end-user needs NOTHING: no Python, no dependencies.
#
# Why a separate .spec for the server:
#   - console=True (server is a CLI application — shows terminal)
#   - excludes PySide6 and frontend_pyside6 (GUI not needed)
#   - no datas/resources to bundle

import sys
from pathlib import Path

sys.setrecursionlimit(5000)

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[str(Path.cwd())],  # cwd = project root (build scripts cd there)
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
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# console=True  → shows terminal window (server is a CLI app)
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
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory=".",
)

# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for ConcertSync PySide6 GUI
# =============================================
# Build command:
#   pyinstaller concert_sync.spec --noconfirm --clean
#
# The output is dist/ConcertSync.exe — a standalone executable.
# The end-user needs NOTHING: no Python, no PySide6, no dependencies.
#
# Why a .spec instead of CLI flags:
#   - deterministic hidden import list
#   - proper excludes to shrink binary
#   - reproducible builds

import sys
from pathlib import Path

sys.setrecursionlimit(5000)

block_cipher = None

# ── Resources to bundle inside the .exe ──────────────────────────────
# styles.qss is loaded at runtime by main_window.py and server_dashboard.py
# via Path(__file__).parent / "resources" / "styles.qss".
# PyInstaller extracts these files under sys._MEIPASS so the relative
# path resolution works automatically — no code changes needed.
# Note: gnome_palette.py is Python code discovered automatically by the
# import scanner; no need to add it as a data file.
datas = [
    ("frontend_pyside6/resources/styles.qss", "frontend_pyside6/resources"),
]

# ── Analysis ─────────────────────────────────────────────────────────
a = Analysis(
    ["scripts/pyside6_entry.py"],
    pathex=[str(Path.cwd())],  # cwd = project root (build scripts cd there)
    binaries=[],
    datas=datas,
    hiddenimports=[
        # ── PySide6 (Qt for Python) ────────────────────────────────
        # These are the ONLY third-party dependencies. Everything else
        # is Python stdlib (socket, json, threading, uuid, time, etc.)
        # and project-internal modules discovered automatically.
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
    ],
    excludes=[
        # ── Not needed in PySide6 GUI build ────────────────────────
        "frontend_tui",  # Textual TUI (alternative frontend)
        "textual",  # TUI framework (not used here)
        "tests",  # never ship test code
        # ── Common bloat to exclude ────────────────────────────────
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

# ── Byte-code archive ────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── Single-file executable (onefile mode) ────────────────────────────
# --windowed (console=False) means no terminal window on Windows.
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
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory=".",
)

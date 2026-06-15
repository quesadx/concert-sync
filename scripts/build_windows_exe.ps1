<#
.SYNOPSIS
    Build a standalone ConcertSync.exe for Windows with PyInstaller.
.DESCRIPTION
    Creates an isolated .venv-build, installs PyInstaller + PySide6,
    and compiles a single-file executable.  The end-user needs NOTHING
    — no Python, no PySide6, no dependencies.

    Usage:
        1. git pull
        2. .\scripts\build_windows_exe.ps1
        3. Grab dist\ConcertSync.exe

    Requirements:
        - Python 3.14+ (Windows launcher "py" must be in PATH)
        - Internet connection (first run downloads PySide6 ~100 MB)
.NOTES
    Version: 2.0 — Uses .spec file for deterministic builds.
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " ConcertSync — Windows Build (PowerShell)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Root: $root"

# ── Step 1: Check Python ──────────────────────────────────────────────────────
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw @"
Python launcher 'py' was not found.
Install Python 3.14+ from https://www.python.org/downloads/
Make sure to check 'Add Python to PATH' during installation.
"@
}
Write-Host "[OK] Python launcher found."

# ── Step 2: Create build venv ─────────────────────────────────────────────────
if (-not (Test-Path ".venv-build")) {
    Write-Host "[BUILD] Creating build venv..."
    py -3 -m venv .venv-build
}

$python = "$root\.venv-build\Scripts\python.exe"
$pip = "$root\.venv-build\Scripts\pip.exe"

Write-Host "[BUILD] Upgrading pip..."
& $python -m pip install --upgrade pip | Out-Null

# ── Step 3: Install build dependencies ────────────────────────────────────────
Write-Host "[BUILD] Installing PyInstaller and PySide6..."
& $pip install pyinstaller "pyside6>=6.8"
if ($LASTEXITCODE -ne 0) {
    throw "pip install failed."
}
Write-Host "[OK] Dependencies installed."

# ── Step 4: Build .exe via .spec ─────────────────────────────────────────────
Write-Host "[BUILD] Running PyInstaller with concert_sync.spec ..."
& $python -m PyInstaller concert_sync.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

# ── Done ──────────────────────────────────────────────────────────────────────
$exe = Get-Item "$root\dist\ConcertSync.exe"
$size = "{0:N0}" -f $exe.Length

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  SUCCESS" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Output: $($exe.FullName)"
Write-Host "  Size:   $size bytes"
Write-Host ""
Write-Host "  To distribute: copy dist\ConcertSync.exe to any Windows machine."
Write-Host "  No Python or PySide6 required.  Just double-click."
Write-Host "========================================" -ForegroundColor Green

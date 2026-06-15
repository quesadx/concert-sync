@echo off
REM ============================================================================
REM  ConcertSync — Windows Build Script (Batch)
REM  Builds a standalone ConcertSync.exe with PyInstaller.
REM
REM  How to use:
REM    1. git pull  (get latest code from repo)
REM    2. Double-click this file or run from cmd:
REM         scripts\build.bat
REM
REM  Output: dist\ConcertSync.exe
REM
REM  The end-user needs nothing — no Python, no PySide6, no dependencies.
REM ============================================================================
setlocal enabledelayedexpansion

cd /d "%~dp0.."
set ROOT=%CD%

echo ========================================
echo  ConcertSync — Windows Build
echo ========================================
echo.
echo Root: %ROOT%

REM ── Step 1: Check for Python ────────────────────────────────────────────────
where py >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python launcher 'py' not found.
    echo Install Python 3.14+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [OK] Python launcher found.

REM ── Step 2: Create build venv ───────────────────────────────────────────────
if not exist ".venv-build" (
    echo [BUILD] Creating build venv...
    py -3 -m venv .venv-build
)

echo [BUILD] Activating venv and upgrading pip...
.venv-build\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1

REM ── Step 3: Install build dependencies ──────────────────────────────────────
echo [BUILD] Installing PyInstaller and PySide6...
.venv-build\Scripts\python.exe -m pip install pyinstaller pyside6>=6.8

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)
echo [OK] Dependencies installed.

REM ── Step 4: Build .exe ──────────────────────────────────────────────────────
echo [BUILD] Running PyInstaller...
.venv-build\Scripts\python.exe -m PyInstaller concert_sync.spec --noconfirm --clean

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo ========================================
echo  SUCCESS
echo ========================================
echo  Output: %ROOT%\dist\ConcertSync.exe
echo  Size:
for %%I in ("%ROOT%\dist\ConcertSync.exe") do echo    %%~zI bytes
echo.
echo  To distribute: copy dist\ConcertSync.exe to any Windows machine.
echo  No Python or PySide6 required.
echo ========================================

pause

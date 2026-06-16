@echo off
REM ============================================================================
REM  ConcertSync — Windows Server Build Script (Batch)
REM  Builds a standalone ConcertSyncServer.exe with PyInstaller.
REM
REM  How to use:
REM    1. git pull  (get latest code from repo)
REM    2. Double-click this file or run from cmd:
REM         scripts\build_server.bat
REM
REM  Output: dist\ConcertSyncServer.exe
REM
REM  The end-user needs nothing — no Python, no dependencies.
REM  Just run:  ConcertSyncServer.exe --port 9999
REM ============================================================================
setlocal enabledelayedexpansion

cd /d "%~dp0.."
set ROOT=%CD%

echo ========================================
echo  ConcertSync Server — Windows Build
echo ========================================
echo.
echo Root: %ROOT%
echo.

REM ── Step 1: Check for Python ────────────────────────────────────────────────
where py >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python launcher 'py' not found.
    echo Install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [OK] Python launcher found.

REM ── Step 2: Clean old build artifacts ───────────────────────────────────────
echo [CLEAN] Removing old build caches and output...
if exist "dist\ConcertSyncServer.exe" (
    echo   Removing dist\ConcertSyncServer.exe ...
    del /q "dist\ConcertSyncServer.exe" 2>nul
)
if exist "build" (
    echo   Removing build\ ...
    rmdir /s /q "build"
)
REM Remove stale .pyc cache files so PyInstaller picks up the latest code
for /d /r "." %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" 2>nul
del /s /q "*.pyc" 2>nul
echo [OK] Cleanup done.
echo.

REM ── Step 3: Create build venv ───────────────────────────────────────────────
if not exist ".venv-build-server" (
    echo [BUILD] Creating build venv...
    py -3 -m venv --clear .venv-build-server
)

echo [BUILD] Upgrading pip...
.venv-build-server\Scripts\python.exe -m pip install --upgrade pip
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] pip upgrade failed, continuing anyway...
)

REM ── Step 4: Install build dependencies ──────────────────────────────────────
REM Server only needs PyInstaller — no PySide6, no GUI deps.
echo [BUILD] Installing/upgrading PyInstaller...
.venv-build-server\Scripts\python.exe -m pip install --upgrade pyinstaller

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)
echo [OK] PyInstaller installed.
echo.

REM Show what we're building
echo [BUILD] Project version and latest commits:
git log --oneline -3 2>nul
echo.

REM ── Step 5: Build .exe ──────────────────────────────────────────────────────
echo [BUILD] Running PyInstaller...
.venv-build-server\Scripts\python.exe -m PyInstaller concert_sync_server.spec --noconfirm --clean

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo ========================================
echo  SUCCESS
echo ========================================
echo  Output: %ROOT%\dist\ConcertSyncServer.exe
echo  Size:
for %%I in ("%ROOT%\dist\ConcertSyncServer.exe") do echo    %%~zI bytes
echo.
echo  To distribute: copy dist\ConcertSyncServer.exe to any Windows machine.
echo  No Python required.
echo.
echo  Usage:
echo    ConcertSyncServer.exe --port 9999
echo    ConcertSyncServer.exe --host 0.0.0.0 --port 9999
echo ========================================

pause

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
if exist "dist" (
    echo   Removing dist\ ...
    rmdir /s /q "dist"
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
if not exist ".venv-build" (
    echo [BUILD] Creating build venv...
    py -3 -m venv --clear .venv-build
)

echo [BUILD] Upgrading pip...
.venv-build\Scripts\python.exe -m pip install --upgrade pip
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] pip upgrade failed, continuing anyway...
)

REM ── Step 4: Install build dependencies ──────────────────────────────────────
echo [BUILD] Installing/upgrading PyInstaller and PySide6...
.venv-build\Scripts\python.exe -m pip install --upgrade pyinstaller "pyside6>=6.8"

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)
echo [OK] Dependencies installed.
echo.

REM Show what we're building
echo [BUILD] Project version and latest commits:
git log --oneline -3 2>nul
echo.

REM ── Step 5: Build .exe ──────────────────────────────────────────────────────
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

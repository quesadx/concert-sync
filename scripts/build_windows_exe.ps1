$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install Python 3 for Windows first."
}

py -3 -m venv .venv-build
.venv-build\Scripts\python.exe -m pip install --upgrade pip pyinstaller textual | Out-Null

pyinstaller --noconfirm --clean --onefile --console --name ConcertSync `
    --add-data "frontend_tui\styles.tcss;frontend_tui" `
    desktop_launcher.py

Write-Host "Built dist\ConcertSync.exe"
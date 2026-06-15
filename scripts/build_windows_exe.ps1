$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install Python 3 for Windows first."
}

py -3 -m venv .venv-build
.venv-build\Scripts\python.exe -m pip install --upgrade pip pyinstaller pyside6 | Out-Null

pyinstaller --noconfirm --clean --onefile --windowed --name "ConcertSync-GUI" `
    --add-data "frontend_pyside6/resources;frontend_pyside6/resources" `
    --hidden-import "PySide6.QtCore" `
    --hidden-import "PySide6.QtGui" `
    --hidden-import "PySide6.QtWidgets" `
    --hidden-import "src.client.concert_client" `
    --hidden-import "src.utils.config" `
    --hidden-import "src.utils.enums" `
    --hidden-import "src.utils.protocol_validator" `
    --hidden-import "src.utils.error_responses" `
    scripts/pyside6_launcher.py

Write-Host ""
Write-Host "========================================"
Write-Host "Built dist\ConcertSync-GUI.exe"
Write-Host "========================================"
Write-Host "Tus companeros solo necesitan ese .exe."
Write-Host "Al abrirlo, escriben tu IP y conectan."

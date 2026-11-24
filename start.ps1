$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

# Repair an existing but incomplete environment instead of skipping installation.
& $python -c "import fastapi, uvicorn, fitz, PIL, edge_tts, playwright, requests" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing Python dependencies..."
    & $python -m pip install --upgrade pip
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
}

& $python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(); b.close(); p.stop()" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing Playwright Chromium..."
    & $python -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw "playwright install failed" }
}

$env:PAPERRELAY_PORT = if ($env:PAPERRELAY_PORT) { $env:PAPERRELAY_PORT } else { "8787" }
Write-Host "Starting PaperRelay on http://127.0.0.1:$env:PAPERRELAY_PORT/ (Ctrl+C to stop)"
& $python run.py

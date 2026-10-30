$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (-not (Test-Path ".venv")) { py -3 -m venv .venv }
$Python = Join-Path (Get-Location) ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt
if (-not (Test-Path ".env")) { Copy-Item .env.example .env }
$HostAddress = if ($env:SDLC_HOST) { $env:SDLC_HOST } else { "127.0.0.1" }
$Port = if ($env:SDLC_PORT) { $env:SDLC_PORT } else { "8000" }
& $Python -m uvicorn backend.app:app --host $HostAddress --port $Port

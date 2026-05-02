<#
    Dev mode — runs core and dashboard without Docker for fast iteration.
    Requires Python 3.12 + Node 20 installed locally.
#>

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition | Split-Path -Parent
Set-Location $ROOT

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtualenv..." -ForegroundColor Cyan
    python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1
pip install -r core/requirements.txt

Push-Location dashboard
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing pnpm dependencies..." -ForegroundColor Cyan
    if (Get-Command pnpm -ErrorAction SilentlyContinue) {
        pnpm install
    } else {
        npm install
    }
}
Pop-Location

Write-Host "`nStarting core (port 8000)..." -ForegroundColor Cyan
$core = Start-Process -PassThru -NoNewWindow powershell -ArgumentList "-NoProfile","-Command",". .\.venv\Scripts\Activate.ps1; uvicorn core.main:app --reload --port 8000"

Write-Host "Starting dashboard (port 3000)..." -ForegroundColor Cyan
$dash = Start-Process -PassThru -NoNewWindow powershell -ArgumentList "-NoProfile","-Command","cd dashboard; pnpm dev"

Write-Host "`nBoth services launched." -ForegroundColor Green
Write-Host "  Core:      http://localhost:8000/docs"
Write-Host "  Dashboard: http://localhost:3000"
Write-Host "`nPress Ctrl+C to stop both."

try {
    Wait-Process -Id $core.Id, $dash.Id
} finally {
    Stop-Process -Id $core.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $dash.Id -Force -ErrorAction SilentlyContinue
}

# Start the API (which also serves the web panel) and the face-service.
# Safe to run repeatedly: anything already running is left alone.
param([switch]$NoBrowser)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "common.ps1")

if (-not (Test-Path -LiteralPath (Join-Path $root ".env"))) {
    Write-Host "سامانه هنوز راه‌اندازی نشده؛ لطفاً «راه‌اندازی» را اجرا کنید." -ForegroundColor Yellow
    exit 1
}

$python = Get-AppPython -Root $root
if (-not $python) {
    Write-Host "موتور پایتون پیدا نشد؛ لطفاً «راه‌اندازی» را اجرا کنید." -ForegroundColor Yellow
    exit 1
}

New-Item -ItemType Directory -Force -Path (Join-Path $root "data\logs") | Out-Null

$apiPort = Get-EnvValue -Root $root -Key "API_PORT" -Default "8000"
$apiHost = Get-EnvValue -Root $root -Key "API_HOST" -Default "0.0.0.0"

$null = Start-Service-Process `
    -Name "api" `
    -Root $root `
    -Python $python `
    -ServiceDirectory (Join-Path $root "services\api") `
    -Arguments @("-m", "uvicorn", "app.main:app", "--host", $apiHost, "--port", $apiPort)

# The face-service asks the API for its camera list, so it starts second.
$null = Start-Service-Process `
    -Name "face-service" `
    -Root $root `
    -Python $python `
    -ServiceDirectory (Join-Path $root "services\face-service") `
    -Arguments @("-m", "app.main")

# Loading the recognition models takes a few seconds on first start; waiting
# for /health means the browser does not open onto a connection error.
$panel = "http://localhost:$apiPort"
$ready = $false
foreach ($attempt in 1..30) {
    Start-Sleep -Seconds 1
    try {
        if ((Invoke-RestMethod "$panel/health" -TimeoutSec 3).status -eq "ok") { $ready = $true; break }
    } catch { }
}

Write-Host ""
if ($ready) {
    Write-Host "سامانه آماده است." -ForegroundColor Green
} else {
    Write-Host "سامانه هنوز پاسخ نمی‌دهد؛ چند لحظه صبر کنید یا «وضعیت» را ببینید." -ForegroundColor Yellow
}
Write-Host "پنل مدیریت: $panel   (نام کاربری admin / رمز admin)" -ForegroundColor White
Write-Host "توقف سامانه: میان‌بر «توقف» در منوی استارت" -ForegroundColor DarkGray

if ($ready -and -not $NoBrowser) { Start-Process $panel }

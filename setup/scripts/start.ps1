# Start the API (which also serves the web panel) and the face-service.
# Safe to run repeatedly: anything already running is left alone.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "common.ps1")

if (-not (Test-Path -LiteralPath (Join-Path $root ".env"))) {
    Write-Host "فایل .env پیدا نشد؛ ابتدا scripts\install.ps1 را اجرا کنید." -ForegroundColor Yellow
    exit 1
}

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "محیط مجازی پیدا نشد؛ ابتدا scripts\install.ps1 را اجرا کنید." -ForegroundColor Yellow
    exit 1
}

$logs = Join-Path $root "data\logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

$apiPort = Get-EnvValue -Root $root -Key "API_PORT" -Default "8000"
$apiHost = Get-EnvValue -Root $root -Key "API_HOST" -Default "0.0.0.0"

Start-Service-Process `
    -Name "api" `
    -Root $root `
    -Python $venvPython `
    -ServiceDirectory (Join-Path $root "services\api") `
    -Arguments @("-m", "uvicorn", "app.main:app", "--host", $apiHost, "--port", $apiPort)

# The face-service asks the API for its camera list, so it starts second.
Start-Service-Process `
    -Name "face-service" `
    -Root $root `
    -Python $venvPython `
    -ServiceDirectory (Join-Path $root "services\face-service") `
    -Arguments @("-m", "app.main")

Write-Host ""
Write-Host "سامانه بالا آمد." -ForegroundColor Green
Write-Host "پنل مدیریت: http://localhost:$apiPort" -ForegroundColor White
Write-Host "مستندات API: http://localhost:$apiPort/docs" -ForegroundColor White
Write-Host "لاگ‌ها: data\logs\  (یا scripts\logs.ps1)" -ForegroundColor DarkGray

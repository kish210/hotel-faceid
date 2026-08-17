# Start / update the full stack. Safe to run repeatedly.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path (Join-Path $root ".env"))) {
    Write-Host "فایل .env پیدا نشد؛ ابتدا scripts\install.ps1 را اجرا کنید." -ForegroundColor Yellow
    exit 1
}

Push-Location $root
try {
    docker compose up -d --build
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }
    Write-Host ""
    Write-Host "سامانه بالا آمد." -ForegroundColor Green
    Write-Host ("پنل: http://localhost:" + ((Get-Content .env | Where-Object { $_ -match '^WEB_PORT=' }) -replace '^WEB_PORT=', '')) -ForegroundColor White
} finally {
    Pop-Location
}

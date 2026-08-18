# Stop the full stack.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Push-Location $root
try {
    docker compose down
    if ($LASTEXITCODE -ne 0) { throw "docker compose down failed" }
    Write-Host "سامانه متوقف شد. داده‌ها در volume ها حفظ می‌شوند." -ForegroundColor Green
} finally {
    Pop-Location
}

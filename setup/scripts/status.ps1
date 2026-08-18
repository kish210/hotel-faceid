# Show container health + which ports the web panel and API use.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "== وضعیت سرویس‌ها ==" -ForegroundColor Cyan
docker compose --project-directory $root ps

Write-Host ""
Write-Host "== پورت‌ها ==" -ForegroundColor Cyan
if (Test-Path (Join-Path $root ".env")) {
    Get-Content (Join-Path $root ".env") | Where-Object { $_ -match '^(WEB_PORT|POSTGRES_PORT)=' }
}

Write-Host ""
Write-Host ("پنل: http://localhost:" + (((Get-Content (Join-Path $root ".env")) | Where-Object { $_ -match '^WEB_PORT=' }) -replace '^WEB_PORT=', '')) -ForegroundColor White

# Tail the live log of one service. Ctrl+C to stop.
#   .\logs.ps1              → API
#   .\logs.ps1 face-service → face-service
param(
    [ValidateSet("api", "face-service")]
    [string]$Service = "api",
    [switch]$Errors
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$suffix = if ($Errors) { ".err" } else { "" }
$logFile = Join-Path $root "data\logs\$Service$suffix.log"

if (-not (Test-Path -LiteralPath $logFile)) {
    Write-Host "فایل لاگ پیدا نشد: $logFile" -ForegroundColor Yellow
    Write-Host "ابتدا سامانه را با scripts\start.ps1 اجرا کنید." -ForegroundColor Yellow
    exit 1
}

Write-Host "== $logFile ==" -ForegroundColor Cyan
Get-Content -LiteralPath $logFile -Tail 50 -Wait

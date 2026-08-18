# Stop both services. Data in data\ is untouched.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "common.ps1")

$stopped = 0
foreach ($name in @("face-service", "api")) {
    $process = Get-ServiceProcess -Root $root -Name $name
    if (-not $process) {
        Write-Host "$name در حال اجرا نبود." -ForegroundColor DarkGray
        continue
    }

    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    Write-Host "$name متوقف شد (PID $($process.Id))." -ForegroundColor Green
    $stopped++
}

Remove-Item -Path (Join-Path (Get-RunDirectory -Root $root) "*.pid") -Force -ErrorAction SilentlyContinue

if ($stopped -gt 0) {
    Write-Host "سامانه متوقف شد. داده‌ها در پوشهٔ data حفظ می‌شوند." -ForegroundColor Green
}

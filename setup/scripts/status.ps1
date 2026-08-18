# Show whether each service is running, and whether the API answers.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "common.ps1")

$apiPort = Get-EnvValue -Root $root -Key "API_PORT" -Default "8000"

Write-Host "== وضعیت سرویس‌ها ==" -ForegroundColor Cyan
foreach ($name in @("api", "face-service")) {
    $process = Get-ServiceProcess -Root $root -Name $name
    if ($process) {
        $memory = [math]::Round($process.WorkingSet64 / 1MB)
        Write-Host ("{0,-14} در حال اجرا  (PID {1}، {2} مگابایت)" -f $name, $process.Id, $memory) -ForegroundColor Green
    } else {
        Write-Host ("{0,-14} متوقف" -f $name) -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "== پاسخ‌دهی API ==" -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Uri "http://localhost:$apiPort/health" -TimeoutSec 5
    Write-Host "سالم است: $($health.status)" -ForegroundColor Green
} catch {
    Write-Host "API پاسخ نداد (http://localhost:$apiPort/health)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "پنل: http://localhost:$apiPort" -ForegroundColor White

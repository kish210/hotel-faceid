# Collect logs + version + environment info into a timestamped folder,
# ready to send to the developer for troubleshooting.
$root = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$out = Join-Path $root "debug\$stamp"
New-Item -ItemType Directory -Force -Path $out | Out-Null

Write-Host "جمع‌آوری اطلاعات عیب‌یابی در: $out" -ForegroundColor Cyan

# System info
systeminfo 2>$null | Out-File (Join-Path $out "system.txt") -Encoding UTF8

# Docker engine info + compose ps
docker info 2>&1 | Out-File (Join-Path $out "docker-info.txt") -Encoding UTF8
docker compose --project-directory $root ps 2>&1 | Out-File (Join-Path $out "compose-ps.txt") -Encoding UTF8

# Logs per service
foreach ($svc in @("db", "api", "face-service", "web")) {
    docker compose --project-directory $root logs --no-color $svc 2>&1 | Out-File (Join-Path $out ("logs-$svc.txt")) -Encoding UTF8
}

# Version + installed .env (passwords redacted)
if (Test-Path (Join-Path $root "VERSION")) {
    Copy-Item (Join-Path $root "VERSION") (Join-Path $out "VERSION")
}
if (Test-Path (Join-Path $root ".env")) {
    Get-Content (Join-Path $root ".env") |
        ForEach-Object { $_ -replace '(PASSWORD|SECRET|KEY)=.*', '$1=***REDACTED***' } |
        Out-File (Join-Path $out "env-redacted.txt") -Encoding UTF8
}

Write-Host "انجام شد. پوشه '$out' را برای ما بفرستید." -ForegroundColor Green
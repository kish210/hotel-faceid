# Collect logs + version + environment info into a timestamped folder,
# ready to send to the developer for troubleshooting.
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "common.ps1")

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$out = Join-Path $root "debug\$stamp"
New-Item -ItemType Directory -Force -Path $out | Out-Null

Write-Host "جمع‌آوری اطلاعات عیب‌یابی در: $out" -ForegroundColor Cyan

# System info
systeminfo 2>$null | Out-File (Join-Path $out "system.txt") -Encoding UTF8

# Python + installed packages of the virtual environment
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPython) {
    & $venvPython -V 2>&1 | Out-File (Join-Path $out "python.txt") -Encoding UTF8
    & $venvPython -m pip freeze 2>&1 | Out-File (Join-Path $out "pip-freeze.txt") -Encoding UTF8
} else {
    "virtualenv not found at $venvPython" | Out-File (Join-Path $out "python.txt") -Encoding UTF8
}

# Which services are up
foreach ($name in @("api", "face-service")) {
    $process = Get-ServiceProcess -Root $root -Name $name
    $state = if ($process) { "running (PID $($process.Id))" } else { "stopped" }
    "$name : $state" | Out-File (Join-Path $out "services.txt") -Encoding UTF8 -Append
}

# Service logs
$logs = Join-Path $root "data\logs"
if (Test-Path -LiteralPath $logs) {
    Copy-Item -Path (Join-Path $logs "*.log") -Destination $out -ErrorAction SilentlyContinue
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

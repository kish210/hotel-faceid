<#
.SYNOPSIS
    Hotel Face-ID installer — no Docker.

    Creates a Python virtual environment, installs both services into it,
    builds the web panel if it is not already built, writes a secure .env and
    starts the system. Safe to run repeatedly.
#>

$ErrorActionPreference = "Stop"
$InstallDir = Split-Path -Parent $PSScriptRoot
$versionLine = Get-Content -LiteralPath (Join-Path $InstallDir "VERSION") -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $versionLine) { $versionLine = "0.9.0" }
$version = $versionLine

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Hotel Face-ID v$version — نصب سامانه (بدون Docker)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------- 1. Python
function Get-PythonCommand {
    # `py -3.11` is the launcher installed with python.org builds; plain
    # `python` on PATH is the fallback. The Microsoft Store stub answers on
    # PATH but fails to report a version, so asking it is what rules it out.
    $candidates = @(
        @{ Exe = "py";     Args = @("-3.11") },
        @{ Exe = "py";     Args = @("-3")    },
        @{ Exe = "python"; Args = @()        }
    )

    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Exe -ErrorAction SilentlyContinue)) { continue }
        $probe = $candidate.Args + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")
        $reported = & $candidate.Exe @probe 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $reported) { continue }

        $parts = $reported.Trim().Split(".")
        if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 10) {
            return @{ Exe = $candidate.Exe; Args = $candidate.Args; Version = $reported.Trim() }
        }
    }
    return $null
}

$python = Get-PythonCommand
if (-not $python) {
    Write-Host "[1/5] پایتون ۳.۱۰ یا بالاتر یافت نشد." -ForegroundColor Yellow
    Write-Host "      لطفاً Python 3.11 را از آدرس زیر نصب کنید و گزینهٔ" -ForegroundColor Yellow
    Write-Host "      'Add python.exe to PATH' را حتماً تیک بزنید:" -ForegroundColor Yellow
    Write-Host "      https://www.python.org/downloads/release/python-3119/" -ForegroundColor White
    Start-Process "https://www.python.org/downloads/"
    exit 1
}
Write-Host "[1/5] پایتون $($python.Version) یافت شد." -ForegroundColor Green

# ------------------------------------------------------------------ 2. venv
Write-Host ""
Write-Host "[2/5] ساخت محیط مجازی و نصب وابستگی‌ها (چند دقیقه طول می‌کشد)" -ForegroundColor Green
$venv = Join-Path $InstallDir ".venv"
$venvPython = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    & $python.Exe @($python.Args + @("-m", "venv", $venv))
    if ($LASTEXITCODE -ne 0) { throw "ساخت محیط مجازی ناموفق بود" }
}

& $venvPython -m pip install --upgrade pip --quiet
foreach ($service in @("api", "face-service")) {
    $requirements = Join-Path $InstallDir "services\$service\requirements.txt"
    Write-Host "      نصب وابستگی‌های $service ..." -ForegroundColor DarkGray
    & $venvPython -m pip install --quiet -r $requirements
    if ($LASTEXITCODE -ne 0) { throw "نصب وابستگی‌های $service ناموفق بود" }
}
Write-Host "      وابستگی‌ها نصب شد." -ForegroundColor Green

# ------------------------------------------------------------------- 3. web
Write-Host ""
Write-Host "[3/5] پنل وب" -ForegroundColor Green
$distIndex = Join-Path $InstallDir "web\dist\index.html"
if (Test-Path -LiteralPath $distIndex) {
    Write-Host "      پنل از قبل build شده است." -ForegroundColor Green
} elseif (Get-Command npm -ErrorAction SilentlyContinue) {
    Push-Location (Join-Path $InstallDir "web")
    try {
        npm install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw "npm install ناموفق بود" }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "build پنل ناموفق بود" }
    } finally {
        Pop-Location
    }
    Write-Host "      پنل build شد." -ForegroundColor Green
} else {
    Write-Host "      Node.js یافت نشد و پنل build نشده است." -ForegroundColor Yellow
    Write-Host "      یا Node.js نصب کنید (https://nodejs.org) و دوباره اجرا کنید،" -ForegroundColor Yellow
    Write-Host "      یا پوشهٔ web\dist را از یک نصب دیگر کپی کنید." -ForegroundColor Yellow
    Write-Host "      API بدون پنل هم کار می‌کند: http://localhost:8000/docs" -ForegroundColor Yellow
}

# ------------------------------------------------------------------ 4. .env
Write-Host ""
Write-Host "[4/5] آماده‌سازی فایل .env" -ForegroundColor Green
$envPath = Join-Path $InstallDir ".env"
if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath (Join-Path $InstallDir ".env.example") -Destination $envPath
    $content = Get-Content -LiteralPath $envPath -Raw

    # Every default secret is replaced on first install; leaving them in place
    # would ship the same JWT and encryption keys to every hotel.
    $jwt = & $venvPython -c "import secrets; print(secrets.token_hex(32))"
    $fernet = & $venvPython -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    $serviceKey = & $venvPython -c "import secrets; print(secrets.token_urlsafe(32))"

    $content = $content -replace "(?m)^JWT_SECRET=.*$", "JWT_SECRET=$jwt"
    $content = $content -replace "(?m)^SECRET_ENCRYPTION_KEY=.*$", "SECRET_ENCRYPTION_KEY=$fernet"
    $content = $content -replace "(?m)^SERVICE_API_KEY=.*$", "SERVICE_API_KEY=$serviceKey"
    Set-Content -LiteralPath $envPath -Value $content -Encoding utf8 -NoNewline
    Write-Host "      .env ساخته شد و رمزها به‌صورت تصادفی تولید شدند." -ForegroundColor Green
} else {
    Write-Host "      .env از قبل وجود دارد؛ دست‌نخورده ماند." -ForegroundColor Green
}

New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "data\media") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "data\logs") | Out-Null

# ----------------------------------------------------------------- 5. start
Write-Host ""
Write-Host "[5/5] راه‌اندازی سامانه" -ForegroundColor Green
& (Join-Path $PSScriptRoot "start.ps1")

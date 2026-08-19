<#
.SYNOPSIS
    Hotel Face-ID first-run setup.

    The packaged build ships its own Python runtime, every package and the
    face-recognition models, so this normally only writes the configuration
    file and starts the two services — no downloads, no internet needed.

    On a developer machine with no bundled runtime it falls back to building a
    virtual environment from the requirements files instead.

    Safe to run repeatedly.
#>

$ErrorActionPreference = "Stop"
$InstallDir = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "common.ps1")

$versionLine = Get-Content -LiteralPath (Join-Path $InstallDir "VERSION") -ErrorAction SilentlyContinue | Select-Object -First 1
$version = if ($versionLine) { $versionLine } else { "1.3.0" }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Hotel Face-ID v$version — راه‌اندازی سامانه" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# --------------------------------------------------------------- 1. runtime
Write-Host "[1/4] موتور اجرا" -ForegroundColor Green
$python = Get-AppPython -Root $InstallDir

if ($python -and $python -like "*runtime\python\python.exe") {
    Write-Host "      موتور پایتون همراه نصب استفاده می‌شود (نیازی به نصب چیزی نیست)." -ForegroundColor Green
} else {
    Write-Host "      موتور همراه پیدا نشد؛ ساخت محیط مجازی از روی پایتون سیستم..." -ForegroundColor Yellow
    $python = Build-DeveloperVenv -InstallDir $InstallDir
    if (-not $python) { exit 1 }
}

$models = Join-Path $InstallDir "models\buffalo_l"
if (Test-Path -LiteralPath $models) {
    Write-Host "      مدل‌های تشخیص چهره همراه نصب موجود است." -ForegroundColor Green
} else {
    Write-Host "      مدل‌ها همراه نصب نیستند؛ در اولین اجرا دانلود می‌شوند (نیاز به اینترنت)." -ForegroundColor Yellow
}

# ------------------------------------------------------------------- 2. web
Write-Host ""
Write-Host "[2/4] پنل وب" -ForegroundColor Green
if (Test-Path -LiteralPath (Join-Path $InstallDir "web\dist\index.html")) {
    Write-Host "      پنل آماده است." -ForegroundColor Green
} else {
    Write-Host "      پنل build‌شده پیدا نشد — فقط API در دسترس خواهد بود." -ForegroundColor Yellow
}

# ------------------------------------------------------------------ 3. .env
Write-Host ""
Write-Host "[3/4] پیکربندی" -ForegroundColor Green
$envPath = Join-Path $InstallDir ".env"
if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath (Join-Path $InstallDir ".env.example") -Destination $envPath
    $content = Get-Content -LiteralPath $envPath -Raw

    # Every default secret is replaced on first install; leaving them in place
    # would ship the same JWT and encryption keys to every hotel.
    $jwt = & $python -c "import secrets; print(secrets.token_hex(32))"
    $fernet = & $python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    $serviceKey = & $python -c "import secrets; print(secrets.token_urlsafe(32))"

    $content = $content -replace "(?m)^JWT_SECRET=.*$", "JWT_SECRET=$jwt"
    $content = $content -replace "(?m)^SECRET_ENCRYPTION_KEY=.*$", "SECRET_ENCRYPTION_KEY=$fernet"
    $content = $content -replace "(?m)^SERVICE_API_KEY=.*$", "SERVICE_API_KEY=$serviceKey"
    Set-Content -LiteralPath $envPath -Value $content -Encoding utf8 -NoNewline
    Write-Host "      فایل تنظیمات ساخته شد و کلیدهای امنیتی تصادفی تولید شدند." -ForegroundColor Green
} else {
    Write-Host "      تنظیمات قبلی حفظ شد." -ForegroundColor Green
}

foreach ($folder in @("data\media", "data\logs", "data\run")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir $folder) | Out-Null
}

# The panel is reachable from other machines on the hotel network; without a
# rule Windows pops a firewall dialog the first time. Needs admin — if the
# user installed without it, Windows will simply ask them once instead.
$apiPort = Get-EnvValue -Root $InstallDir -Key "API_PORT" -Default "8000"
try {
    if (-not (Get-NetFirewallRule -DisplayName "Hotel Face-ID" -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName "Hotel Face-ID" -Direction Inbound -Action Allow `
            -Protocol TCP -LocalPort $apiPort -ErrorAction Stop | Out-Null
        Write-Host "      قانون فایروال برای پورت $apiPort اضافه شد." -ForegroundColor Green
    }
} catch {
    Write-Host "      قانون فایروال اضافه نشد (نیاز به دسترسی مدیر) — بی‌اهمیت است." -ForegroundColor DarkGray
}

# ----------------------------------------------------------------- 4. start
Write-Host ""
Write-Host "[4/4] راه‌اندازی" -ForegroundColor Green
& (Join-Path $PSScriptRoot "start.ps1")

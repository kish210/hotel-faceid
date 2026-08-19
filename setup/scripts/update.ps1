<#
.SYNOPSIS
    Upgrades an existing Hotel Face-ID installation in place.

.DESCRIPTION
    Run by Hotel-FaceID-Update.exe after it has laid the new files down. The
    installer replaces program files; this script deals with everything the
    installer cannot know about:

      * stopping whatever is running, including the console-window layout that
        earlier releases used
      * backing the database up before a single column is touched
      * carrying settings forward — the .env of an older release is missing
        every key added since, and the defaults must not silently differ
      * clearing away the file layout of the 1.0 release, whose `app\` and
        `faceservice\` folders would otherwise sit there confusing everyone
      * starting the system again

    Guest data — the database, the face images, the camera list — is never
    touched beyond the schema migration the API performs at startup.
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "common.ps1")

$versionLine = Get-Content -LiteralPath (Join-Path $root "VERSION") -ErrorAction SilentlyContinue | Select-Object -First 1
$version = if ($versionLine) { $versionLine } else { "1.3.0" }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Hotel Face-ID — به‌روزرسانی به نسخهٔ $version" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------------ 1. stop
Write-Host "[1/5] توقف سامانه" -ForegroundColor Green
try {
    & (Join-Path $PSScriptRoot "stop.ps1") | Out-Null
} catch {
    Write-Host "      (سرویسی از طریق اسکریپت‌ها در حال اجرا نبود)" -ForegroundColor DarkGray
}

# Releases before 1.2 started python from start.bat, so no PID file exists for
# them. Those processes still hold the database open and must go.
$ours = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) }
foreach ($process in $ours) {
    Write-Host "      بستن پروسهٔ قدیمی (PID $($process.ProcessId))" -ForegroundColor DarkGray
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2

# ---------------------------------------------------------------- 2. backup
Write-Host ""
Write-Host "[2/5] پشتیبان‌گیری از داده‌ها" -ForegroundColor Green
$database = Join-Path $root "data\hotel_faceid.db"
if (Test-Path -LiteralPath $database) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupDir = Join-Path $root "data\backup"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    $backup = Join-Path $backupDir "hotel_faceid-$stamp.db"
    Copy-Item -LiteralPath $database -Destination $backup
    Write-Host "      نسخهٔ پشتیبان: data\backup\$(Split-Path $backup -Leaf)" -ForegroundColor Green
} else {
    Write-Host "      پایگاه داده‌ای برای پشتیبان‌گیری پیدا نشد (نصب تازه)." -ForegroundColor DarkGray
}

# ------------------------------------------------------------------- 3. env
Write-Host ""
Write-Host "[3/5] انتقال تنظیمات" -ForegroundColor Green
$envPath = Join-Path $root ".env"
$examplePath = Join-Path $root ".env.example"

if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath $examplePath -Destination $envPath
    Write-Host "      فایل تنظیمات ساخته شد." -ForegroundColor Green
} else {
    # Only keys that are entirely absent get appended: an operator's edited
    # value must survive the upgrade untouched.
    $existing = Get-Content -LiteralPath $envPath
    $present = @{}
    foreach ($line in $existing) {
        if ($line -match "^\s*([A-Z0-9_]+)=") { $present[$Matches[1]] = $true }
    }

    $added = @()
    foreach ($line in Get-Content -LiteralPath $examplePath) {
        if ($line -match "^\s*([A-Z0-9_]+)=" -and -not $present.ContainsKey($Matches[1])) {
            $added += $line
        }
    }

    if ($added.Count -gt 0) {
        Add-Content -LiteralPath $envPath -Value "" -Encoding utf8
        Add-Content -LiteralPath $envPath -Value "# --- افزوده‌شده در به‌روزرسانی $version ---" -Encoding utf8
        Add-Content -LiteralPath $envPath -Value $added -Encoding utf8
        Write-Host "      $($added.Count) تنظیم جدید اضافه شد؛ مقادیر قبلی دست‌نخورده ماند." -ForegroundColor Green
    } else {
        Write-Host "      تنظیمات کامل بود." -ForegroundColor Green
    }
}

# An installation whose API was moved off port 8000 kept an API_BASE_URL
# pointing at the old one, and the capture service then talks to nothing —
# no faces are ever recognised, with no error in the panel to show for it.
$apiPort = Get-EnvValue -Root $root -Key "API_PORT" -Default "8000"
$baseUrl = Get-EnvValue -Root $root -Key "API_BASE_URL"
if ($baseUrl -and $baseUrl -match "^https?://(localhost|127\.0\.0\.1):(\d+)" -and $Matches[2] -ne $apiPort) {
    $content = (Get-Content -LiteralPath $envPath -Raw) -replace "(?m)^API_BASE_URL=.*$", "API_BASE_URL="
    Set-Content -LiteralPath $envPath -Value $content -Encoding utf8 -NoNewline
    Write-Host "      آدرس داخلی سرویس با پورت $apiPort هماهنگ شد." -ForegroundColor Yellow
}

# An install that ran with an empty encryption key stored camera passwords as
# plain text. Generating one now is the fix, and the API re-encrypts on save.
$python = Get-AppPython -Root $root
$encryptionKey = Get-EnvValue -Root $root -Key "SECRET_ENCRYPTION_KEY"
if (-not $encryptionKey -and $python) {
    $fernet = & $python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    $content = (Get-Content -LiteralPath $envPath -Raw) -replace "(?m)^SECRET_ENCRYPTION_KEY=.*$", "SECRET_ENCRYPTION_KEY=$fernet"
    Set-Content -LiteralPath $envPath -Value $content -Encoding utf8 -NoNewline
    Write-Host "      کلید رمزنگاری ساخته شد — رمز دوربین‌ها از این پس رمزنگاری می‌شود." -ForegroundColor Yellow
    Write-Host "      (رمزهای ثبت‌شدهٔ قبلی را یک بار در صفحهٔ دوربین‌ها ذخیره کنید)" -ForegroundColor Yellow
}

# ------------------------------------------------------------- 4. old files
Write-Host ""
Write-Host "[4/5] پاک‌سازی فایل‌های نسخهٔ قدیمی" -ForegroundColor Green
$obsolete = @(
    "app", "faceservice", "fonts",
    "start.bat", "stop.bat", "test-standalone.py", "test-face.jpg",
    "docker-compose.yml"
)
$removed = 0
foreach ($item in $obsolete) {
    $path = Join-Path $root $item
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
        $removed++
    }
}
Write-Host "      $removed مورد از ساختار قدیمی حذف شد." -ForegroundColor Green

foreach ($folder in @("data\media", "data\logs", "data\run", "data\modules")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $root $folder) | Out-Null
}

# ----------------------------------------------------------------- 5. start
Write-Host ""
Write-Host "[5/5] راه‌اندازی مجدد" -ForegroundColor Green

# The small update package assumes the machine already has these; say so
# plainly instead of letting the services fail with an import error.
if (-not (Get-AppPython -Root $root)) {
    Write-Host "      موتور پایتون روی این سیستم پیدا نشد." -ForegroundColor Red
    Write-Host "      این بستهٔ به‌روزرسانیِ کوچک است و موتور اجرا را همراه ندارد؛" -ForegroundColor Red
    Write-Host "      لطفاً از فایل نصب کامل (Hotel-FaceID-Setup) استفاده کنید." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $root "models\buffalo_l"))) {
    Write-Host "      مدل‌های تشخیص چهره پیدا نشد؛ در اولین اجرا دانلود می‌شوند." -ForegroundColor Yellow
}
Write-Host "      (اولین اجرا چند ثانیه طول می‌کشد: ستون‌های جدید به پایگاه داده اضافه می‌شوند)" -ForegroundColor DarkGray
& (Join-Path $PSScriptRoot "start.ps1")

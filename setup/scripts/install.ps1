<#
.SYNOPSIS
    Hotel Face-ID installer — checks Docker, writes a secure .env,
    builds and starts the full stack, creates desktop shortcuts.
#>

$ErrorActionPreference = "Stop"
$InstallDir = Split-Path -Parent $PSScriptRoot
$versionLine = Get-Content -LiteralPath (Join-Path $InstallDir "VERSION") -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $versionLine) { $versionLine = "0.9.0" }
$version = $versionLine

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Hotel Face-ID v$version — نصب سامانه" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------- 1. Docker
function Test-DockerDaemon {
    try {
        $info = docker info 2>$null | Out-String
        return [bool]($info -match "Server Version|Operating System")
    } catch {
        return $false
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "[1/4] Docker یافت نشد." -ForegroundColor Yellow
    Write-Host "      لطفاً Docker Desktop را از آدرس زیر نصب کنید:" -ForegroundColor Yellow
    Write-Host "      https://www.docker.com/products/docker-desktop/" -ForegroundColor White
    Start-Process "https://www.docker.com/products/docker-desktop/"
    Write-Host "      پس از نصب، دوباره این اسکریپت را اجرا کنید." -ForegroundColor Yellow
    exit 1
}
Write-Host "[1/4] Docker یافت شد." -ForegroundColor Green

if (-not (Test-DockerDaemon)) {
    Write-Host "      Docker در حال اجرا نیست؛ در حال تلاش برای راه‌اندازی..." -ForegroundColor Yellow
    $desktop = @("C:\Program Files\Docker\Docker\Docker Desktop.exe", "$env:LOCALAPPDATA\Docker\Docker Desktop.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($desktop) { Start-Process $desktop }
    $attempts = 0
    while (-not (Test-DockerDaemon) -and $attempts -lt 30) {
        Start-Sleep -Seconds 4
        $attempts++
    }
    if (-not (Test-DockerDaemon)) {
        Write-Host "      Docker هنوز بالا نیامده. Docker Desktop را باز و صبر کنید تا سبز شود،" -ForegroundColor Red
        Write-Host "      سپس دوباره اجرا کنید." -ForegroundColor Red
        exit 1
    }
    Write-Host "      Docker آماده شد." -ForegroundColor Green
}

# ---------------------------------------------------------------- 2. .env
Write-Host ""
Write-Host "[2/4] آماده‌سازی فایل .env" -ForegroundColor Green
$envPath = Join-Path $InstallDir ".env"
if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath (Join-Path $InstallDir ".env.example") -Destination $envPath

    # Secure random values
    $jwt = (1..32 | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) }) -join ''
    $serviceKey = (1..24 | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) }) -join ''
    $pgPass = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
    $fernet = "TEMP" # replaced below if cryptography is available

    # Fernet key via python if available
    if (Get-Command python -ErrorAction SilentlyContinue) {
        try {
            $fernet = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>$null
            if ($LASTEXITCODE -ne 0 -or -not $fernet) { $fernet = "TEMP" }
        } catch { $fernet = "TEMP" }
    }

    $c = Get-Content -LiteralPath $envPath -Raw
    $c = $c -replace '^POSTGRES_PASSWORD=change-me$', ("POSTGRES_PASSWORD=" + $pgPass)
    $c = $c -replace '^JWT_SECRET=change-me-to-a-random-32-byte-hex-string$', ("JWT_SECRET=" + $jwt)
    $c = $c -replace '^SERVICE_API_KEY=change-me-service-key$', ("SERVICE_API_KEY=" + $serviceKey)
    $c = $c -replace '^SECRET_ENCRYPTION_KEY=$', ("SECRET_ENCRYPTION_KEY=" + $fernet)
    Set-Content -LiteralPath $envPath -Value $c -Encoding ASCII

    Write-Host "      .env ساخته و با رمزهای تصادفی امن شد." -ForegroundColor Green
} else {
    Write-Host "      .env از قبل وجود دارد — بدون تغییر." -ForegroundColor Green
}

# ---------------------------------------------------------------- 3. Ports
Write-Host ""
Write-Host "[3/4] بررسی پورت‌ها" -ForegroundColor Green
$envFile = Get-Content -LiteralPath $envPath
$webPort = [int](($envFile | Where-Object { $_ -match '^WEB_PORT=' }) -replace '^WEB_PORT=', '')
$pgPort  = [int](($envFile | Where-Object { $_ -match '^POSTGRES_PORT=' }) -replace '^POSTGRES_PORT=', '')
if (-not $webPort) { $webPort = 4000 }
if (-not $pgPort)  { $pgPort = 5432 }

function Test-PortFree([int]$port) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return -not $conn
}

foreach ($p in @(@{Name="WEB_PORT"; Port=$webPort; Label="پنل مدیریت"},
                 @{Name="POSTGRES_PORT"; Port=$pgPort; Label="پایگاه داده"})) {
    if (-not (Test-PortFree $p.Port)) {
        Write-Host ("      پورت {0} ({1}) اشغال است." -f $p.Port, $p.Label) -ForegroundColor Yellow
        $auto = $p.Port + 1
        while (-not (Test-PortFree $auto)) { $auto++ }

        $chosen = $auto
        try {
            $input = Read-Host ("      پورت جدید برای {0} را وارد کنید (خالی = {1}): " -f $p.Label, $auto)
            if ($input) { $chosen = [int]$input }
        } catch {
            Write-Host ("      حالت غیرتعاملی؛ پورت {0} خودکار انتخاب شد." -f $auto) -ForegroundColor DarkGray
        }

        $envFile = $envFile -replace ("^{0}=.*$" -f $p.Name), ("{0}={1}" -f $p.Name, $chosen)
        Set-Content -LiteralPath $envPath -Value $envFile -Encoding ASCII
        Write-Host ("      {0} → {1}" -f $p.Name, $chosen) -ForegroundColor Green
    } else {
        Write-Host ("      پورت {0} ({1}) آزاد است." -f $p.Port, $p.Label) -ForegroundColor DarkGray
    }
}

# ---------------------------------------------------------------- 4. Compose
Write-Host ""
Write-Host "[4/4] ساخت و راه‌اندازی کانتینرها (چند دقیقه)" -ForegroundColor Green
Write-Host "      اولین بار مدل تشخیص چهره (~300MB) دانلود می‌شود." -ForegroundColor DarkGray

Push-Location $InstallDir
try {
    docker compose up -d --build
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  نصب کامل شد! سامانه در حال اجراست." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host ("  پنل مدیریت : http://localhost:{0}" -f $webPort) -ForegroundColor White
Write-Host "  ورود اولیه : admin / admin  (حتماً تغییر دهید)" -ForegroundColor Yellow
Write-Host ""
Write-Host "  دستورات: .\scripts\status.ps1 | .\scripts\logs.ps1 | .\scripts\stop.ps1" -ForegroundColor DarkGray

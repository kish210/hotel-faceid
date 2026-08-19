# Shared helpers for the start/stop/status scripts.
#
# Both services run as ordinary background processes. Their PIDs are written
# to data\run so stop.ps1 and status.ps1 can find exactly the processes this
# installation started, rather than guessing from the process list.

function Get-AppPython {
    <#
        The interpreter the services run on, in order of preference:

        1. runtime\python\python.exe — shipped inside the installer, already
           holding every package and needing nothing from the machine.
        2. .venv — built by install.ps1 on a developer box that has Python.

        Returns $null when neither exists.
    #>
    param([Parameter(Mandatory)][string]$Root)

    foreach ($candidate in @("runtime\python\python.exe", ".venv\Scripts\python.exe")) {
        $path = Join-Path $Root $candidate
        if (Test-Path -LiteralPath $path) { return $path }
    }
    return $null
}

function Find-SystemPython {
    <#
        A Python 3.10+ on the machine, for the developer fallback only.
        `py -3.11` is the launcher installed with python.org builds; plain
        `python` is the fallback. The Microsoft Store stub answers on PATH but
        fails to report a version, so asking it is what rules it out.
    #>
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

function Build-DeveloperVenv {
    <#
        Builds .venv from the requirements files. Only used when the bundled
        runtime is absent, i.e. when running from a source checkout.
        Returns the path to the virtualenv's python.exe, or $null.
    #>
    param([Parameter(Mandatory)][string]$InstallDir)

    $system = Find-SystemPython
    if (-not $system) {
        Write-Host "      پایتون ۳.۱۰ یا بالاتر روی این سیستم نصب نیست." -ForegroundColor Red
        Write-Host "      این نسخه از بستهٔ نصب، موتور پایتون همراه ندارد." -ForegroundColor Red
        Write-Host "      Python 3.11 را نصب کنید: https://www.python.org/downloads/" -ForegroundColor White
        return $null
    }

    $venvPython = Join-Path $InstallDir ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython)) {
        & $system.Exe @($system.Args + @("-m", "venv", (Join-Path $InstallDir ".venv")))
        if ($LASTEXITCODE -ne 0) { throw "ساخت محیط مجازی ناموفق بود" }
    }

    & $venvPython -m pip install --upgrade pip --quiet --no-warn-script-location
    foreach ($service in @("api", "face-service")) {
        Write-Host "      نصب وابستگی‌های $service ..." -ForegroundColor DarkGray
        & $venvPython -m pip install --quiet --no-warn-script-location `
            -r (Join-Path $InstallDir "services\$service\requirements.txt")
        if ($LASTEXITCODE -ne 0) { throw "نصب وابستگی‌های $service ناموفق بود" }
    }
    return $venvPython
}

function Get-RunDirectory {
    param([Parameter(Mandatory)][string]$Root)

    $runDirectory = Join-Path $Root "data\run"
    New-Item -ItemType Directory -Force -Path $runDirectory | Out-Null
    return $runDirectory
}

function Get-EnvValue {
    param(
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][string]$Key,
        [string]$Default = ""
    )

    $envPath = Join-Path $Root ".env"
    if (-not (Test-Path -LiteralPath $envPath)) { return $Default }

    $line = Get-Content -LiteralPath $envPath | Where-Object { $_ -match "^\s*$Key=" } | Select-Object -Last 1
    if (-not $line) { return $Default }

    $value = ($line -replace "^\s*$Key=", "").Trim()
    if ($value) { return $value } else { return $Default }
}

function Get-ServiceProcess {
    param(
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][string]$Name
    )

    $pidFile = Join-Path (Get-RunDirectory -Root $Root) "$Name.pid"
    if (-not (Test-Path -LiteralPath $pidFile)) { return $null }

    $recorded = (Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not $recorded) { return $null }

    try { return Get-Process -Id ([int]$recorded) -ErrorAction Stop } catch { return $null }
}

function Start-Service-Process {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][string]$Python,
        # Directory holding the service's `app` package, put on PYTHONPATH.
        [Parameter(Mandatory)][string]$ServiceDirectory,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    $running = Get-ServiceProcess -Root $Root -Name $Name
    if ($running) {
        Write-Host "      $Name از قبل در حال اجراست (PID $($running.Id))." -ForegroundColor DarkGray
        return $running
    }

    $logs = Join-Path $Root "data\logs"
    New-Item -ItemType Directory -Force -Path $logs | Out-Null

    # Both services run *from the installation root* so that `.env` and the
    # relative paths inside it (data\media, the SQLite file) resolve to one
    # place; the service's own folder is reached through PYTHONPATH instead.
    $previousPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = $ServiceDirectory
    try {
        $process = Start-Process -FilePath $Python `
            -ArgumentList $Arguments `
            -WorkingDirectory $Root `
            -RedirectStandardOutput (Join-Path $logs "$Name.log") `
            -RedirectStandardError (Join-Path $logs "$Name.err.log") `
            -WindowStyle Hidden `
            -PassThru
    } finally {
        $env:PYTHONPATH = $previousPythonPath
    }

    Set-Content -LiteralPath (Join-Path (Get-RunDirectory -Root $Root) "$Name.pid") `
        -Value $process.Id -Encoding ascii

    Write-Host "      $Name اجرا شد (PID $($process.Id))." -ForegroundColor Green
    return $process
}

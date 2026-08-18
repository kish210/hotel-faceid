# Shared helpers for the start/stop/status scripts.
#
# Both services run as ordinary background processes. Their PIDs are written
# to data\run so stop.ps1 and status.ps1 can find exactly the processes this
# installation started, rather than guessing from the process list.

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

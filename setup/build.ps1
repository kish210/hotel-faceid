<#
.SYNOPSIS
    Builds the self-contained Hotel Face-ID installer.

.DESCRIPTION
    The shipped package contains a full Python runtime, every dependency and
    the InsightFace models, so the hotel's machine needs nothing installed and
    no internet connection. Those pieces are too large for git, so they are
    assembled here into setup\payload\ before Inno Setup is invoked.

    Run from a machine that has Python 3.11, Node.js and Inno Setup 6:

        powershell -ExecutionPolicy Bypass -File setup\build.ps1

.PARAMETER Python
    Python 3.11 used to create the bundled runtime. Defaults to `py -3.11`.

.PARAMETER SkipPayload
    Reuse setup\payload as-is (fast rebuilds when only source changed).
#>
param(
    [string]$Python = "",
    [switch]$SkipPayload,
    [switch]$SkipWeb
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$payload = Join-Path $root "setup\payload"
$runtime = Join-Path $payload "runtime\python"
$models = Join-Path $payload "models"

function Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }

# --------------------------------------------------------------- 1. runtime
if ($SkipPayload -and (Test-Path (Join-Path $runtime "python.exe"))) {
    Step "runtime: reusing setup\payload"
} else {
    Step "runtime: assembling a portable Python with every dependency"

    if (-not $Python) {
        $Python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
    }
    $versionArgs = if ($Python -eq "py") { @("-3.11") } else { @() }

    # A copy of the interpreter's own installation is what makes the runtime
    # portable: a venv would still point at the machine's Python.
    $base = & $Python @($versionArgs + @("-c", "import sys, os; print(os.path.dirname(sys.executable))"))
    if ($LASTEXITCODE -ne 0 -or -not $base) { throw "Python 3.11 not found (pass -Python)" }

    Write-Host "   copying $base"
    New-Item -ItemType Directory -Force -Path $runtime | Out-Null
    robocopy $base $runtime /E /NFL /NDL /NJH /NJS /MT:16 /XD "__pycache__" | Out-Null

    $runtimePython = Join-Path $runtime "python.exe"
    & $runtimePython -m pip install --upgrade pip --quiet --no-warn-script-location
    foreach ($service in @("api", "face-service")) {
        Write-Host "   installing $service requirements"
        & $runtimePython -m pip install --quiet --no-warn-script-location `
            -r (Join-Path $root "services\$service\requirements.txt")
        if ($LASTEXITCODE -ne 0) { throw "pip install failed for $service" }
    }
}

# ---------------------------------------------------------------- 2. models
if ($SkipPayload -and (Test-Path (Join-Path $models "buffalo_l"))) {
    Step "models: reusing setup\payload\models"
} else {
    Step "models: downloading the InsightFace pack once, into the payload"

    $runtimePython = Join-Path $runtime "python.exe"
    New-Item -ItemType Directory -Force -Path $models | Out-Null
    # FaceAnalysis downloads into <root>\models\<pack>, which is the layout the
    # installed application expects, so point it straight at the payload.
    & $runtimePython -c @"
from insightface.app import FaceAnalysis
app = FaceAnalysis(name='buffalo_l', root=r'$payload',
                   allowed_modules=['detection', 'recognition', 'genderage'])
app.prepare(ctx_id=-1)
print('models ready')
"@
    if ($LASTEXITCODE -ne 0) { throw "model download failed" }
}

# ------------------------------------------------------------------- 3. web
if ($SkipWeb -and (Test-Path (Join-Path $root "web\dist\index.html"))) {
    Step "web: reusing web\dist"
} else {
    Step "web: building the React panel"
    Push-Location (Join-Path $root "web")
    try {
        npm install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
    } finally { Pop-Location }
}

# ------------------------------------------------------------- 4. installer
Step "installer: compiling with Inno Setup"

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 7\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) { throw "Inno Setup 6 not found — install it from https://jrsoftware.org/isdl.php" }

& $iscc (Join-Path $root "setup\Hotel-FaceID.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compile failed" }

$exe = Get-ChildItem (Join-Path $root "setup\dist") -Filter "*.exe" | Sort-Object LastWriteTime | Select-Object -Last 1
Write-Host "`nBuilt $($exe.FullName) ($([math]::Round($exe.Length/1MB,1)) MB)" -ForegroundColor Green

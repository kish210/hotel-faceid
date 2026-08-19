<#
.SYNOPSIS
    Downloads the Python runtime and recognition models after installation.

.DESCRIPTION
    The small installer carries the application but not the ~900 MB of runtime
    and models. This fetches them on first run, from the parts published
    alongside the release.

    Written to survive a hotel's internet rather than assume a good line:

      * each part is a separate download, so a dropped connection costs one
        part rather than the whole gigabyte
      * a part already on disk with the right hash is not downloaded again, so
        re-running after a failure resumes where it stopped
      * every part is checked against its SHA256 before anything is unpacked,
        because a truncated archive that half-extracts is far worse than a
        clean failure

.PARAMETER Component
    runtime, models, or both (default).
#>
param(
    [ValidateSet("runtime", "models", "both")]
    [string]$Component = "both",
    [string]$ManifestPath,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not $ManifestPath) { $ManifestPath = Join-Path $root "payload-manifest.json" }
if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "فایل فهرست اجزا پیدا نشد: $ManifestPath"
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$cache = Join-Path $root "data\download"
New-Item -ItemType Directory -Force -Path $cache | Out-Null

# TLS 1.2 is not the default on older Windows 10 builds and GitHub needs it.
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Get-Part {
    param([string]$Name, [string]$Sha256, [long]$Size)

    $path = Join-Path $cache $Name
    if ((Test-Path -LiteralPath $path) -and (Get-Item $path).Length -eq $Size) {
        if ((Get-FileHash $path -Algorithm SHA256).Hash.ToLower() -eq $Sha256) {
            Write-Host "      $Name — از قبل دانلود شده" -ForegroundColor DarkGray
            return $path
        }
    }
    Remove-Item $path -Force -ErrorAction SilentlyContinue

    $url = "$($manifest.base_url)/$Name"
    foreach ($attempt in 1..4) {
        try {
            Write-Host ("      $Name — دانلود ({0} مگابایت)" -f [math]::Round($Size / 1MB)) -NoNewline
            # WebClient rather than Invoke-WebRequest: it streams to disk instead
            # of buffering the whole part in memory.
            $client = New-Object Net.WebClient
            try { $client.DownloadFile($url, $path) } finally { $client.Dispose() }

            if ((Get-FileHash $path -Algorithm SHA256).Hash.ToLower() -eq $Sha256) {
                Write-Host "  ✓" -ForegroundColor Green
                return $path
            }
            Write-Host "  — فایل ناقص بود" -ForegroundColor Yellow
        } catch {
            Write-Host "  — تلاش $attempt ناموفق" -ForegroundColor Yellow
        }
        Remove-Item $path -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds (5 * $attempt)
    }
    throw "دانلود $Name پس از چند تلاش ناموفق ماند"
}

function Expand-Archive-Overwriting {
    <#
        Unpacks entry by entry rather than calling ExtractToDirectory.

        Windows PowerShell 5.1 runs on .NET Framework, whose
        ExtractToDirectory has no "overwrite" parameter — its third argument is
        an encoding, so passing $true there fails with a cast error. ExtractToFile
        does take one, so extracting the entries individually works on every
        Windows version this ships to, and lets a re-run repair a half-finished
        unpack instead of stopping on the first existing file.
    #>
    param([Parameter(Mandatory)][string]$Archive, [Parameter(Mandatory)][string]$Target)

    $zip = [System.IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        $total = $zip.Entries.Count
        $done = 0
        foreach ($entry in $zip.Entries) {
            $destination = Join-Path $Target $entry.FullName
            $parent = Split-Path -Parent $destination
            if ($parent -and -not (Test-Path -LiteralPath $parent)) {
                New-Item -ItemType Directory -Force -Path $parent | Out-Null
            }
            # A directory entry has an empty name and nothing to write.
            if ($entry.Name) {
                [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destination, $true)
            }

            $done++
            if ($done % 500 -eq 0) {
                Write-Host ("`r      {0} از {1} فایل" -f $done, $total) -NoNewline -ForegroundColor DarkGray
            }
        }
        Write-Host ("`r      {0} فایل باز شد            " -f $total) -ForegroundColor DarkGray
    } finally {
        $zip.Dispose()
    }
}


function Install-Component {
    param([string]$Name)

    $target = Join-Path $root $Name
    if ((Test-Path -LiteralPath $target) -and -not $Force) {
        $marker = if ($Name -eq "runtime") { "python\python.exe" } else { "buffalo_l" }
        if (Test-Path -LiteralPath (Join-Path $target $marker)) {
            Write-Host "   $Name از قبل نصب است." -ForegroundColor Green
            return
        }
    }

    $spec = $manifest.parts.$Name
    Write-Host "   $Name — $($spec.parts.Count) بخش" -ForegroundColor Cyan

    $paths = foreach ($part in $spec.parts) {
        Get-Part -Name $part.name -Sha256 $part.sha256 -Size $part.size
    }

    Write-Host "      اتصال بخش‌ها" -ForegroundColor DarkGray
    $archive = Join-Path $cache "$Name.zip"
    Remove-Item $archive -Force -ErrorAction SilentlyContinue
    $output = [System.IO.File]::Create($archive)
    try {
        foreach ($path in $paths) {
            $input = [System.IO.File]::OpenRead($path)
            try { $input.CopyTo($output) } finally { $input.Dispose() }
        }
    } finally { $output.Dispose() }

    if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLower() -ne $spec.archive_sha256) {
        Remove-Item $archive -Force -ErrorAction SilentlyContinue
        throw "$Name — فایل نهایی سالم نیست؛ دوباره اجرا کنید"
    }

    Write-Host "      باز کردن فایل‌ها" -ForegroundColor DarkGray
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Expand-Archive-Overwriting -Archive $archive -Target $target

    Remove-Item $archive -Force -ErrorAction SilentlyContinue
    # The parts are only useful for a re-run; once unpacked they are dead weight.
    foreach ($path in $paths) { Remove-Item $path -Force -ErrorAction SilentlyContinue }
    Write-Host "   $Name آماده شد." -ForegroundColor Green
}

$components = if ($Component -eq "both") { @("runtime", "models") } else { @($Component) }
foreach ($name in $components) { Install-Component -Name $name }

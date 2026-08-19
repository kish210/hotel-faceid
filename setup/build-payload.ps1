<#
.SYNOPSIS
    Packages the Python runtime and the recognition models for download.

.DESCRIPTION
    The full installer carries ~900 MB of runtime and models, which makes a
    400 MB exe. This script turns those two folders into archives, splits them
    into parts small enough to upload and re-download reliably, and writes a
    manifest the installer reads.

    The small "web" installer then fetches these on first run instead of
    carrying them, so the file people download is a couple of megabytes.

    Run after setup\build.ps1 has assembled setup\payload.
#>
param(
    [int]$PartMegabytes = 64,
    [string]$BaseUrl = "https://github.com/kish210/hotel-faceid/releases/download/payload-v1"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$payload = Join-Path $root "setup\payload"
$out = Join-Path $root "setup\dist\payload"

New-Item -ItemType Directory -Force -Path $out | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem

$manifest = [ordered]@{
    version  = 1
    base_url = $BaseUrl
    parts    = [ordered]@{}
}

foreach ($component in @("runtime", "models")) {
    $source = Join-Path $payload $component
    if (-not (Test-Path $source)) { throw "missing $source — run setup\build.ps1 first" }

    $archive = Join-Path $out "$component.zip"
    Write-Host "`n== packing $component" -ForegroundColor Cyan
    Remove-Item $archive -Force -ErrorAction SilentlyContinue

    # Models are .onnx — already compressed data, so squeezing them costs
    # minutes and saves almost nothing. The runtime is mostly text.
    $level = if ($component -eq "models") {
        [System.IO.Compression.CompressionLevel]::Fastest
    } else {
        [System.IO.Compression.CompressionLevel]::Optimal
    }

    [System.IO.Compression.ZipFile]::CreateFromDirectory($source, $archive, $level, $false)
    $size = (Get-Item $archive).Length
    Write-Host ("   {0} MB" -f [math]::Round($size / 1MB, 1))

    Write-Host "   splitting and hashing"
    $partSize = $PartMegabytes * 1MB
    $parts = @()
    $stream = [System.IO.File]::OpenRead($archive)
    try {
        $buffer = New-Object byte[] (4MB)
        $index = 0
        while ($stream.Position -lt $stream.Length) {
            $index++
            $name = "{0}.zip.{1:d3}" -f $component, $index
            $partPath = Join-Path $out $name
            $partStream = [System.IO.File]::Create($partPath)
            try {
                $written = 0
                while ($written -lt $partSize -and $stream.Position -lt $stream.Length) {
                    $want = [math]::Min($buffer.Length, $partSize - $written)
                    $read = $stream.Read($buffer, 0, $want)
                    if ($read -le 0) { break }
                    $partStream.Write($buffer, 0, $read)
                    $written += $read
                }
            } finally { $partStream.Dispose() }

            $parts += [ordered]@{
                name   = $name
                size   = (Get-Item $partPath).Length
                sha256 = (Get-FileHash $partPath -Algorithm SHA256).Hash.ToLower()
            }
        }
    } finally { $stream.Dispose() }

    $manifest.parts[$component] = [ordered]@{
        archive_size   = $size
        archive_sha256 = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLower()
        parts          = $parts
    }

    Remove-Item $archive -Force
    Write-Host ("   {0} parts" -f $parts.Count) -ForegroundColor Green
}

$manifestPath = Join-Path $root "setup\payload-manifest.json"
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding utf8
Write-Host "`nmanifest: $manifestPath" -ForegroundColor Green
Get-ChildItem $out | Select-Object Name, @{N="MB";E={[math]::Round($_.Length/1MB,1)}} | Format-Table -AutoSize

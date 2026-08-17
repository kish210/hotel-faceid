# Builds the portable HotelFaceID-Standalone.zip (no Docker needed).
# Run:  powershell -ExecutionPolicy Bypass -File build-zip.ps1
$src = "C:\HotelFaceID\standalone"
$out = "C:\HotelFaceID\HotelFaceID-Standalone.zip"
$tmp = "$env:TEMP\hfid-pack"
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $tmp | Out-Null

$include = @("app", "faceservice", "web\dist", "fonts", "runtime", "models", ".env", "start.bat", "stop.bat", "test-standalone.py", "test-face.jpg", "hotel-faceid.iss")
foreach ($p in $include) {
    $full = Join-Path $src $p
    if (Test-Path $full) {
        Copy-Item $full -Destination $tmp -Recurse -Force
    }
}

# strip python __pycache__ and tests to keep the zip lean
Get-ChildItem $tmp -Recurse -Directory -Filter __pycache__ -ErrorAction SilentlyContinue | ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

if (Test-Path $out) { Remove-Item $out -Force }
Compress-Archive -Path "$tmp\*" -DestinationPath $out -CompressionLevel Fastest
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
"Created $out ($([math]::Round((Get-Item $out).Length/1MB,1)) MB)"
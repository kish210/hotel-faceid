# Tail live logs from all services. Ctrl+C to stop.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Push-Location $root
try {
    docker compose logs -f --tail=50
} finally {
    Pop-Location
}

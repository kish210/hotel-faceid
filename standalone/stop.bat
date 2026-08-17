@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'runtime';" ^
  "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\"" ^
  "| Where-Object { $_.CommandLine -like \"$root*\" -and ($_.CommandLine -match 'uvicorn app.main' -or $_.CommandLine -match 'faceservice.main') }" ^
  "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host ('Stopped PID ' + $_.ProcessId) }"
echo Done. You can also close the two "HotelFaceID-*" console windows.
endlocal
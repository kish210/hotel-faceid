@echo off
rem Launch the Hotel Face-ID installer in a visible PowerShell window.
rem Inno Setup calls this file so quoting stays trivial.
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"

@echo off
rem Launched by the update installer, and usable on its own afterwards.
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0update.ps1"

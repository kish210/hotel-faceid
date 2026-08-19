@echo off
rem Windows startup entry: bring the services up without opening a browser
rem or leaving a console window on screen.
cd /d "%~dp0.."
powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0start.ps1" -NoBrowser

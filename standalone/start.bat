@echo off
setlocal
cd /d "%~dp0"

if not exist "data" mkdir "data"
if not exist "data\media" mkdir "data\media"

echo [1/2] Starting Hotel Face-ID API on http://localhost:8000 ...
start "HotelFaceID-API" /min runtime\python\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo [2/2] Starting face-service (capture + recognition API on :8001) ...
start "HotelFaceID-FaceService" /min runtime\python\python.exe -m faceservice.main

timeout /t 8 /nobreak >nul
start "" http://localhost:8000
echo.
echo Hotel Face-ID is starting.
echo   Web UI :  http://localhost:8000   (admin / admin)
echo   Close the two "HotelFaceID-*" console windows to stop.
endlocal
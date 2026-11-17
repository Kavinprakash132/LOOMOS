@echo off
setlocal
echo ============================================================
echo   LOOMOS PRODUCTION LAUNCHER (Real Shed DB: loomos.db)
echo ============================================================

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "LOOMOS_DB_PATH=%BACKEND%\data\loomos.db"
set "LOOMOS_DEMO_MODE=false"

for /f "usebackq delims=" %%i in (`"%BACKEND%\.venv\Scripts\python.exe" -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(('8.8.8.8',80)); print(s.getsockname()[0]); s.close()" 2^>nul`) do set "LAN_IP=%%i"
if "%LAN_IP%"=="" set "LAN_IP=localhost"

echo Applying migrations on REAL database (%LOOMOS_DB_PATH%)...
pushd "%BACKEND%"
".venv\Scripts\alembic.exe" upgrade head
if errorlevel 1 (
    echo Migration failed!
    popd
    pause
    exit /b 1
)
popd

echo Starting LOOMOS Backend on 0.0.0.0:8000 ...
start "LOOMOS Backend (REAL)" cmd /k "cd /d "%BACKEND%" && set LOOMOS_DB_PATH=%LOOMOS_DB_PATH% && set LOOMOS_DEMO_MODE=false && .venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000"

echo Starting LOOMOS Frontend on 0.0.0.0:5173 ...
start "LOOMOS Frontend (REAL)" cmd /k "cd /d "%FRONTEND%" && npm run dev"

timeout /t 3 >nul
echo.
echo   Laptop URL : http://127.0.0.1:5173
echo   Phone Wi-Fi: http://%LAN_IP%:5173
echo   (If Phone does not connect, allow Python/Node on Private Networks in Windows Firewall)
echo.
start "" "http://127.0.0.1:5173"
endlocal

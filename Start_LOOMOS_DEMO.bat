@echo off
setlocal
echo ============================================================
echo   LOOMOS DEMO LAUNCHER (Isolated DB: loomos_demo.db)
echo   Real database loomos.db will NOT be touched.
echo ============================================================

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "LOOMOS_DB_PATH=%BACKEND%\data\loomos_demo.db"
set "LOOMOS_DEMO_MODE=true"

for /f "usebackq delims=" %%i in (`"%BACKEND%\.venv\Scripts\python.exe" -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(('8.8.8.8',80)); print(s.getsockname()[0]); s.close()" 2^>nul`) do set "LAN_IP=%%i"
if "%LAN_IP%"=="" set "LAN_IP=localhost"

pushd "%BACKEND%"
if /I "%~1"=="clean" (
    echo Resetting ONLY loomos_demo.db to empty Setup Wizard state...
    ".venv\Scripts\python.exe" scripts\seed_demo_cli.py --clean
) else (
    if not exist "%LOOMOS_DB_PATH%" (
        echo Seeding isolated demo database loomos_demo.db...
        ".venv\Scripts\python.exe" scripts\seed_demo_cli.py --demo
    ) else (
        ".venv\Scripts\alembic.exe" upgrade head
    )
)
popd

echo Starting LOOMOS Backend (DEMO DB) on 0.0.0.0:8000 ...
start "LOOMOS Backend (DEMO)" cmd /k "cd /d "%BACKEND%" && set LOOMOS_DB_PATH=%LOOMOS_DB_PATH% && set LOOMOS_DEMO_MODE=true && .venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000"

echo Starting LOOMOS Frontend (DEMO MODE) on 0.0.0.0:5173 ...
start "LOOMOS Frontend (DEMO)" cmd /k "cd /d "%FRONTEND%" && npm run dev"

timeout /t 3 >nul
echo.
echo   DEMO MODE ACTIVE (loomos_demo.db)
echo   Laptop URL : http://127.0.0.1:5173
echo   Phone Wi-Fi: http://%LAN_IP%:5173
echo   Demo Owner : welcome123 / welcome123
echo   Demo Sup   : sup_siva  / supPassword1
echo.
start "" "http://127.0.0.1:5173"
endlocal

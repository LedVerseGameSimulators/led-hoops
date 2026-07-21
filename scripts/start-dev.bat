@echo off
REM Start Hoops dev stack (API 8000, ws_bridge 8765, UI 5173).
setlocal
cd /d "%~dp0.."

echo ==^> LED Hoops dev stack from %CD%

start "LED Hoops API" cmd /k "cd /d %CD% && set "USE_SERIAL_HD=1" && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000"
timeout /t 2 /nobreak >nul
start "LED Hoops ws_bridge" cmd /k "cd /d %CD% && python ws_bridge.py"
timeout /t 2 /nobreak >nul
start "LED Hoops Frontend" cmd /k "cd /d %CD%\frontend && npm run dev"

echo.
echo Hoops ready:
echo   UI:        http://localhost:5173
echo   API:       http://localhost:8000
echo   ws_bridge: http://localhost:8765
echo.
echo Close the three command windows to stop the stack.
endlocal

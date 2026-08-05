@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%CD%"

title LED Hoops - Starting
echo.
echo ========================================
echo   LED HOOPS - Starting game
echo   Mode: HARDWARE + simulator
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 goto no_python

where node >nul 2>&1
if errorlevel 1 goto no_node

if not exist "games\setting\led_parameter.dat" goto no_settings

if not exist "frontend\node_modules" goto need_npm
goto after_npm

:need_npm
echo First run: installing frontend packages (may take a few minutes)...
pushd frontend
call npm install
if errorlevel 1 (
  echo ERROR: npm install failed.
  popd
  pause
  exit /b 1
)
popd

:after_npm
echo Stopping any previous game windows...
call "%ROOT%\STOP_GAME.bat" /quiet
ping -n 3 127.0.0.1 >nul

echo Starting floor engine with HARDWARE mode (API port 8000)...
start "LED Hoops API" /D "%ROOT%" cmd /k "call scripts\run-api-hardware.bat"
ping -n 4 127.0.0.1 >nul

echo Starting bridge (port 8765)...
start "LED Hoops ws_bridge" /D "%ROOT%" cmd /k "python ws_bridge.py"
ping -n 3 127.0.0.1 >nul

echo Starting game UI (port 5173)...
start "LED Hoops Frontend" /D "%ROOT%\frontend" cmd /k "npm run dev"
ping -n 5 127.0.0.1 >nul

echo Waiting for game UI...
set /a _tries=0

:wait_ui
set /a _tries+=1
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://localhost:5173' -UseBasicParsing -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto ui_ready
if %_tries% GEQ 30 goto ui_timeout
ping -n 2 127.0.0.1 >nul
goto wait_ui

:ui_timeout
echo WARNING: UI did not respond yet. Opening browser anyway.
goto check_hw

:ui_ready
echo UI is ready.

:check_hw
echo Checking hardware mode...
powershell -NoProfile -Command "try { $r = Invoke-RestMethod -Uri 'http://localhost:8000/hw-debug' -TimeoutSec 5; if ($r.use_serial_hd) { Write-Host 'HARDWARE MODE: ON' } else { Write-Host 'ERROR: HARDWARE MODE OFF - floor will stay dark'; exit 2 } } catch { Write-Host 'WARNING: could not confirm hardware mode yet'; exit 0 }"
if errorlevel 2 goto hw_failed

:open_browser
start "" "http://localhost:5173"

echo.
echo ========================================
echo   LED HOOPS is running (HARDWARE)
echo ========================================
echo   Open:  http://localhost:5173
echo   Floor LEDs should light when you start a game.
echo   Leave the three black windows open.
echo   To stop: double-click STOP_GAME.bat
echo ========================================
echo.
pause
exit /b 0

:hw_failed
echo.
echo ERROR: API started without hardware mode.
echo Check the "LED Hoops API" window for errors.
echo.
pause
exit /b 1

:no_python
echo ERROR: Python not found.
echo Install Python 3.11 and add it to PATH, then try again.
pause
exit /b 1

:no_node
echo ERROR: Node.js not found.
echo Install Node.js LTS and try again.
pause
exit /b 1

:no_settings
echo ERROR: Floor settings missing.
echo Expected file: games\setting\led_parameter.dat
echo Ask a technician to copy settings onto this PC.
pause
exit /b 1

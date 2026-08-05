@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "QUIET=%~1"
if /i not "%QUIET%"=="/quiet" (
  title LED Hoops - Stopping
  echo.
  echo ========================================
  echo   LED HOOPS - Stopping game
  echo ========================================
  echo.
)

REM Kill by window titles started by START_GAME.bat
taskkill /FI "WINDOWTITLE eq LED Hoops API*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq LED Hoops ws_bridge*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq LED Hoops Frontend*" /T /F >nul 2>&1

REM Also free ports (works even if window titles differ)
powershell -NoProfile -Command ^
  "foreach ($p in 8000,8765,5173) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }" >nul 2>&1

if /i "%QUIET%"=="/quiet" (
  endlocal
  exit /b 0
)

echo.
echo LED Hoops stopped. Ports 8000 / 8765 / 5173 are free.
echo You can close this window.
echo.
pause
endlocal

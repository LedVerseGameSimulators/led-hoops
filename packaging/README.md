# Windows freeze scripts (placeholders — run on Windows PC/VM or CI windows-latest)
#
# Primary operator artifact: Nuitka
#   packaging\build_nuitka_windows.ps1
# Secondary fallback: PyInstaller onedir
#   packaging\build_pyinstaller_windows.ps1
#
# These cannot be fully exercised on macOS. Mirror the Mac scripts:
#   1. npm ci && npm run build
#   2. Stage allowlist (ui/, games data, simulator/static, STOP, README)
#   3. Freeze packaging\run_api.py → hoops-api.exe
#      packaging\run_bridge.py → hoops-bridge.exe
#      packaging\supervisor.py → "LED Hoops.exe"
#   4. Assert no *.py in stage
#   5. Zip as LED-Hoops-<tag>-nuitka-windows.zip / -pyinstaller-windows.zip
#
# See docs/PLAN_KIOSK_AND_PACKAGING.md (repo parent) for the locked matrix.

"""Per-product constants. This is the only file that differs between game repos."""

SLUG = "hoops"            # kiosk profile slug, release/zip names
DISPLAY_NAME = "LED Hoops"
API_PORT = 8000           # must match frontend/src/config.js
BRIDGE_PORT = 8765
# Ports freed on STOP (same set STOP_GAME.bat frees; 5173 = legacy vite preview).
STOP_PORTS = (8000, 8765, 5173)

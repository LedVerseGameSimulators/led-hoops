# LED Hoops — Operator Guide

Simple start / play / stop for floor staff. No coding needed.

## Start

1. Double-click **`START_GAME.bat`** in this folder.
2. Wait until you see **LED HOOPS is running (HARDWARE)**.
3. The API window must say **HARDWARE MODE ON**.
4. The browser should open at **http://localhost:5173**.
5. Leave the three black command windows open while playing.
6. When a game starts, the **physical floor** and the on-screen sim both run.

## Play

1. On the login screen, scan a card **or** choose **Play as Guest**.
2. Pick a level and start.
3. Use **one browser tab only**.
4. The physical floor and the on-screen simulator run together.

## Stop

1. Double-click **`STOP_GAME.bat`**.
2. Wait until it says the game stopped.
3. Close any leftover black windows if they are still open.

## Common fixes

| Problem | What to do |
|---------|------------|
| Start says Python not found | Ask tech to install Python 3.11 with “Add to PATH”. |
| Start says Node.js not found | Ask tech to install Node.js LTS. |
| Start says floor settings missing | Ask tech to copy `games\setting\` files onto this PC. |
| Browser page blank / won’t load | Wait 10–15 seconds after start, then refresh. Or run `STOP_GAME.bat`, then `START_GAME.bat` again. |
| Floor LEDs dark but game runs in browser | Check USB cable to the floor controller. Run start again. |
| Two games fighting each other / freeze | Close all browser tabs, run `STOP_GAME.bat`, then start once with one tab. |
| Need to reboot game mid-day | `STOP_GAME.bat` → wait → `START_GAME.bat`. |

## Notes

- These buttons only **run and stop** LED Hoops on this PC.
- They do **not** change Wi‑Fi / LAN / RFID server settings.
- Port used by the game UI: **5173**.

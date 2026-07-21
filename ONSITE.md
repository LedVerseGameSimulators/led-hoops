# On-Site Hardware Integration Guide — LED Hoops

> **For Cursor agent:** Follow every step in order. Do not skip verification steps. Do not touch the RFID server, SQL server, or any service already running on this PC.

---

## Game Config

| Key | Value |
|-----|-------|
| Game | LED Hoops |
| Grid | 1 row × 6 cols |
| COM ports | 1 (read from shelve — see Step 4) |
| Layout type | read from shelve |
| Display var | `led_display` |
| Zip extract dir | `C:\activerse\led-hoops` |
| Python version | 3.10 or 3.11 (3.12+ may have issues with decompiled code) |
| Server port | 8000 |

---

## Step 1 — Extract the zip

1. Download zip to `C:\activerse\` (create folder if missing)
2. Extract so the structure is:
   ```
   C:\activerse\led-hoops\
     api\
     games\
     frontend\
     scripts\
     ...
   ```
3. Open **Command Prompt as Administrator** (Start → cmd → right-click → Run as administrator). Use this terminal for all remaining steps.

---

## Step 2 — Check Python

```cmd
python --version
```

**Expected:** `Python 3.10.x` or `3.11.x`

**If not found or wrong version:**

Option A — winget (Windows 10/11):
```cmd
winget install Python.Python.3.11
```

Option B — manual: download `python-3.11.x-amd64.exe` from python.org, install with "Add to PATH" checked, then re-open terminal.

Verify again:
```cmd
python --version
pip --version
```

Both must respond before continuing.

---

## Step 3 — Install dependencies

```cmd
cd C:\activerse\led-hoops
pip install -r api\requirements.txt
pip install pyserial httpx
```

**Expected:** packages install without error. Ignore deprecation warnings.

`pyserial` is required for floor COM access; `httpx` is required by the
bridge/debug tooling.

**If any package fails on Windows build tools:**
```cmd
pip install --only-binary :all: -r api\requirements.txt
pip install pyserial httpx
```

---

## Step 4 — Verify shelve (hardware config)

```cmd
cd C:\activerse\led-hoops\games
python -c "import shelve; db=shelve.open('setting/led_parameter',flag='r'); [print(k,'=',db[k]) for k in db.keys()]; db.close()"
```

**Expected output includes:**
- `list_com_info` — list of COM port entries, e.g. `[['COM3 (USB Serial...)', 1, 6]]`
- `led_layout_type` — integer (layout)
- `value_high` — rows (should be 1)
- `value_width` — cols (should be 6)

**If shelve missing or empty:** STOP — the `games/setting/led_parameter` shelve must exist. It was pre-populated from the original Windows machine. Do not proceed without it.

Note the COM port name (e.g. `COM3`) — compare it with Windows in Step 5.

---

## Step 5 — Verify COM port is visible to Windows

Open Device Manager → Ports (COM & LPT). The USB-serial adapter for the floor should appear (e.g. `USB Serial Port (COM3)`).

```cmd
python -c "import serial.tools.list_ports; [print(p) for p in serial.tools.list_ports.comports()]"
```

**Expected:** COM3 (or whatever the shelve says) appears in the list.

**If COM port missing:** USB cable not connected, or driver not installed. This floor uses a **WCH USB-Serial adapter** — install the WCH driver: search "WCH CH340 driver Windows" or "WCH CH9102 driver" and download from wch.cn or wch-ic.com. After install, replug USB and re-run the check.

---

## Step 6 — Run hardware diagnostic

Run this standalone diagnostic **before** the full stack. Confirm that the
API and any other process that could own the floor COM port are stopped.

From `games\`:

```cmd
cd C:\activerse\led-hoops\games
python test_hardware.py
```

The equivalent repository-root command is:

```cmd
cd C:\activerse\led-hoops
python games\test_hardware.py
```

**Expected sequence:**
1. Prints COM ports + grid dims from shelve
2. Reports successful serial initialization
3. Shows all six columns at once in six distinct colors
4. Runs six one-column output phases; only columns 0, 1, 2, 3, 4, and 5
   respectively should light
5. Opens a 15-second input window by default. For each column 0..5, start
   released, press it, then release it; the script reports `CYCLE COMPLETE`
   only after that full post-baseline cycle
6. Prints a per-column `PASS`/`MISSING` result, blanks the floor, and closes
   serial

Output and input durations are configurable:

```cmd
python games\test_hardware.py --output-duration 2 --input-duration 30
```

From `games\`, omit the `games\` prefix. Exit code `0` means all six cycles
completed; `1` means one or more cycles were missing **or** an unexpected
runtime error occurred; `2` means configuration, serial-initialization, or
timing validation failed; `130` means interrupted. Pre-layout validation
touches no floor. After layout/diagnostic initialization is entered, cleanup
attempts to blank the floor and close serial. Do not assume every possible
CLI exit can blank hardware.

**If `Serial initialization passed.` but no lights:** check cable from controller box to floor tiles. Check power to floor controller.

**If COM port open error:** wrong COM port number, or port in use by another process. Check Device Manager for actual port name and update shelve if needed (see Troubleshooting).

---

## Step 7 — Start all three services

```cmd
cd C:\activerse\led-hoops
scripts\start-dev.bat
```

This opens three command windows:

1. FastAPI on port 8000 with `USE_SERIAL_HD=1`
2. `ws_bridge.py` on port 8765
3. React/Vite on port 5173

The standalone diagnostic must already have exited so the API can own COM.

---

## Step 8 — Start a game and verify hardware initialization

1. Open `http://localhost:5173`.
2. Start a game through the UI.
3. Check the API command window.

`_hw_init()` runs when the game starts, not when Uvicorn merely starts.
After starting the game, the expected API log includes:
```
Hardware ready: 1 port(s), 1×6, layout=X
```

If you see `Hardware init failed: ...`, stop all three services so the API
releases COM, re-run Step 6, then restart at Step 7.

---

## Step 9 — Verify sim + hardware both working

1. All three services from Step 7 must remain running
2. Open browser on this PC → `http://localhost:5173`
3. Start a game through the UI
4. Confirm: floor tiles receive color data (LEDs respond to game state)
5. Confirm: stepping on a tile registers in the game (score or state change)

Both sim output (browser canvas) and hardware (physical floor) run simultaneously.

---

## What NOT to touch

- Do not stop or restart the **RFID server** or **SQL server** running on this PC
- Do not change port 8000 if RFID/game integration is already wired to it
- Do not modify `games/setting/led_parameter` shelve — it contains calibrated hardware config

---

## Troubleshooting

**Wrong COM port in shelve:**
```python
import shelve
db = shelve.open('games/setting/led_parameter')
# Print current
print(db['list_com_info'])
# Update port name only (keep indices):
# db['list_com_info'] = [['COM4 (USB Serial Port)', 1, 6]]
db.close()
```
Only do this if Device Manager confirms COM port changed.

**`ModuleNotFoundError` on startup:** from the `led-hoops` directory run
`pip install -r api\requirements.txt`, then `pip install pyserial httpx`.

**Floor lights but no input (PRESS not detected):** sensor cable may be separate from LED cable. Confirm both data cables connected.

**Port already in use (8000):** `netstat -ano | findstr :8000` to find PID, then `taskkill /PID <pid> /F`.

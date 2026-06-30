# On-Site Hardware Integration Guide — LED Hoops

> **For Cursor agent:** Follow every step in order. Do not skip verification steps. Do not touch the RFID server, SQL server, or any service already running on this PC.

---

## Game Config

| Key | Value |
|-----|-------|
| Game | LED Hoops |
| Grid | 1 row × 6 cols |
| COM ports | 1 (read from shelve — see Step 5) |
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
     requirements.txt
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
pip install -r requirements.txt
```

**Expected:** packages install without error. Ignore deprecation warnings.

**If `pyserial` fails:** `pip install pyserial` manually.

**If any package fails on Windows build tools:**
```cmd
pip install --only-binary :all: -r requirements.txt
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

Note the COM port name (e.g. `COM3`) — you'll need it in Step 6.

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

```cmd
cd C:\activerse\led-hoops\games
python test_hardware.py
```

**Expected sequence:**
1. Prints COM ports + grid dims from shelve
2. `All COM ports opened OK`
3. Floor lights up **green** for 3 seconds
4. Prints `Reading sensors for 5s — step on tiles to test...`
5. When you step on a tile: `PRESS detected: row=0 col=X`
6. `Floor cleared. Done.`

**If `All COM ports opened OK` but no lights:** check cable from controller box to floor tiles. Check power to floor controller.

**If COM port open error:** wrong COM port number, or port in use by another process. Check Device Manager for actual port name and update shelve if needed (see Troubleshooting).

---

## Step 7 — Find the server start command

```cmd
dir C:\activerse\led-hoops\*.bat C:\activerse\led-hoops\*.cmd C:\activerse\led-hoops\start*.py 2>nul
```

If a `start.bat` or `run.bat` exists, inspect it first:
```cmd
type C:\activerse\led-hoops\start.bat
```

If no start script, use the manual command in Step 8.

---

## Step 8 — Start game server with hardware enabled

```cmd
cd C:\activerse\led-hoops
set USE_SERIAL_HD=1
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**Expected startup log includes:**
```
Hardware ready: 1 port(s), 1×6, layout=X
```

If you see `Hardware init failed: ...` — re-run Step 6 to diagnose serial issue before proceeding.

**PowerShell alternative:**
```powershell
$env:USE_SERIAL_HD="1"
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

## Step 9 — Verify sim + hardware both working

1. Server must be running (Step 8 terminal stays open)
2. Open browser on this PC → `http://localhost:8000` (or simulator URL)
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

**`ModuleNotFoundError` on startup:** run `pip install -r requirements.txt` again from the `led-hoops` directory.

**Floor lights but no input (PRESS not detected):** sensor cable may be separate from LED cable. Confirm both data cables connected.

**Port already in use (8000):** `netstat -ano | findstr :8000` to find PID, then `taskkill /PID <pid> /F`.

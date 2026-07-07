# LED Hoops — Windows Hardware Integration Handoff

**Date:** June 2026  
**Target machine path:** `C:\activerse\led-hoops`  
**Hardware:** 1×6 hoop strip, WCH USB-Serial (COM3), floor layout from `games/setting/led_parameter`

This document lists everything changed to run the React frontend + headless API + physical LED floor on Windows, and how to deploy on a new PC.

---

## 1. Architecture (3 services)

| Service | Port | Purpose |
|---------|------|---------|
| **React frontend** | 5173 | Game launcher UI (Guest/RFID login, level select, simulator iframe) |
| **FastAPI (`api/`)** | 8000 | Game logic, hardware serial I/O when `USE_SERIAL_HD=1` |
| **ws_bridge** | 8765 | Polls API, broadcasts LED frames to simulator canvas via WebSocket |

**User URL:** http://localhost:5173 (not 8000 or 8765 alone)

Quick start (Windows):

```cmd
C:\activerse\led-hoops\scripts\start-dev.bat
```

Or three separate terminals — see `ONSITE.md` Step 8.

---

## 2. Environment setup (Windows)

### Required software

- **Python 3.10 or 3.11** (3.12+ may break decompiled game code)
- **Node.js LTS** (for frontend)
- **WCH USB-Serial driver** (CH340/CH9102) if COM port not visible

### Install commands

```cmd
cd C:\activerse\led-hoops
pip install -r api\requirements.txt
pip install pyserial httpx
cd frontend
npm install
```

### Hardware test (before full stack)

```cmd
cd C:\activerse\led-hoops\games
python test_hardware.py
```

Expected: all 6 tiles green 3s, step detection, floor cleared.

---

## 3. Code changes for integration

### 3.1 New files

| File | Purpose |
|------|---------|
| `api/` | FastAPI server wrapping headless game loop |
| `ws_bridge.py` | WebSocket bridge: API → simulator iframe |
| `frontend/` | React UI (Vite, port 5173) |
| `simulator/static/index.html` | 1×6 hoop canvas (embedded in iframe) |
| `scripts/start-dev.bat` | Starts all 3 services on Windows |
| `scripts/debug_sim.py` | API test: start game, poll `led_display` |
| `games/test_hardware.py` | COM open, green pattern, sensor read |
| `ONSITE.md` | Step-by-step onsite guide |
| `WINDOWS_HARDWARE_INTEGRATION.md` | This document |

### 3.2 `api/game_manager.py` — headless game + hardware

- **`HeadlessLedTable`**: In-memory LED table (no tkinter). Same interface as original `LedTable`.
- **`USE_SERIAL_HD=1`**: Enables real serial via `games/led/led_control.py`.
- **`_hw_init()`**: Opens COM ports from `games/setting/led_parameter` shelve, calls `init_layout` + `init_com`.
- **Per-frame callback**: Builds `led_display` (6 RGB values), scores input, updates game state for API/simulator.
- **Hardware I/O** (each frame when `USE_SERIAL_HD=1`):
  - `draw_screen_by_com()` — send colors to floor
  - `update_screen_state_by_com()` every 3rd frame — read step sensors
- **`_setup_level()` fix**: Level files are 1×5 but hardware is 1×6. LED table is **never shrunk below** shelve `value_width` (6):

  ```python
  lr = max(lr, _hw_rows)
  lc = max(lc, _hw_cols)
  ```

  Without this, `draw_screen_by_com` hits `IndexError` and the API can crash.

- **Mock imports**: When `USE_SERIAL_HD=0`, tkinter/serial are mocked so sim-only mode works without hardware.

### 3.3 `api/main.py` — REST endpoints

Key endpoints used by frontend/simulator:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/start-game` | POST | Create + start game thread |
| `/game-state/{id}` | GET | Poll score, life, `led_display` |
| `/active-game` | GET | Resume game after page reload |
| `/game-input` | POST | Simulator tile press/release |
| `/health` | GET | API alive check |

### 3.4 `ws_bridge.py` — simulator feed

- Polls `GET /active-game` at ~60 Hz
- Broadcasts `{type:"frame", rows, cols, grid}` to WebSocket clients
- Forwards tile clicks to `POST /game-input`
- **Windows fix**: Replaced Unicode `✓`/`✗` in print statements with `[OK]`/`[ERR]` (GBK console `UnicodeEncodeError` crashed bridge → blank simulator)

### 3.5 `frontend/` — React launcher

- **`SimulatorScreen.jsx`**: iframe → `http://localhost:8765?game_id=...`
- **`App.jsx`**: On load, calls `/active-game` to resume in-progress game
- **`config.js`**: API port 8000, ws_bridge port 8765

### 3.6 `simulator/static/index.html`

- WebSocket URL includes `?game_id=` from query string
- Renders 1×N hoop strip from ws_bridge frames

### 3.7 `games/led/led_control.py` — serial + decompile fixes

| Fix | Detail |
|-----|--------|
| **`read()` empty buffer** | Return early when `in_len == 0` (was `UnboundLocalError`) |
| **`debug_parameter` path** | Resolve relative to `games/setting/`, not CWD |
| **`yanqian()` import** | `encryption/yanqian.py` — dongle check bypassed (`return True`) |

### 3.8 `games/encryption/yanqian.py`

USB dongle verification bypassed for standalone Windows install (no physical dongle).

### 3.9 `games/game_play/game_util.py`

- **`half_up()`**: Fixed Python 3.11 `Decimal.quantize()` call (decompile bug)

### 3.10 `games/led/led_control_c.py`

- Same class of fixes as `led_control.py` where applicable

---

## 4. Hardware configuration (do not change casually)

Stored in **`games/setting/led_parameter`** shelve (binary, from original machine):

| Key | Typical value |
|-----|---------------|
| `list_com_info` | `[['WCH USB-SERIAL Ch A (COM3)', '1', '6', 'floor_light']]` |
| `value_high` | `1` (one row) |
| `value_width` | `6` (six hoops) |
| `led_layout_type` | `0` |

Verify:

```cmd
cd C:\activerse\led-hoops\games
python -c "import shelve; db=shelve.open('setting/led_parameter',flag='r'); print('COM:', db.get('list_com_info')); print('Grid:', db.get('value_high'), 'x', db.get('value_width')); db.close()"
```

---

## 5. Known issues / open items

### 6th hoop (column index 5)

- Level files (`.led`) are authored for **5 columns** (0–4).
- Hardware has **6 columns** (0–5).
- With current (reverted) code: **hoops 1–5 work**, **6th hoop stays dark** during gameplay.
- `test_hardware.py` proves the 6th tile works electrically.
- A future fix needs **minimal mapping** (only stretch last level column → hardware col 5) without remapping cols 0–3.

### API crash on serial

- Heavy COM3 traffic can crash the Python process (`exit code 0xC0000005`).
- If simulator goes blank, check if API is still running on port 8000.
- **Sim-only test:** `set USE_SERIAL_HD=0` before starting API — confirms simulator independent of serial.

### Multiple browser tabs

- Each `/start-game` call **kills the previous game**.
- Use **one browser tab** only.

---

## 6. Deploy on a new Windows PC

1. Extract zip to `C:\activerse\led-hoops`
2. Install Python 3.11 + Node.js LTS
3. `pip install -r api\requirements.txt` + `pyserial httpx`
4. `cd frontend && npm install`
5. Copy **`games/setting/led_parameter`** from original machine if not in zip
6. Install WCH driver, verify COM port in Device Manager
7. Run `python games\test_hardware.py`
8. Run `scripts\start-dev.bat`
9. Open http://localhost:5173 → Guest → play

---

## 7. Debug commands

```cmd
REM API health
curl http://localhost:8000/health

REM Active game + LED colors
curl http://localhost:8000/active-game

REM ws_bridge status
curl http://localhost:8765/status

REM Automated game test
cd C:\activerse\led-hoops
python scripts\debug_sim.py
```

---

## 8. What NOT to touch on onsite PC

- RFID server / SQL server already running
- `games/setting/led_parameter` shelve (calibrated hardware config)
- Port 8000 if other services depend on it

---

## 9. File change summary (quick reference)

```
NEW:     api/                    (entire FastAPI layer)
NEW:     ws_bridge.py
NEW:     frontend/               (React UI)
NEW:     scripts/start-dev.bat
NEW:     scripts/debug_sim.py
NEW:     ONSITE.md
MODIFIED: games/led/led_control.py      (read fix, paths)
MODIFIED: games/encryption/yanqian.py   (dongle bypass)
MODIFIED: games/game_play/game_util.py  (half_up Python 3.11)
MODIFIED: simulator/static/index.html   (game_id in WebSocket URL)
MODIFIED: frontend/src/screens/SimulatorScreen.jsx (iframe game_id)
```

**Reverted (do not re-apply without testing):** `_scale_level_to_hardware` column remapping — caused 4th/5th hoop bugs and simulator issues.

---

*For step-by-step onsite setup, see `ONSITE.md`.*

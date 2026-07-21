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

Run the standalone diagnostic first, then start the stack; see `ONSITE.md`
Steps 6–8.

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

From the repository root:

```cmd
cd C:\activerse\led-hoops
python games\test_hardware.py
```

From `games\`, use `python test_hardware.py`. Expected: an all-six
distinct-color phase, six one-column-only phases (each followed by a
manual yes/no confirmation), then a default 15-second input window. Each
column 0..5 requires a released baseline → press → release cycle.
Exit codes are `0` only when all seven output phases are manually confirmed
and all six input cycles complete; `1` means one or more output
confirmations failed, one or more input cycles are missing, or an
unexpected runtime error occurred; `2` means configuration,
serial-initialization, or timing validation failed; and `130` means
interrupted. Pre-layout validation touches no floor. Blank/close cleanup is
attempted after entering layout/diagnostic initialization; it is not a
guarantee for every possible CLI exit. Automated tests cover buffers and
confirmation plumbing; physical lights remain onsite PENDING. Durations are
configurable, for example:

```cmd
python games\test_hardware.py --output-duration 2 --input-duration 30
```

Automated software evidence (run from the repository root; this does not
replace physical validation):

```cmd
python -m unittest tests.test_level_scaling tests.test_level_preparation tests.test_hoop6_gameplay tests.test_hardware_config tests.test_hardware_diagnostic tests.test_hardware_boot
```

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
| `games/test_hardware.py` | Six-column output/input matrix and cleanup |
| `ONSITE.md` | Step-by-step onsite guide |
| `WINDOWS_HARDWARE_INTEGRATION.md` | This document |

### 3.2 `api/game_manager.py` — headless game + hardware

- **`HeadlessLedTable`**: In-memory LED table (no tkinter). Same interface as original `LedTable`.
- **`USE_SERIAL_HD=1`**: Enables real serial via `games/led/led_control.py`.
- **`_hw_init()`**: Opens COM ports from `games/setting/led_parameter` shelve, calls `init_layout` + `init_com`.
- **Per-frame callback**: Builds `led_display` (6 RGB values), scores input, updates game state for API/simulator.
- **Hardware I/O** (each throttled hardware frame when `USE_SERIAL_HD=1`):
  - `draw_screen_by_com()` — send colors to floor
  - `update_screen_state_by_com()` — read step sensors immediately after
    that frame's draw
  - Runtime draw/read/blank operations share one serial lock; `_hw_init()`
    does not run under that runtime lock.
- **Source-parity level preparation**: Each fresh five-column archive is
  scaled once, before setup, to configured `grid_rows` × `grid_cols`
  dimensions. For `group.scale='both'`, columns map `0→0`, `1→1`,
  `2→{2,3}`, `3→4`, `4→5`. `group.scale='none'` uses source `none2edge`
  behavior:
  `0→0`, `1→1`, `2→2`, `3→4`, `4→5`; zone/activity end `5→6`.
  Simulator, hardware, scoring, and movement then use physical coordinates
  directly, with no inverse remap. This replaces the old minimum-width
  padding description.

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

- **Implemented and automated-verified; onsite revalidation pending.**
- Root cause: five-column archive geometry was placed in a six-column minimum
  table without source scaling, so affected groups did not populate physical
  column 5.
- The definitive source mappings and exactly-once fresh-load lifecycle are in
  §3.2. All downstream systems use the resulting physical 1×6 coordinates.
- The old ad-hoc `_scale_level_to_hardware` attempt was reverted because it
  differed from source behavior and caused fourth/fifth-hoop and simulator
  regressions. That historical attempt is not the current implementation.
- Automated tests cover mappings; real levels `001`, `003`, `007`, `DK01`,
  and `DK03`; 1×6 display/hardware serialization; simulator and fake-sensor
  column-5 scoring; goal/red/deduct/moving/two-player/restart behavior; and
  the diagnostic. Physical lights, sensors, gameplay, marathon/restart, and
  blank-on-stop remain onsite checks.

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
3. Run `pip install -r api\requirements.txt`, then
   `pip install pyserial httpx`
4. `cd frontend && npm install`
5. Copy **`games/setting/led_parameter`** from original machine if not in zip
6. Install WCH driver, verify COM port in Device Manager
7. Run `python games\test_hardware.py` and require all six output positions
   plus all six released → pressed → released input cycles
8. Run `scripts\start-dev.bat`
9. Open http://localhost:5173 → Guest → start a game; only then require the
   API log to show `Hardware ready` (Uvicorn startup alone does not open COM)

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

**Historical note:** the old ad-hoc `_scale_level_to_hardware` remapping was
reverted because it differed from source behavior and caused fourth/fifth-hoop
and simulator issues. The current source-parity implementation supersedes it.

---

*For step-by-step onsite setup, see `ONSITE.md`.*

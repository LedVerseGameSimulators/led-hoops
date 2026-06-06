# Hoops — Development Playbook & Status

**Last updated:** 2026-06-07  
**Repo:** `/Users/apple/activerse_final_changes/led-hoops`  
**Original source:** `hoops/ledplay/` (decompiled under `games/`)  
**Reference pattern:** `../CLIMB_MIGRATION_PLAYBOOK.md`, `../led-hexagon/`

---

## What this game is

LED **hoop backboard strip** game — typically **1 row × up to 6 columns** (one lit column = one hoop target).  
Players “make shots” by triggering the sensor on a lit hoop column.

| Mode | Behavior |
|------|----------|
| **1P** | Score on PLUS_ARR colors (orange, blue, yellow, cyan, magenta, white) |
| **2P (DK `.ledb`)** | P1 = blue `(0,0,254)`, P2 = orange `(254,128,0)`, separate scores |
| **Hazards** | RED → score + life penalty (rate-limited). DEDUCT → score only |
| **Safe** | GREEN shields from red while active |
| **Session** | 5-min marathon through a level series; score + lives persist across levels |

Headless stack runs **without Tkinter** and **without physical hardware** — simulator + API only. Original hardware drivers remain in `games/` for a future integration pass.

---

## Status at a glance

| Area | Status |
|------|--------|
| Headless API + game loop | ✅ Done |
| React kiosk UI + simulator | ✅ Done |
| Level loading (casual / level / DK) | ✅ Done |
| Session marathon + wave skip | ✅ Done |
| 2P DK scoring | ✅ Done (sim verified) |
| Cover / disappear hidden tiles | ✅ Done |
| Parallel dev ports (8000 / 8765 / 5173) | ✅ Done |
| Hardware serial LED output | ⏳ Pending — code exists, not wired |
| Hardware sensor input | ⏳ Pending — code exists, not wired |
| RFID wedge login on kiosk | ⚠️ Partial — API ready, UI manual entry |
| MySQL player DB in prod | ⚠️ Optional — fails open in dev |
| Audio / idle video | ⏳ Pending — mocked |
| Production deploy / CI | ⏳ Pending |

---

## Architecture

```
led-hoops/
├── api/
│   ├── main.py              # FastAPI — login, start-game, game-input, game-state
│   ├── game_manager.py      # Play lifecycle, session loop, HeadlessLedTable, scoring
│   ├── config.py            # GAMES_ROOT, ports, DB env
│   ├── database.py          # MySQL (optional) + SQLite leaderboard
│   └── models.py
├── games/                   # Full decompiled ledplay tree (gitignored in parts)
│   ├── game_play/
│   │   ├── Play.py          # MODIFIED — get_game_speed, deal_all_direction fixes
│   │   ├── game_hw.py       # Hardware glue (NOT used by API yet)
│   │   └── game_running.py  # Original Tkinter kiosk entry
│   ├── led/                 # Serial drivers — led_control, communication
│   ├── gui/                 # Original editor + scoring (reference for parity)
│   ├── gui2/                # Real LedTable (tkinter) — reference only
│   ├── model/setting.py     # USE_SERIAL_HD = True
│   ├── source/
│   │   ├── -/               # casual 1P (*.led)
│   │   ├── --/              # level 1P (*.led)
│   │   └── ---/             # DK 2P (*.ledb)
│   └── setting/             # led_parameter + debug_parameter (shelve, often local)
├── frontend/                # React (Vite) — login → settings → simulator → result
├── simulator/static/
│   └── index.html           # 1×N hoop strip canvas
├── ws_bridge.py             # Polls API → WebSocket frames to simulator iframe
└── scripts/
    ├── start-dev.sh         # One-shot dev stack
    └── setup_settings.sh    # Copy shelve settings from original ledplay install
```

### Data flow (current — simulator)

```
React UI → POST /start-game → GameManager thread → Play.running_by_blue()
                ↓
         frame callback → led_display → GET /game-state
                ↓
         ws_bridge (~60fps) → simulator iframe WebSocket
                ↓
         click hoop → POST /game-input → press_cell → try_score_cell
```

### Data flow (future — hardware)

```
Play.update → led_table.led_table
                ↓
         GameHW.draw_hw_led_color → led_control.draw_screen_by_com → serial OUT
                ↓
         led_control.update_screen_state_by_com → state_table ← serial IN
                ↓
         try_score_cell / calculation_editor_group_scode parity
```

---

## Run locally

```bash
cd led-hoops

# First time: copy real shelve settings from original install
./scripts/setup_settings.sh
# or: HOOPS_LEDPLAY=/path/to/hoops/ledplay ./scripts/setup_settings.sh

# All three services
./scripts/start-dev.sh
```

| Service | Port | URL |
|---------|------|-----|
| Frontend | 5173 | http://localhost:5173 |
| API | 8000 | http://localhost:8000/health |
| ws_bridge | 8765 | http://localhost:8765 (simulator iframe) |

Run alongside Climb (8001/8766/5174) and Hex (8002/8767/5175) — ports are fixed per game.

---

## What has been done

### Core headless migration
- [x] FastAPI backend decoupled from Tkinter
- [x] `HeadlessLedTable` — in-memory grid matching LedTable interface
- [x] Mock all GUI / serial / audio imports in `game_manager.py` for headless import
- [x] Load real settings from `games/setting/led_parameter` + `debug_parameter`
- [x] Level load from `.led` / `.ledb` ZIP → shelve (`play_order=False` gameplay only)
- [x] Per-level grid resize from `para_key_game` (often 1×5 or 1×6)

### Gameplay fidelity
- [x] `Play.py` decompiler fixes: `get_game_speed` default, rigid-bounce `deal_all_direction`
- [x] Session marathon — level series from chosen start through end of series
- [x] Score + lives + 5-min timer persist across levels
- [x] Priority overlap resolution (green > red/deduct > scoreable)
- [x] Wave skip when scoreable wave cleared (~1s delay before next wave)
- [x] Cover / disappear mode for hidden scoreable tiles (`blue_hide_max_time`)
- [x] Live press scoring + consume-on-hit (moving levels)
- [x] Breath/pulse on scoreable hoops in simulator display
- [x] 2P DK scoring: `.ledb` + `player_count >= 2` → P1 blue / P2 orange
- [x] `effectivePlayerCount` + `player_count` in start-game from frontend

### Frontend
- [x] Hoops-only game selection screen
- [x] Login → settings (category + level + difficulty + 2P) → countdown → simulator → result
- [x] P1/P2 score panels in 2P mode
- [x] Resume active game on reload (`/active-game`)
- [x] Centralized `frontend/src/config.js` for API/ws URLs

### DevOps / repo hygiene
- [x] `scripts/start-dev.sh` with dedicated ports
- [x] `scripts/setup_settings.sh` for shelve bootstrap
- [x] `.gitignore` for `*.rar` source archives and shelve runtime files

### Git milestones (recent)
| Commit | Summary |
|--------|---------|
| `90498ea` | Initial headless stack |
| `4706a19` | Gameplay mechanics + settings setup |
| `b6d4955` | 2P scoring, gameplay regressions, frontend flow |
| `bc15354` | Parallel dev ports + config.js |
| `31d0851` | Ignore source `.rar` archives |

---

## Pending checklist

Use this as the living backlog. Check items off in PRs; update **Last updated** when the doc changes.

### P0 — Before hardware floor test
- [ ] **Hardware mode design** — choose Option A (sidecar bridge) vs Option B (`HARDWARE_MODE` in game_manager); document in this file
- [ ] **COM port validation** — run solid-color test pattern per column on real WCH controller; confirm 1×6 mapping matches `list_com_info` in shelve
- [ ] **Sensor polarity** — confirm serial byte `10` = shot on your install (`led_control.read`)
- [ ] **Edge-trigger scoring** — if sensors hold high, score on rising edge only (avoid double score vs current press + per-frame loop)
- [ ] **Windows kiosk** — USB dongle (`encryption/yanqian.py` + `use_dll/Dongle_d.dll`) or controlled lab bypass
- [ ] **CWD / paths** — ensure process runs with `games/` as cwd or patch `./setting/` relative paths in `led_control`

### P1 — Hardware integration (glue layer)
- [ ] Stop mocking `serial`, `led.*` when hardware mode enabled
- [ ] Wire `GameHW.init_hw_led` + `draw_hw_led_color` after each frame (or sidecar equivalent)
- [ ] Wire `update_screen_state_by_com` → `HeadlessLedTable.state_table`
- [ ] Align display source: hardware should use `led_table.led_table` post-`Play.update`, not only priority `cell_win` buffer (verify visual parity)
- [ ] Input bridge: serial → `/game-input` or direct `press_cell` / `release_cell`
- [ ] Smoke test: one casual level end-to-end on floor with no React simulator

### P2 — Kiosk / production readiness
- [ ] Fix `_SCORES_DB` hardcoded path in `api/database.py` → repo-local or env var
- [ ] MySQL `DBOperation` connection for real RFID player lookup (or seed dev players)
- [ ] RFID keyboard-wedge capture on LoginScreen (auto-focus + scan-to-submit)
- [ ] Session time deduction / `update_session_start` wired to match original kiosk
- [ ] Production start script (systemd / Windows service) — API + ws_bridge optional on floor
- [ ] Environment docs: `DB_*`, `GAMES_ROOT`, `API_PORT`, `HOOPS_LEDPLAY`

### P3 — Polish & parity
- [ ] Audio feedback (score ding, red buzz) via Web Audio or `audio_play` in hardware mode
- [ ] Idle / attract loop video (original `game_running` idle path)
- [ ] Leaderboard score normalization (`game_scode_divide_person`, `game_scode_divide_time`)
- [ ] Automated smoke test script (API health, level load, one simulated shot)
- [ ] E2E test for 2P DK level with two simulated players

### P4 — Out of scope / later
- [ ] Wall / screen LED paths (`wall_light=False` on current Hoops install — skip unless hardware adds walls)
- [ ] Original Tkinter editor / admin GUI
- [ ] Multi-game parent launcher polish (`../scripts/start-all-games.sh`)

---

## How to continue development

### New session quick-start

```bash
cd /Users/apple/activerse_final_changes/led-hoops
git pull
./scripts/setup_settings.sh   # if setting/*.dat missing
./scripts/start-dev.sh
# open http://localhost:5173 — pick Hoops only (not kavida_claude or other Vite on 5173)
```

Read this file + skim `api/game_manager.py` frame callback (`_frame_callback`) before changing scoring.

### Adding a gameplay fix

1. Reproduce in simulator (note level id, 1P vs 2P, moving vs static).
2. Compare behavior to `games/gui/gui_editor_game.py` (`calculation_editor_group_scode`) for original intent.
3. Change logic in `api/game_manager.py` (not `Play.py` unless movement/decompiler issue).
4. Restart API only (`lsof -ti:8000 | xargs kill; uvicorn …`) — frontend/ws_bridge can stay up.
5. Update **Pending checklist** or **What has been done** in this doc.

### Starting hardware integration

Original stack is **present but not imported** by the API path:

| Module | Purpose |
|--------|---------|
| `games/led/led_control.py` | Serial RGB out + sensor read, 115200 baud |
| `games/led/communication.py` | pyserial wrapper |
| `games/game_play/game_hw.py` | Init COM, draw + read cycle |
| `games/gui/gui_editor_game.py` | Reference frame order: draw → read → score |
| `games/encryption/yanqian.py` | Dongle gate before `init_com` |

**Recommended approach when on the floor:**

1. Validate serial with a **standalone script** calling `led_control.init_com` + test pattern (no game_manager changes yet).
2. Add **`HARDWARE_MODE=1`** (or separate `hardware_bridge.py`) that:
   - Reads `games/setting/led_parameter` for `list_com_info`, `value_high`, `value_width`
   - Subscribes to `/game-state` → pushes colors
   - Reads serial → POSTs `/game-input`
3. Once stable, merge into `game_manager` as a second I/O backend alongside `HeadlessLedTable`.

Do **not** remove mocks until hardware path is tested — keep simulator working for dev.

### Level buckets (API `/levels`)

| Category | Path | 2P |
|----------|------|-----|
| `casual` | `source/-/*.led` | No |
| `level` | `source/--/*.led` | No |
| `dk` | `source/---/*.ledb` | Yes (when `player_count=2`) |

---

## Key settings (shelve)

From `games/setting/led_parameter` (machine-specific):

| Key | Typical Hoops value | Notes |
|-----|---------------------|-------|
| `value_high` | `1` | Grid rows (hoop strip) |
| `value_width` | `6` | Max hoop columns |
| `game_time_sw` | `5.0` | Session minutes |
| `life_value_sw` | `20` | Starting lives |
| `list_com_info` | `[COM3, 1, 6, floor_light]` | Serial mapping |
| `wall_light` | `False` | No wall boards on current install |
| `blue_hide_max_time_sw` | ~20s | Cover disappear timing |

Copy from original install: `./scripts/setup_settings.sh`

---

## Common pitfalls

1. **Wrong frontend on 5173** — must be `led-hoops/frontend`, not another Vite app; stale processes bind wrong ports.
2. **Don't use mocked `gui2.LedTable`** — always `HeadlessLedTable` in API path.
3. **2P scoring** — only `.ledb` + `player_count >= 2`; 1P `.led` files stay combined score even with two card IDs.
4. **Footer `P1: xxx | P2: xxx`** — card IDs, not scores.
5. **Settings missing** — without `games/setting/*.dat`, defaults apply (1×6 grid); run `setup_settings.sh`.
6. **Hardware on macOS** — dongle DLL is Windows-only; serial init skipped even if code present.
7. **Display vs logic** — simulator uses `cell_win` + breath; hardware will use `led_table` unless aligned intentionally.

---

## Related docs

| Doc | Location |
|-----|----------|
| Climb migration pattern | `../CLIMB_MIGRATION_PLAYBOOK.md` |
| Parallel multi-game ports | `../scripts/start-all-games.sh` |
| Hex playbook (if exists) | `../led-hexagon/docs/` |

---

## Quick reference — important files

| File | Why |
|------|-----|
| `api/game_manager.py` | Session loop, scoring, led_display, mocks |
| `api/main.py` | HTTP routes, `/game-input` |
| `games/game_play/Play.py` | Movement, `running_by_blue` |
| `frontend/src/screens/SimulatorScreen.jsx` | Start game, 2P, stop |
| `ws_bridge.py` | Simulator WebSocket feed |
| `simulator/static/index.html` | Hoop strip UI |
| `games/led/led_control.py` | Future hardware output/input |
| `games/game_play/game_hw.py` | Future hardware init/update |

---

*Update this document when closing pending items or changing architecture.*

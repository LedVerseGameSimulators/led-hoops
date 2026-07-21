# Hardware Validation — LED Hoops

> **Read this before an on-site hardware session.** It states what hardware
> integration exists, what has and hasn't been validated on the real floor,
> and gives a concrete checklist to run through on-site.

---

## 1. What hardware integration exists

- **Grid:** 1 row × 6 columns (single hoop strip, 6 physical hoop positions,
  column index 0–5).
- **COM ports:** 1 serial port (WCH USB-Serial adapter), port name/index read
  from the `games/setting/led_parameter` shelve (`list_com_info`), not
  hardcoded.
- **Mechanism:**
  - `USE_SERIAL_HD` env var (`api/game_manager.py`) gates all hardware code
    paths. Default `0` (sim-only); set to `1` to drive the real floor.
  - `_hw_init()` — called once per game start when `USE_SERIAL_HD=1`. Reads
    `games/setting/led_parameter` (COM port list, layout type, grid
    dimensions), calls `led.led_control.init_layout(...)` and
    `led.led_control.init_com(list_com_info)` to open the serial port(s).
  - Per-frame output: `_hw_led_control.draw_screen_by_com(_hw_layout_type, grid)`
    — pushes the same `led_display` buffer the simulator renders, throttled
    to `_HW_DRAW_INTERVAL` (~22 fps default, `HW_DRAW_INTERVAL` env override).
  - Per-frame input: `_hw_led_control.update_screen_state_by_com(...)` reads
    floor sensor state into `state_table`, feeding the same scoring path as
    simulator clicks.
  - Runtime serial draw, sensor-read, and blank calls are wrapped in
    `_hw_serial_lock` (one lock shared across runtime I/O). Initialization is
    not performed under that lock. Runtime calls are gated by
    `USE_SERIAL_HD and _hw_led_control is not None`, so sim-only runs never
    touch the `led` module.

### Source-parity level mapping and lifecycle

The five-column archive coordinates are expanded to the configured 1×6 table
with the original game's scaling rules:

- Groups with `group.scale='both'`: `0→0`, `1→1`, `2→{2,3}`,
  `3→4`, `4→5`.
- Groups with `group.scale='none'` are treated as the source
  `none2edge` mode: `0→0`, `1→1`, `2→2`, `3→4`, `4→5`.
- Exclusive zone/activity-area end coordinate `5→6`.

This scaling runs exactly once, immediately after each fresh archive load and
before level setup. Restarts and progression load fresh archive objects, then
repeat that load → scale → setup lifecycle. The configured `grid_rows` and
`grid_cols` determine the table dimensions; this is real source scaling, not
padding to a minimum width. After preparation, simulator rendering, hardware
serialization/input, scoring, and movement all use physical coordinates
directly. There is no downstream inverse remap.

## 2. Validation history

| When | What happened | Evidence |
|------|----------------|----------|
| 2026-06-30 (`f86d7dd`) | Hardware mode (`USE_SERIAL_HD`) added: serial init, per-frame draw/read, `games/test_hardware.py` diagnostic. Decompiler slice bugs fixed in `led_control.py`/`led_control_c.py`. | commit `f86d7dd` |
| 2026-07-07 (`9cf58ff`) | **Real on-site hardware validation.** Critical runtime fixes found while testing against the physical floor: `UnboundLocalError` on empty sensor read, absolute `debug_parameter` path, bounds-check in `draw_screen_by_com`, level-size flooring to hardware dims, sensor read throttling, Windows console encoding fix in `ws_bridge.py`. | commit `9cf58ff`, `WINDOWS_HARDWARE_INTEGRATION.md` |
| 2026-07-09 (`3e22c28`) | Additional headless hardware-integration hardening (thread safety, single serial lock, RGB normalization, draw throttle) — still part of the validated hardware layer. | commit `3e22c28` |
| 2026-07-11 → 2026-07-13 (`966e77c` … `4aaf708`) | **This session's gameplay rework**, layered on top of the validated hardware code: cross-tier level marathon loop, 5-heart lives display + life=0 restart, RFID card-scan login (Mode-2 scan flow), credit-gated sessions, score-schema changes (2P identity, marathon depth, raw/normalized scores), pushable settings, persistent player badge. | commits `966e77c`, `04e1971`, `1ec084d`, `dbda5dd`, `4aaf708` |

**Bottom line:** the hardware driver itself (`_hw_init`, `USE_SERIAL_HD`,
`led.led_control` calls) is real, working code that was confirmed against a
physical LED floor as of 2026-07-07. Everything gameplay-related built since
then (marathon loop, lives, RFID, credits, settings, badge) has **not** been
re-run against that floor. It talks to the hardware through the exact same
draw/read calls, so it should work, but "should" is not "confirmed."

**Sixth-hoop source-parity fix:** implemented and automated-verified; onsite
revalidation is pending. The root cause was that five-column archive
coordinates were only placed in a table whose minimum width was six; the
archive geometry itself was not transformed, leaving physical column 5
unpopulated for affected groups. The definitive mapping and lifecycle are in
§1 above. A historical ad-hoc `_scale_level_to_hardware` attempt was reverted
because it differed from source behavior and broke the fourth/fifth hoops and
simulator. That old implementation must not be confused with the current
source-parity scaler.

**Newly added, not yet hardware-tested:** the blank-on-stop fix
(`_hw_blank_floor`, added this session — see
`docs/TODO_HARDWARE_BLANK_ON_STOP.md`) sends an all-black frame to the floor
at every session-end / stop_game / clear_all path. It is gated the same way
as normal frame draws and uses the same `draw_screen_by_com` call, so it
should work, but it has never been run against real hardware.

## 3. Validation matrix

### Automated — PASS

Run from the repository root:

```cmd
python -m unittest tests.test_level_scaling tests.test_level_preparation tests.test_hoop6_gameplay tests.test_hardware_diagnostic tests.test_hardware_boot
```

The passing suite covers:

- golden `both` and fixed `none`/`none2edge` mappings, zone/activity end
  scaling, and exactly-once fresh-load preparation;
- real levels `001`, `003`, `007`, `DK01`, and `DK03`;
- display and hardware 1×6 serialization, simulator column 5, and fake
  hardware sensor column 5 scoring on the next frame;
- goal, red, deduct, moving, two-player, restart, and fresh-reload behavior;
- diagnostic output/input, exit-result, timing validation, and cleanup unit
  tests.

These tests establish software behavior only; they do not constitute physical
floor validation. Tested DK levels assign blue to Player 1 and orange to
Player 2; there is no same-color two-player alternation.

### Onsite — PENDING

- [ ] Six per-column output phases each light only the intended physical
      column, in addition to the all-six distinct-color phase.
- [ ] Six sensor inputs each complete a released baseline → press → release
      cycle.
- [ ] Physical column 5 scores during representative single-player and
      two-player levels.
- [ ] Marathon progression and life-zero restart work on the floor.
- [ ] Gameplay blanks the floor on implemented session-end, manual-stop,
      game-exception, and pre-new-game cleanup paths.
- [ ] Separately, the standalone diagnostic blanks/closes after entering
      layout/diagnostic initialization, including when interrupted.

## 4. On-site validation procedure

Run these in order. Record pass/fail for each — don't just say "done."

- [ ] **Standalone diagnostic, before the full stack:** Ensure the API and
      any other process that could own the floor COM port are stopped. From
      the Windows repository root run
      `python games\test_hardware.py`; from `games\`, run
      `python test_hardware.py`. It sends all six distinct colors, then six
      one-column-only output phases. During the default 15-second input
      window, every column 0..5 must be observed released as a baseline, then
      pressed, then released. Durations are configurable, for example:
      `python games\test_hardware.py --output-duration 2 --input-duration 30`
      from root, or the equivalent `python test_hardware.py ...` from
      `games\`.
      Exit codes are `0` complete; `1` means one or more input cycles were
      missing **or** an unexpected runtime error occurred; `2` means
      configuration, serial-initialization, or timing validation failed; and
      `130` means interrupted. Pre-layout validation touches no floor. After
      layout/diagnostic initialization is entered, cleanup attempts to blank
      the floor and close serial; do not interpret this as a guarantee that
      every possible CLI exit can blank hardware.
- [ ] **Start the complete stack:** After the standalone diagnostic releases
      COM, run `scripts\start-dev.bat` from the repository root. This starts
      FastAPI (8000), `ws_bridge` (8765), and React (5173), with the API in
      hardware mode.
- [ ] **Start a game, then check hardware initialization:** Open
      `http://localhost:5173` and start a game. `_hw_init()` runs at game
      start, not at Uvicorn startup. Only now require
      `Hardware ready: 1 port(s), 1×6, layout=X`; fail the check if
      `Hardware init failed: ...` appears.
- [ ] **Each of the 6 hoop positions individually:** With the API running
      (`USE_SERIAL_HD=1`) or via `test_hardware.py`, verify columns 0, 1, 2,
      3, 4, AND 5 each individually light up and register a press. Pay
      specific attention to **column index 5 (the 6th hoop)**. Its
      source-parity software path is automated-verified, but physical
      gameplay revalidation is still pending.
- [ ] **Full marathon session, real hardware, end-to-end:** Play one
      complete marathon session (card scan or guest login → level 1 through
      session end) on the physical floor. Confirm:
  - [ ] Score increments correctly on scoring hoops (physical + simulator UI
        agree).
  - [ ] Lives (5-heart display) decrement correctly on misses; life=0
        mid-session (with time remaining) triggers a level restart with
        refilled HP, not a hard game-over.
  - [ ] Session ends correctly on: timeout, true game-over (life=0 with
        <10s left), or full level-sequence completion — and the correct
        `game_over_reason`/`result` shows in the UI.
  - [ ] RFID card-scan login (if a reader is present on this floor) reads
        the card and starts a session against the right player/credit
        balance.
- [ ] **Blank-on-stop fix:** Confirm the floor actually goes fully dark
      (not just the simulator UI) within ~1s of each of:
  - [ ] A session ending via timeout (no manual stop).
  - [ ] A true game-over (life=0, <10s left).
  - [ ] Manually stopping via `/logout` (or a Stop-Game control in the UI)
        mid-level.
  - [ ] A game-loop exception cleanup path, if it can be induced safely
        without touching hardware configuration.
  - [ ] Starting a **new** game while a stale pattern is showing on the
        floor (skip the blank steps above once to reproduce the stuck
        state, then start a new game) — confirm `clear_all()`'s blank fires
        before the new game's first real frame.
  - [ ] No regression: floor still draws normally during active gameplay
        (throttle/lock unaffected by the added blank calls).

Report each checklist item as **PASS** or **FAIL** with a one-line note, not
a blanket "hardware works."

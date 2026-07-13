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
  - All hardware calls are wrapped in `_hw_serial_lock` (single lock shared
    across reads/writes) and gated by `USE_SERIAL_HD and _hw_led_control is
    not None`, so sim-only runs never touch the `led` module.

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

**Known open hardware bug (not yet fixed):** the 6th hoop (column index 5).
Level files are authored for 5 columns (0–4); the physical floor has 6
(0–5). With the current (reverted) code, hoops 1–5 respond during gameplay
but the 6th hoop stays dark — `test_hardware.py` proves the 6th tile works
electrically, so this is a level/column-mapping gap, not a wiring fault. A
previous attempt at column remapping (`_scale_level_to_hardware`) was
reverted because it broke the 4th/5th hoops and the simulator — do not
re-apply without dedicated testing. See `WINDOWS_HARDWARE_INTEGRATION.md`
§5 for full detail.

**Newly added, not yet hardware-tested:** the blank-on-stop fix
(`_hw_blank_floor`, added this session — see
`docs/TODO_HARDWARE_BLANK_ON_STOP.md`) sends an all-black frame to the floor
at every session-end / stop_game / clear_all path. It is gated the same way
as normal frame draws and uses the same `draw_screen_by_com` call, so it
should work, but it has never been run against real hardware.

## 3. On-site validation checklist

Run these in order. Record pass/fail for each — don't just say "done."

- [ ] **Environment:** Start the API with `USE_SERIAL_HD=1` (see `ONSITE.md`
      Step 8). Confirm the startup log shows
      `Hardware ready: 1 port(s), 1×6, layout=X` — not
      `Hardware init failed: ...`.
- [ ] **Diagnostic script:** Run `python games\test_hardware.py` (or
      `python3` on non-Windows). Confirm: COM port(s) open OK, floor lights
      solid green for 3s, and stepping on tiles prints `PRESS detected:
      row=0 col=X` for each tile you step on.
- [ ] **Each of the 6 hoop positions individually:** With the API running
      (`USE_SERIAL_HD=1`) or via `test_hardware.py`, verify columns 0, 1, 2,
      3, 4, AND 5 each individually light up and register a press. Pay
      specific attention to **column index 5 (the 6th hoop)** — this is a
      known trouble spot (see §2 above): confirm whether it lights/scores
      correctly during actual gameplay (not just the diagnostic script,
      which drives hardware directly and is known to work) or whether the
      5-column-authored levels still leave it dark.
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
  - [ ] A level/session ending via timeout (no manual stop).
  - [ ] A true game-over (life=0, <10s left).
  - [ ] Manually stopping via `/logout` (or a Stop-Game control in the UI)
        mid-level.
  - [ ] Starting a **new** game while a stale pattern is showing on the
        floor (skip the blank steps above once to reproduce the stuck
        state, then start a new game) — confirm `clear_all()`'s blank fires
        before the new game's first real frame.
  - [ ] No regression: floor still draws normally during active gameplay
        (throttle/lock unaffected by the added blank calls).

Report each checklist item as **PASS** or **FAIL** with a one-line note, not
a blanket "hardware works."

# LED Hoops — Effects Implementation Plan

Implementation plan for **transition `.led` panels**, **marathon-loop wiring**, and **non-blocking audio**.

Specs:
- Global: [activerse_final_changes/docs/game-effects/GLOBAL_RULES.md](../../docs/game-effects/GLOBAL_RULES.md)
- Hoops: [EFFECTS_SPEC.md](./EFFECTS_SPEC.md)

---

## 1. Spec summary

### Locked product decisions

| Event | LED | Audio | Next step |
|-------|-----|-------|-----------|
| **Every level start** (incl. first, after clear, after fail restart) | `countdown.led` — green 3→2→1→GO | Tick/noise per step; **no BGM** | Gameplay level |
| **Level clear** (time remaining) | `level_clear.led` — all green ~2–3 s | Transition stinger; **no BGM** | Countdown → next level |
| **Level fail** (all lives lost, >10 s session time left) | `level_fail.led` — all red ~2–3 s | Transition stinger; **no BGM** | Countdown → same level restart |
| **Timer expire** (= session end) | `level_clear.led` — all green ~2–3 s | Transition stinger; **no BGM** | All LEDs black/off; **no countdown** |
| **Session over** (life=0 with ≤10 s left, sequence exhausted, stop) | Same as timer expire when applicable | Stinger then silence | Black/off; **no countdown** |
| **Active gameplay** | Normal level `.led`/`.ledb` | BGM loop + score SFX | — |
| **In-game press flash** (Hoops-only) | Red hoop blinks 1–2× on penalty/perfect press | Positive/negative score SFX | Code-side (not a `.led` panel) |

### Hoops countdown LED pattern (1×N strip, default 1×6)

| Step | Duration | Cells lit (0-indexed cols on 6-hoop board) |
|------|----------|---------------------------------------------|
| **3** | ~1 s | Middle pair: cols `2, 3` |
| **2** | ~1 s | Four hoops: cols `1, 2, 3, 4` |
| **1** | ~1 s | All hoops: cols `0…5` |
| **GO** | ~0.3 s | Hold all green, then gameplay |

Scale group coordinates via existing `prepare_level_for_platform()` when `grid_cols` ≠ 6.

---

## 2. Code audit — what exists vs missing

### Exists (reuse)

| Area | Location | Notes |
|------|----------|-------|
| Marathon session loop | `api/game_manager.py` — `_run_game()`, lines ~1902–1972 | Iterates `level_sequence`; handles `_level_cleared`, `_restart_level`, `_session_over` |
| Level load + play | `_load_level_file()` (~443), `_run_level_attempt()` (~552), `Play.running()` / `running_by_blue()` | ZIP → shelve → `dict_group`; main gameplay = `play_order=False` |
| Platform scaling | `prepare_level_for_platform()` (~478), `api/level_scaling.py` | Mutates groups for 1×6 (or configured) hoop strip |
| LED frame I/O | `_build_hoops_led_display()`, `_write_hoops_hardware_frame()`, `HeadlessLedTable` | Publishes `led_display` to state + HW |
| Life restart | `_frame_callback` life≤0 branch (~1721–1727); restart loop (~1957–1963) | Refills HP when >10 s session time left; **no fail panel** |
| Level clear detection | Board time exceeded (~1741–1743); all scoreables done (~1814–1821) | Sets `_level_cleared`; **no clear panel** |
| Timer session end | `session_elapsed > game_time_sec` (~1733–1737, ~1924–1927) | Sets `_session_over`, `result=2`; **no clear panel before blank** |
| In-game flash | `game.flashes` + `_build_hoops_led_display()` (~942–953) | White 0.4 s blink on consume; **not red per spec** |
| Audio primitives | `games/audio_play/audio.py` | `play()` (SFX channel), `play_bmg()` (mixer.music), non-blocking channels |
| Audio thread | `games/util/audio_play_thread.py` | Dedicated thread for long clips |
| Original fragment model | `games/gui/gui_editor_game2.py` (~903–915) | After gameplay: load `game.clap_light` / `game.game_accomplished` sub-shelve, `running(dict_group_end, True)` |
| Original music map | `games/game_play/game_music.py` | Maps `count_down`, `bmg_video`, `clap_light`, `game_accomplished`, score/blood mp3s; **`waitting_music_end()` blocks** |
| Frontend pre-session countdown | `frontend/src/screens/CountdownScreen.jsx` | 3-2-1-GO with Web Audio synth; **once per session, before `start-game`** |
| Frontend gameplay HUD | `frontend/src/screens/SimulatorScreen.jsx` | Polls `/game-state`; synth score/hurt beeps; **no phase/countdown overlay** |
| Transition input gating (reference) | `led-grid/api/game_manager.py` — `begin_level_transition()`, `finish_level_transition()`, `transition_consumer` in `_run_level_attempt()` | **Not ported to Hoops** |

### Missing

| Gap | Impact |
|-----|--------|
| `games/source/effects/` directory and `.led` assets | No transition panels |
| `_play_led_panel()` / effect runner in marathon loop | Levels start/stop with no countdown or transition hold |
| Per-level countdown in backend | Spec requires countdown before **every** level; only frontend pre-session countdown exists |
| `phase` / `countdown_step` in game state | UI cannot sync with hoop LEDs during transitions |
| Non-blocking audio service wired into `game_manager` | `audio_play` mocked in sim (~93–94); `GameMusic` never invoked headlessly |
| BGM start/stop tied to gameplay boundaries | BGM policy (play only during active level) unenforced |
| Transition stingers | No asset path or fire-and-forget playback |
| `level_fail.led` before life restart | Restart loop jumps straight to reload |
| `level_clear.led` on timer expire before blank | Session ends with last gameplay frame frozen until `_hw_blank_floor()` |
| Red 1–2× blink on penalty press | Current flash is white on consume only |
| `read_game_parameter_game_frag()` | Stubbed `pass` in `game_util.py` (~620) — not needed if standalone effect `.led` files are used |

---

## 3. Architecture — `.led` effects via same play path

### Design principle

Transition panels are **mini `.led` files** loaded with `_load_level_file()` and played with the **same `Play.running()` loop** as gameplay. Do not add a parallel solid-fill renderer as the primary mechanism.

Effect files live at:

```
games/source/effects/
  countdown.led      # 3-2-1-GO green expansion
  level_clear.led    # all green hold ~2.5 s
  level_fail.led     # all red hold ~2.5 s
```

Optional bundled mp3s (stinger / ticks) can sit inside each ZIP under an `audio/` subfolder (mirrors gameplay `.led` layout) or in a shared `games/audio/` directory.

### Helper: `_play_led_panel`

Add to `api/game_manager.py` (names illustrative; match repo style):

```python
EFFECTS_DIR = os.path.join(GAMES_ROOT, "source", "effects")

def _effect_path(name: str) -> str:
    return os.path.join(EFFECTS_DIR, f"{name}.led")

def _play_led_panel(game, play, led_table, path, *, phase, settings,
                    audio_svc=None, stinger=None, countdown_ticks=False):
    """Load one effect .led, run Play.running() until timeline ends.
    Blocks the game thread for LED timing only (same as gameplay).
    Audio is fire-and-forget — never wait on mixer."""
    _set_input_acceptance(game, False)
    game.update_state(phase=phase, accepting_input=False, countdown_step=None)

    dg, go = _load_level_file(path)
    if not dg:
        logger.warning(f"Effect missing or corrupt: {path}")
        return

    dg, go = prepare_level_for_platform(dg, go, settings)
    board_time = max((getattr(g, "end_time_sec", 0) for g in dg.values()), default=3.0)

    # Stop BGM before any transition/countdown
    if audio_svc:
        audio_svc.stop_bgm()
        if stinger:
            audio_svc.play_sfx(stinger)  # non-blocking

    def _effect_frame(play_self, dgroup, time_pass, total_pass):
        session_elapsed = time.time() - game.session_start
        # Publish LED frame (reuse classification/display path or simple group draw)
        led_display = _build_effect_led_display(dgroup, total_pass, led_table)
        if countdown_ticks:
            step = _countdown_step_from_pass(total_pass)  # 3,2,1,0
            if step != game._last_countdown_step:
                game._last_countdown_step = step
                if audio_svc and step in (3, 2, 1):
                    audio_svc.play_sfx(audio_svc.tick_sfx)
                game.update_state(countdown_step=step if step else "go")
        game.update_state(
            phase=phase,
            led_display=led_display,
            time_left=max(0, game.game_time_sec - session_elapsed),
            accepting_input=False,
        )
        _write_hoops_hardware_frame(...)  # if USE_SERIAL_HD
        time.sleep(0.01)
        if total_pass >= board_time or not game.running:
            return False
        return True

    prev_cb = play.callback
    play.callback = _effect_frame
    play.running_state = True
    play.total_pass = 0
    use_order = bool(getattr(go, "play_order", True))  # effects may use play_order=True
    if use_order:
        play.running(dg)
    else:
        play.running_by_blue(dg)
    play.callback = prev_cb
    game._last_countdown_step = None
```

`_build_effect_led_display()` can reuse `_classify_hoops_frame` + `_build_hoops_led_display` if effect groups are `FLOOR_LIGHT`, or a thin wrapper that reads `start_member` + `color` directly from static groups.

### Marathon loop pseudocode (concrete for this repo)

Replace the inner body of `_run_game()` session loop (~1916–1972) with:

```python
EFFECT_COUNTDOWN = _effect_path("countdown")
EFFECT_CLEAR     = _effect_path("level_clear")
EFFECT_FAIL      = _effect_path("level_fail")

audio_svc = HeadlessAudioService(settings=_s)  # see §5

for lvl_path in game.level_sequence:
    if game._session_over or not game.running:
        break
    if time.time() - game.session_start > game.game_time_sec:
        game._session_over = True
        game._end_reason = "timeout"
        break

    lvl_id = os.path.basename(lvl_path).rsplit(".", 1)[0]

    # ── COUNTDOWN before every level ──
    _play_led_panel(game, play, led_table, EFFECT_COUNTDOWN,
                    phase="countdown", settings=_s, audio_svc=audio_svc,
                    countdown_ticks=True)

    while True:  # restart loop for this level
        game.current_level_id = lvl_id
        prepared = _run_level_attempt(lvl_path, game, _s, _setup_level, play)
        if prepared is None:
            break

        # BGM: active gameplay only
        audio_svc.start_bgm()

        # _run_level_attempt already ran play.running* until callback returned False
        audio_svc.stop_bgm()

        if game._session_over:
            # Timer expire (or true game-over): clear panel → blank, NO countdown
            if game._end_reason == "timeout":
                _play_led_panel(game, play, led_table, EFFECT_CLEAR,
                                phase="session_end", settings=_s,
                                audio_svc=audio_svc, stinger=audio_svc.stinger_clear)
            _hw_blank_floor(game.led_table)
            break

        if game._restart_level:
            # Lives=0, time remaining → fail → countdown → replay
            _play_led_panel(game, play, led_table, EFFECT_FAIL,
                            phase="transition_fail", settings=_s,
                            audio_svc=audio_svc, stinger=audio_svc.stinger_fail)
            game.life = game.max_life
            game._cell_red_penalty_at.clear()
            game.last_life_loss_time = 0.0
            game._restart_level = False
            _play_led_panel(game, play, led_table, EFFECT_COUNTDOWN,
                            phase="countdown", settings=_s, audio_svc=audio_svc,
                            countdown_ticks=True)
            continue

        if game._level_cleared:
            game.levels_cleared += 1
            _play_led_panel(game, play, led_table, EFFECT_CLEAR,
                            phase="transition_clear", settings=_s,
                            audio_svc=audio_svc, stinger=audio_svc.stinger_clear)
            break  # outer for advances; countdown at top of next level

    if game._session_over:
        break

# Post-loop: if session ended without timeout path above, blank floor
_resolve_session_outcome(game)
_hw_blank_floor(game.led_table)
```

**Important:** `_run_level_attempt()` today runs gameplay inside the same function. Refactor so BGM wraps the `play.running*` call explicitly (either split `_run_level_attempt` like Grid's `play_consumer`, or start/stop BGM inside `_run_level_attempt` with a `is_gameplay=True` flag).

**Life=0 with ≤10 s left:** `_frame_callback` sets `_session_over` (no `_restart_level`). Treat like session end: optional `level_clear.led` + stinger + blank (per GLOBAL_RULES session-over row).

### `play_order` for effect files

- Gameplay levels: `play_order=False` → `running_by_blue()` (current behavior).
- Effect panels: author with **`play_order=True`** and static timed groups (matches original end-fragment playback in `gui_editor_game2.py` line 913: `running(dict_group_end, True)`).
- `_load_level_file()` already prefers `play_order=False` shelve; for effects, either:
  - Author as single-board ZIP with only one shelve (loader returns it regardless), or
  - Add `_load_effect_file()` that accepts the first valid shelve without filtering by `play_order`.

---

## 4. Authoring `.led` effect files

### Tooling options

1. **Original LED editor** (if available on-site) — export mini-board with timed `normal_led` groups.
2. **Clone + edit** — copy a minimal static `.led` (e.g. `games/source/--/14.led`), replace `dict_group` timing/colors in editor.
3. **Programmatic bootstrap script** (one-time) — build shelve + ZIP from Python using `model` classes; commit resulting `.led` binaries.

### `countdown.led` (1×6, ~3.3 s total)

| Group | `start_time_sec` | `end_time_sec` | `color` | `start_member` (row,col) |
|-------|------------------|----------------|--------|--------------------------|
| step3 | 0.0 | 1.0 | green `(0,255,0)` | `(0,2), (0,3)` |
| step2 | 1.0 | 2.0 | green | `(0,1)…(0,4)` |
| step1 | 2.0 | 3.0 | green | `(0,0)…(0,5)` |
| go_hold | 3.0 | 3.3 | green | all cols |

Set `para_key_game.play_order = True`, `zone_*` to full 1×6, no moving groups (`speed=0`).

### `level_clear.led` (~2.5 s)

Single group: all cells green, `start_time_sec=0`, `end_time_sec=2.5`.

### `level_fail.led` (~2.5 s)

Single group: all cells red `(255,0,0)`, `start_time_sec=0`, `end_time_sec=2.5`.

### Validation

- `_load_level_file("games/source/effects/countdown.led")` returns non-`None` `(dg, go)`.
- `prepare_level_for_platform()` succeeds for configured `grid_rows`/`grid_cols`.
- `get_max_end_time_in_all_group(dg)` matches expected duration.
- Simulator + HW show correct colors at 0 s, 1 s, 2 s for countdown.

Reference capture timing: `~/Downloads/Hoops 2/` (design only, not UI video).

---

## 5. Non-blocking audio design

### Requirements (from GLOBAL_RULES)

- BGM **only** during active gameplay (`Play.running*` loop for a level `.led`).
- **Off** during countdown, transitions, fail/clear holds, session end.
- Countdown: tick/noise on 3-2-1 (not on GO).
- Score: positive SFX on score gain; negative on penalty/miss.
- Transition stingers ~2–3 s, fire-and-forget.

### Proposed `HeadlessAudioService`

New module: `api/audio_service.py` (or `games/audio_play/headless_audio.py`).

```python
class HeadlessAudioService:
    def __init__(self, settings):
        audio.Audio().init()
        self._bgm_path = ...      # "Thank You Not So Bad" mp3
        self._score_pos = ...     # shared positive mp3
        self._score_neg = ...     # shared negative mp3
        self._tick_sfx = ...      # countdown tick
        self._stinger_clear = ... # TBD / stock
        self._stinger_fail = ...  # TBD / stock
        self._bgm_playing = False

    def start_bgm(self):
        if not self._bgm_playing:
            audio.Audio().play_bmg(self._bgm_path, loops=-1)
            self._bgm_playing = True

    def stop_bgm(self):
        if self._bgm_playing:
            audio.Audio().stop()  # stops mixer.music
            self._bgm_playing = False

    def play_sfx(self, path):
        if path:
            audio.Audio().play(path)  # mixer.find_channel().play(Sound) — non-blocking

    # NEVER call waitting_music_end / time.sleep waiting for audio on game thread
```

| Event | Call site | Blocking? |
|-------|-----------|-----------|
| Gameplay start | After countdown, before `play.running*` | `start_bgm()` — instant |
| Gameplay end | When level callback returns | `stop_bgm()` — instant |
| Countdown tick | `_effect_frame` on step change | `play_sfx(tick)` |
| Transition stinger | Start of clear/fail panel | `play_sfx(stinger)` |
| Score +1 | `try_score_cell` goal branch | `play_sfx(score_pos)` |
| Penalty / red | `try_score_cell` red/deduct branch | `play_sfx(score_neg)` |

Use `AudioPlayThread` only if a clip must run isolated from mixer.music; prefer `Audio.play()` for short SFX.

**Sim mode:** Remove or narrow `audio_play` MagicMock in `game_manager` import shim (~93–94) when `HEADLESS_AUDIO=1` or always in production — mock only in unit tests that assert silence.

### Asset locations (TBD)

| Asset | Suggested path |
|-------|----------------|
| BGM | `games/audio/bgm_thank_you_not_so_bad.mp3` |
| Positive SFX | `games/audio/score_positive.mp3` (shared cross-game) |
| Negative SFX | `games/audio/score_negative.mp3` |
| Countdown tick | `games/audio/countdown_tick.mp3` or reuse `game_start_video` audio extract |
| Stingers | `games/audio/stinger_clear.mp3`, `stinger_fail.mp3` (stock OK) |

Extract mp3s from existing `.led` bundles under `games/source/*/*/audio/` where present.

---

## 6. Frontend sync notes

### Current flow gap

`App.jsx`: LOGIN → **CountdownScreen** (frontend-only) → SimulatorScreen → `POST /start-game`.

Backend marathon starts inside SimulatorScreen; **no per-level countdown** today. Frontend and hoop LEDs can diverge after level 1.

### Recommended approach

1. **Backend owns all countdowns** via `countdown.led` + state fields.
2. **Remove or bypass** frontend `CountdownScreen` for gameplay sync — either:
   - Start game at LOGIN, show SimulatorScreen immediately with `phase=countdown` overlay, or
   - Keep CountdownScreen as cosmetic-only for first impression but accept double countdown on level 1 (not recommended).
3. Add to `game.update_state()` payload:
   - `phase`: `"countdown" | "playing" | "transition_clear" | "transition_fail" | "session_end"`
   - `countdown_step`: `3 | 2 | 1 | "go" | null`
   - `accepting_input`: bool (already partially enforced server-side)
4. **SimulatorScreen.jsx**: When `phase === "countdown"`, render large 3-2-1-GO overlay driven by `countdown_step` from polled state (not local timer).
5. **ws_bridge.py**: Forward new fields unchanged to simulator iframe.
6. **Countdown audio**: Prefer backend ticks on HW/speaker; frontend can mute local beeps during `phase !== "playing"` to avoid double audio.

### In-game red blink (code-side)

In `_build_hoops_led_display()`, change penalty flash from white to red `(255,0,0)`, 1–2 toggles (~0.2 s period):

- Trigger in `try_score_cell` for red/deduct/goal branches (not only `_consume_cell`).
- Align with spec "1–2×" by setting `flashes[(i,j)]` with a flag or separate `flash_kind` dict.

---

## 7. File-by-file change list

### New files

- [ ] `games/source/effects/countdown.led`
- [ ] `games/source/effects/level_clear.led`
- [ ] `games/source/effects/level_fail.led`
- [ ] `api/audio_service.py` — `HeadlessAudioService`
- [ ] `games/audio/` — BGM, SFX, stinger, tick mp3s (or document extract paths)
- [ ] `scripts/build_effect_led.py` — optional one-time authoring helper
- [ ] `tests/test_effects_marathon.py` — transition sequencing tests
- [ ] `tests/test_audio_service.py` — non-blocking smoke tests

### `api/game_manager.py`

- [ ] `EFFECTS_DIR`, `_effect_path()`, `_load_effect_file()` (if needed)
- [ ] `_play_led_panel()`, `_build_effect_led_display()`, `_countdown_step_from_pass()`
- [ ] `begin_level_transition()` / `finish_level_transition()` — port from Grid for input gating during loads
- [ ] Refactor `_run_level_attempt()` to accept `play_consumer` / BGM boundaries (Grid pattern)
- [ ] Rewire `_run_game()` marathon loop (§3 pseudocode)
- [ ] Timer expire: play `level_clear.led` before `_hw_blank_floor()`
- [ ] Life restart: play `level_fail.led` + countdown before reload
- [ ] Publish `phase`, `countdown_step` in `update_state()`
- [ ] Wire `HeadlessAudioService`; score SFX in `try_score_cell()`
- [ ] Penalty flash: red 1–2× in `_build_hoops_led_display()`
- [ ] Narrow `audio_play` mock to test-only

### `games/game_play/game_music.py`

- [ ] Do **not** use blocking `waitting_music_end()` in headless path
- [ ] Optional: extract path resolution helpers for `HeadlessAudioService`

### `frontend/src/App.jsx`

- [ ] Route LOGIN → SIMULATOR (skip CountdownScreen) **or** start-game before countdown

### `frontend/src/screens/CountdownScreen.jsx`

- [ ] Deprecate or repurpose as idle/attract-only

### `frontend/src/screens/SimulatorScreen.jsx`

- [ ] Phase-aware countdown overlay from `gameState.phase` / `countdown_step`
- [ ] Disable local countdown beeps when backend drives audio
- [ ] Optional: stop synth beeps when backend SFX enabled

### `ws_bridge.py`

- [ ] Pass through `phase`, `countdown_step`

### `tests/test_level_preparation.py`

- [ ] Extend transition gating tests for effect panels

### Docs

- [ ] Update `docs/STATUS.md`, `docs/GAPS.md` when implemented

---

## 8. Risks / open questions

| Risk | Mitigation |
|------|------------|
| Double countdown on level 1 (frontend + backend) | Remove frontend CountdownScreen from critical path |
| `_load_level_file` skips `play_order=True` effect shelve | Single-shelve effect ZIPs or `_load_effect_file()` |
| Effect `.led` wrong grid size on site | Always run `prepare_level_for_platform()`; test on HW layout |
| BGM/stinger race on rapid restarts | `stop_bgm()` before every transition; idempotent audio service |
| `time.sleep(0.01)` in effect loop blocks thread | Acceptable (same as gameplay); audio must not add waits |
| Stinger assets TBD | Ship stock mp3; swap later without code change |
| Life=0 ≤10 s: fail vs clear panel | Use **clear** panel + blank per GLOBAL_RULES session-over |
| `read_game_parameter_game_frag` stub | Not needed if standalone effect `.led` files are authoritative |
| 2P `.ledb` marathon | Effects are visual-only on shared strip; same panels for 1P/2P |
| pytest without pygame display | Mock `HeadlessAudioService` in tests |

**Open questions for product**

1. Confirm stinger asset choice (single stinger vs separate clear/fail).
2. Confirm LOGIN → immediate simulator vs retain pre-session attract countdown.
3. Should frontend play score SFX when backend audio is enabled (likely no).

---

## 9. Test plan

### Simulator (default, `USE_SERIAL_HD=0`)

| # | Scenario | Expected |
|---|----------|----------|
| 1 | Start session, level 1 | `countdown.led` (3-2-1-GO) → gameplay; `phase` transitions |
| 2 | Clear level with time left | `level_clear.led` ~2.5 s → countdown → level 2 gameplay |
| 3 | Lose all lives, >10 s left | `level_fail.led` → countdown → same level reload, score kept |
| 4 | Session timer hits 0 mid-level | Gameplay stops → `level_clear.led` → LEDs off; **no** countdown |
| 5 | Clear last level in sequence | Clear panel → countdown only if time left; else session end |
| 6 | Score tile | Positive SFX; BGM continues |
| 7 | Red tile penalty | Negative SFX; red blink 1–2× on hoop |
| 8 | Stop button mid-countdown | Input locked; clean stop; floor blank |

**Commands**

```bash
cd led-hoops
pytest tests/test_effects_marathon.py tests/test_audio_service.py -q
# Manual: scripts/start-all-games.sh or frontend dev + api/main.py
```

### Hardware (`USE_SERIAL_HD=1`)

| # | Check |
|---|-------|
| 1 | Countdown greens match spec on physical 1×6 strip |
| 2 | Clear = all green; fail = all red; hold ~2–3 s |
| 3 | Timer expire → clear hold → all off |
| 4 | BGM audible only during gameplay; silent during countdown/transitions |
| 5 | Stinger audible on clear/fail; no hang on game thread |
| 6 | Session stop / logout blanks floor (`_hw_blank_floor`) |

```bash
USE_SERIAL_HD=1 python -m pytest tests/test_hardware_boot.py -q
# Full smoke: scripts/hw_mode_smoke_test.py (if present) with effects scenarios
```

### State sync

- Poll `/game-state/{id}` during countdown: `countdown_step` decrements 3→2→1→go in sync with `led_display`.
- Simulator iframe shows matching colors via ws_bridge.

---

## 10. Implementation order

1. Author three effect `.led` files + loader smoke test
2. `_play_led_panel()` + marathon loop wiring (silent)
3. `HeadlessAudioService` + BGM boundaries
4. State fields + SimulatorScreen overlay
5. Red blink + score SFX
6. Remove frontend countdown duplication
7. HW validation + pytest coverage

---

*Plan only — no runtime code changes in this commit.*

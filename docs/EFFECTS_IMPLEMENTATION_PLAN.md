# LED Hoops — Effects Implementation Plan

Implementation plan for **transition `.led` panels**, **marathon-loop wiring**, and **non-blocking audio**.

**Locked product decisions:** [docs/game-effects/LOCKED_DECISIONS.md](../../docs/game-effects/LOCKED_DECISIONS.md) — all open questions resolved there; this plan implements those locks.

Specs:
- Global: [activerse_final_changes/docs/game-effects/GLOBAL_RULES.md](../../docs/game-effects/GLOBAL_RULES.md)
- Hoops: [EFFECTS_SPEC.md](./EFFECTS_SPEC.md)

---

## Plan review (2026-08-07)

**Verdict:** **Ready for implementation** — plan body is actionable; all product decisions locked in [LOCKED_DECISIONS.md](../../docs/game-effects/LOCKED_DECISIONS.md).

| Gate | Status |
|------|--------|
| Aligns with GLOBAL_RULES + EFFECTS_SPEC + LOCKED_DECISIONS | **Pass** |
| Code audit vs `api/game_manager.py` (spot-check) | **Pass** |
| `.led` authoring path | **Pass** — study existing levels; bootstrap/test in sim (locked #12) |
| Non-blocking audio design | **Pass** — `api/audio_manager.py` `AudioManager`; BGM stop must not kill SFX channels |
| Session-end paths (timer, life≤10s, sequence done) | **Pass** — `_finish_session()` via `level_clear.led` |
| Frontend + floor countdown | **Pass** — both run, ~sync (locked #4) |
| Test plan | **Pass** |

### Findings (code audit — unchanged)

| Sev | Finding |
|-----|---------|
| **blocker** | Marathon pseudocode only played `level_clear.led` on timeout inside the inner `while`; timer/life/session-end at the **top** of the `for lvl_path` loop (current code ~L1923–1927) skipped the clear hold entirely. |
| **blocker** | `AudioManager.stop_bgm()` must **not** call `audio.Audio().stop()` — that stops **all** mixer channels and can cut transition stingers mid-play. Use `mixer.music.stop()` (+ unload) for BGM only. |
| **major** | Red penalty path in `try_score_cell()` (~L1335–1344) never sets `flashes`; only `_consume_cell()` does. Wire red blink in **red/deduct branches only** — not goal/scoring hoops (locked #11). |
| **major** | Hoops has no `begin_level_transition()` / `finish_level_transition()` on `GameInstance` (Grid has them ~L1123+). Port must add **instance methods**, not free functions only. |
| **major** | Test row “clear last level → countdown if time left” contradicts GLOBAL_RULES: sequence exhausted = **session end** → clear hold → stinger → black, **no countdown** (even with time remaining). |
| **minor** | `_run_game()` is nested inside `start_game()` (~L1528); session loop ~L1916–1972 (plan line refs were directionally correct). |
| **minor** | `ws_bridge.py` forwards `led_display` only — sufficient for iframe hoop colors; `phase` / `countdown_step` are for React HUD overlay via `/game-state` poll (optional ws_bridge passthrough). **No RFID changes** (locked #7). |
| **minor** | `games/source/effects/`, `games/audio/`, `tests/test_effects_marathon.py`, `tests/test_audio_manager.py` do not exist yet (expected). |
| **minor** | Grid plan uses `api/effects_runner.py`; Hoops inlines `_play_led_panel()` in `game_manager.py` — acceptable; extract later if tests need isolation. |

### Locked decisions (was “Open decisions for human”)

All resolved — see [LOCKED_DECISIONS.md](../../docs/game-effects/LOCKED_DECISIONS.md):

| Former open item | Locked answer |
|------------------|---------------|
| Frontend pre-session countdown | **Keep both** — UI countdown + backend `countdown.led`; keep ~in sync |
| Stinger assets | **One shared** `games/audio/transition_stinger.mp3` for clear **and** fail |
| `.led` authoring | Study existing levels; invent/bootstrap; test in sim |
| Red blink scope | **Only red (penalty) hoops** — not good/scoring hoops |
| Frontend score SFX | **Mute** SimulatorScreen synth when backend audio active |

---

## 1. Spec summary

### Locked product decisions

| Event | LED | Audio | Next step |
|-------|-----|-------|-----------|
| **Every level start** (incl. first, after clear, after fail restart) | `countdown.led` — green 3→2→1→GO | Tick/noise per step; **no BGM** | Gameplay level |
| **Level clear** (time remaining, more levels) | `level_clear.led` — all green ~2–3 s | Shared transition stinger; **no BGM** | Countdown → next level |
| **Level fail** (all lives lost, >10 s session time left) | `level_fail.led` — all red ~2–3 s | Shared transition stinger; **no BGM** | Countdown → same level restart |
| **Timer expire** (= session end) | `level_clear.led` — all green ~2–3 s | Stinger then silence | All LEDs black/off; **no countdown** |
| **Life=0 with ≤10 s left** (= session end) | `level_clear.led` — all green ~2–3 s | Stinger then silence | Black/off; **no fail panel; no countdown** |
| **Last level cleared** (= session end) | `level_clear.led` — all green ~2–3 s | Stinger then silence | Black/off; **no countdown** |
| **Active gameplay** | Normal level `.led`/`.ledb` | BGM loop + score SFX | — |
| **In-game press flash** (Hoops-only) | **Red penalty hoops only** blink 1–2× on press | Positive/negative score SFX (backend authoritative) | Code-side (not a `.led` panel) |

### Session flow (locked)

```
Every level start:
  play(countdown.led) + UI countdown (~sync) → play(gameplay) + BGM

Lives = 0 and >10 s left:
  stop BGM → play(level_fail.led) + stinger → play(countdown.led) → restart same level

Lives = 0 and ≤10 s left:
  stop BGM → play(level_clear.led) + stinger → black → session end

Level cleared (more levels remain):
  stop BGM → play(level_clear.led) + stinger → play(countdown.led) → next level

Timer expire OR last level cleared:
  stop BGM → play(level_clear.led) + stinger → black → session end
```

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
| Marathon session loop | `api/game_manager.py` — `start_game()` → nested `_run_game()`, lines ~1528 / ~1916–1972 | Iterates `level_sequence`; handles `_level_cleared`, `_restart_level`, `_session_over` |
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
| Frontend pre-session countdown | `frontend/src/screens/CountdownScreen.jsx` | 3-2-1-GO with Web Audio synth; **once per session, before `start-game`** — **keep** (locked #4) |
| Frontend gameplay HUD | `frontend/src/screens/SimulatorScreen.jsx` | Polls `/game-state`; synth score/hurt beeps; **no phase/countdown overlay** |
| Transition input gating (reference) | `led-grid/api/game_manager.py` — `GameInstance.begin_level_transition()`, `finish_level_transition()`, `transition_consumer` in `_run_level_attempt()` | **Not ported to Hoops** — add methods on Hoops `GameInstance` |

### Missing

| Gap | Impact |
|-----|--------|
| `games/source/effects/` directory and three `.led` assets | No transition panels |
| `_play_led_panel()` / effect runner in marathon loop | Levels start/stop with no countdown or transition hold |
| Per-level countdown in backend | Spec requires countdown before **every** level; only frontend pre-session countdown exists today |
| `phase` + `accepting_input` in game state | UI cannot sync with hoop LEDs during transitions |
| Non-blocking `AudioManager` wired into `game_manager` | `audio_play` mocked in sim (~93–94); `GameMusic` never invoked headlessly |
| BGM start/stop tied to gameplay boundaries | BGM policy (play only during active level) unenforced |
| Shared transition stinger | No asset path or fire-and-forget playback |
| `level_fail.led` before life restart | Restart loop jumps straight to reload |
| `level_clear.led` on timer expire before blank | Session ends with last gameplay frame frozen until `_hw_blank_floor()` |
| Red 1–2× blink on penalty press only | `try_score_cell` red branch (~1335–1344) sets no `flashes`; `_consume_cell` white flash (~942–953) |
| `read_game_parameter_game_frag()` | Stubbed `pass` in `game_util.py` (~620) — not needed if standalone effect `.led` files are used |

---

## 3. Architecture — `.led` effects via same play path

### Design principle

Transition panels are **mini `.led` files** loaded with `_load_level_file()` and played with the **same `Play.running()` loop** as gameplay. Do not add a parallel solid-fill renderer as the primary mechanism.

Effect files (exactly three — locked #2):

```
games/source/effects/
  countdown.led      # 3-2-1-GO green expansion
  level_clear.led    # all green hold ~2.5 s
  level_fail.led     # all red hold ~2.5 s
```

Shared audio (locked #5):

```
games/audio/
  transition_stinger.mp3   # one file for clear AND fail
```

Optional bundled mp3s (ticks) can sit inside each ZIP under an `audio/` subfolder or in `games/audio/`.

### Helper: `_play_led_panel` + `_finish_session`

Add to `api/game_manager.py` (names illustrative; match repo style):

```python
EFFECTS_DIR = os.path.join(GAMES_ROOT, "source", "effects")

def _effect_path(name: str) -> str:
    return os.path.join(EFFECTS_DIR, f"{name}.led")

def _finish_session(game, play, led_table, audio_mgr, *, reason: str, play_clear: bool = True):
    """Session end: optional clear hold → stinger → black. NO countdown."""
    if play_clear and reason in ("timeout", "out_of_life", "stopped"):
        _play_led_panel(
            game, play, led_table, _effect_path("level_clear"),
            phase="session_end", settings=_s, audio_mgr=audio_mgr,
            stinger=audio_mgr.transition_stinger,
        )
    elif play_clear and reason == "sequence_done":
        pass  # clear panel already played in level_cleared branch
    _hw_blank_floor(getattr(game, "led_table", None))
    game._session_over = True

def _play_led_panel(game, play, led_table, path, *, phase, settings,
                    audio_mgr=None, stinger=None, countdown_ticks=False):
    """Load one effect .led, run Play.running() until timeline ends.
    Blocks the game thread for LED timing only (same as gameplay).
    Audio is fire-and-forget — never wait on mixer."""
    game.begin_level_transition()  # GameInstance method — port from Grid
    game.update_state(phase=phase, accepting_input=False, countdown_step=None)

    dg, go = _load_effect_file(path)  # see play_order note below
    if not dg:
        logger.warning(f"Effect missing or corrupt: {path}")
        game.finish_level_transition()
        return

    dg, go = prepare_level_for_platform(dg, go, settings)
    board_time = max((getattr(g, "end_time_sec", 0) for g in dg.values()), default=3.0)

    if audio_mgr:
        audio_mgr.stop_bgm()  # music channel only — do not stop SFX channels
        if stinger:
            audio_mgr.play_sfx(stinger)

    def _effect_frame(play_self, dgroup, time_pass, total_pass):
        session_elapsed = time.time() - game.session_start
        led_display = _build_effect_led_display(dgroup, total_pass, led_table)
        if countdown_ticks:
            step = _countdown_step_from_pass(total_pass)
            if step != game._last_countdown_step:
                game._last_countdown_step = step
                if audio_mgr and step in (3, 2, 1):
                    audio_mgr.play_sfx(audio_mgr.tick_sfx)
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
    use_order = bool(getattr(go, "play_order", True))
    if use_order:
        play.running(dg)
    else:
        play.running_by_blue(dg)
    play.callback = prev_cb
    game._last_countdown_step = None
    game.finish_level_transition()
```

`_build_effect_led_display()` can reuse `_classify_hoops_frame` + `_build_hoops_led_display` if effect groups are `FLOOR_LIGHT`, or a thin wrapper that reads `start_member` + `color` directly from static groups.

**Loader:** add `_load_effect_file()` that returns the first valid shelve (accepts `play_order=True` effect boards). Single-shelve effect ZIPs also work via existing `_load_level_file()` fallback, but a dedicated loader avoids ambiguity.

### Marathon loop pseudocode (concrete for this repo)

Replace the inner body of nested `_run_game()` session loop (~1916–1972) with:

```python
EFFECT_COUNTDOWN = _effect_path("countdown")
EFFECT_CLEAR     = _effect_path("level_clear")
EFFECT_FAIL      = _effect_path("level_fail")

audio_mgr = AudioManager(settings=_s)

for lvl_index, lvl_path in enumerate(game.level_sequence):
    if game._session_over or not game.running:
        break
    if time.time() - game.session_start > game.game_time_sec:
        _finish_session(game, play, led_table, audio_mgr, reason="timeout")
        break

    lvl_id = os.path.basename(lvl_path).rsplit(".", 1)[0]

    # ── COUNTDOWN before every level ──
    _play_led_panel(game, play, led_table, EFFECT_COUNTDOWN,
                    phase="countdown", settings=_s, audio_mgr=audio_mgr,
                    countdown_ticks=True)

    while True:  # restart loop for this level
        game.current_level_id = lvl_id
        game.update_state(phase="playing", accepting_input=True, countdown_step=None)
        prepared = _run_level_attempt(lvl_path, game, _s, _setup_level, play)
        if prepared is None:
            break

        audio_mgr.start_bgm()
        # _run_level_attempt already ran play.running* until callback returned False
        audio_mgr.stop_bgm()

        if game._session_over:
            _finish_session(
                game, play, led_table, audio_mgr,
                reason=game._end_reason or "timeout",
            )
            break

        if game._restart_level:
            _play_led_panel(game, play, led_table, EFFECT_FAIL,
                            phase="level_fail", settings=_s,
                            audio_mgr=audio_mgr, stinger=audio_mgr.transition_stinger)
            game.life = game.max_life
            game._cell_red_penalty_at.clear()
            game.last_life_loss_time = 0.0
            game._restart_level = False
            _play_led_panel(game, play, led_table, EFFECT_COUNTDOWN,
                            phase="countdown", settings=_s, audio_mgr=audio_mgr,
                            countdown_ticks=True)
            continue

        if game._level_cleared:
            game.levels_cleared += 1
            _play_led_panel(game, play, led_table, EFFECT_CLEAR,
                            phase="level_clear", settings=_s,
                            audio_mgr=audio_mgr, stinger=audio_mgr.transition_stinger)
            # More levels in sequence → outer for runs countdown at top
            has_next = lvl_index + 1 < len(game.level_sequence)
            if not has_next or time.time() - game.session_start > game.game_time_sec:
                _finish_session(
                    game, play, led_table, audio_mgr,
                    reason="sequence_done", play_clear=False,
                )
            break

    if game._session_over:
        break

# Post-loop: resolve result if not already finished
if not game.get_state().get("game_over"):
    final_result, final_reason = _resolve_session_outcome(game)
    game.update_state(game_over=True, time_left=0, ...)
    if not getattr(game, "_floor_blanked", False):
        _hw_blank_floor(getattr(game, "led_table", None))
```

**Important:** `_run_level_attempt()` today runs gameplay inside the same function. Refactor so BGM wraps the `play.running*` call explicitly (either split `_run_level_attempt` like Grid's `play_consumer`, or start/stop BGM inside `_run_level_attempt` with a `is_gameplay=True` flag).

**Life=0 with ≤10 s left:** `_frame_callback` sets `_session_over` (no `_restart_level`). `_finish_session(..., reason="out_of_life")` uses **level_clear** panel + stinger + blank — **no fail panel, no countdown** (locked #8).

**External stop:** `game.running = False` mid-effect → effect callback returns False → proceed to `_finish_session(..., reason="stopped")` or immediate blank per stop handler.

### `play_order` for effect files

- Gameplay levels: `play_order=False` → `running_by_blue()` (current behavior).
- Effect panels: author with **`play_order=True`** and static timed groups (matches original end-fragment playback in `gui_editor_game2.py` line 913: `running(dict_group_end, True)`).
- `_load_level_file()` already prefers `play_order=False` shelve; for effects, either:
  - Author as single-board ZIP with only one shelve (loader returns it regardless), or
  - Add `_load_effect_file()` that accepts the first valid shelve without filtering by `play_order`.

---

## 4. Authoring `.led` effect files

**Locked (#12):** Study existing levels; invent/bootstrap our own effect `.led`; test in sim.

### Tooling options

1. **Programmatic bootstrap (recommended)** — `scripts/build_effect_led.py` builds shelve + ZIP from `model` classes for exact 1×6 timing table below; commit resulting `.led` binaries. Reproducible in CI.
2. **Original LED editor** (if available on-site) — export mini-board with timed `normal_led` groups.
3. **Clone + edit** — copy a minimal static `.led` (e.g. `games/source/--/14.led`), replace `dict_group` timing/colors in editor.

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

- `_load_effect_file("games/source/effects/countdown.led")` returns non-`None` `(dg, go)`.
- `prepare_level_for_platform()` succeeds for configured `grid_rows`/`grid_cols`.
- `get_max_end_time_in_all_group(dg)` matches expected duration.
- Optional: extend `scripts/validate_level_catalog.py` with `--path games/source/effects` (Grid pattern).
- Simulator + HW show correct colors at 0 s, 1 s, 2 s for countdown.

Reference capture timing: `~/Downloads/Hoops 2/` (design only, not UI video).

---

## 5. Non-blocking audio design

### Requirements (from GLOBAL_RULES + LOCKED_DECISIONS)

- BGM **only** during active gameplay (`Play.running*` loop for a level `.led`).
- **Off** during countdown, transitions, fail/clear holds, session end.
- Countdown: tick/noise on 3-2-1 (not on GO).
- Score: positive SFX on score gain; negative on penalty/miss — **backend authoritative** (locked #10).
- **One shared** transition stinger ~2–3 s, fire-and-forget, for clear **and** fail (locked #5).

### `AudioManager` (locked #6)

New module: `api/audio_manager.py` with class `AudioManager` — non-blocking (no game-thread waits).

```python
class AudioManager:
    def __init__(self, settings):
        audio.Audio().init()
        self._bgm_path = ...           # "Thank You Not So Bad" mp3
        self._score_pos = ...          # shared positive mp3
        self._score_neg = ...          # shared negative mp3
        self._tick_sfx = ...           # countdown tick
        self.transition_stinger = ... # games/audio/transition_stinger.mp3 (clear + fail)
        self._bgm_playing = False

    def start_bgm(self):
        if not self._bgm_playing:
            audio.Audio().play_bmg(self._bgm_path, loops=-1)
            self._bgm_playing = True

    def stop_bgm(self):
        if self._bgm_playing:
            # CRITICAL: do NOT call audio.Audio().stop() — that stops ALL
            # mixer channels and cuts stingers. Stop music channel only:
            from pygame import mixer
            mixer.music.stop()
            mixer.music.unload()
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
| Transition stinger | Start of clear/fail panel | `play_sfx(transition_stinger)` |
| Score +1 | `try_score_cell` goal branch | `play_sfx(score_pos)` |
| Penalty / red | `try_score_cell` red/deduct branch | `play_sfx(score_neg)` |

Use `AudioPlayThread` only if a clip must run isolated from mixer.music; prefer `Audio.play()` for short SFX.

**Sim mode:** Remove or narrow `audio_play` MagicMock in `game_manager` import shim (~93–94) when `HEADLESS_AUDIO=1` or always in production — mock only in unit tests that assert silence. Guard `AudioManager` init so pytest without pygame display still passes (inject mock in tests).

**Never call:** `GameMusic.waitting_music_end()`, `audio.play_sync()`, or any `time.sleep` waiting for clip completion on the game thread.

### Asset locations

| Asset | Path |
|-------|------|
| BGM | `games/audio/bgm_thank_you_not_so_bad.mp3` |
| Positive SFX | `games/audio/score_positive.mp3` (shared cross-game) |
| Negative SFX | `games/audio/score_negative.mp3` |
| Countdown tick | `games/audio/countdown_tick.mp3` or reuse `game_start_video` audio extract |
| **Transition stinger** | **`games/audio/transition_stinger.mp3`** — clear **and** fail |

Extract mp3s from existing `.led` bundles under `games/source/*/*/audio/` where present.

---

## 6. Frontend sync notes

### Current flow

`App.jsx`: LOGIN → **CountdownScreen** (frontend-only) → SimulatorScreen → `POST /start-game`.

Backend marathon starts inside SimulatorScreen; **no per-level backend countdown** today. After level 1, UI and hoop LEDs can diverge.

### Locked approach (#4, #7, #10)

1. **Keep both countdowns** — frontend UI countdown **and** backend `countdown.led` on floor; keep approximately in sync.
2. **Level 1:** CountdownScreen runs pre-session; backend also plays `countdown.led` at first level start — accept brief overlap; align step timing where practical.
3. **Levels 2+:** SimulatorScreen overlay driven by backend `phase` / `countdown_step` from `/game-state` poll.
4. Add to `game.update_state()` payload (and `current_state` defaults) — **this game's `/game-state` only; no RFID changes**:
   - `phase`: `"countdown" | "playing" | "level_clear" | "level_fail" | "session_end"`
   - `countdown_step`: `3 | 2 | 1 | "go" | null`
   - `accepting_input`: bool (`False` during effects; `True` during gameplay)
5. **SimulatorScreen.jsx**: When `phase === "countdown"`, render 3-2-1-GO overlay from polled `countdown_step` (not local timer alone).
6. **Mute frontend synth** when backend audio active — score beeps, countdown ticks (locked #10).
7. **ws_bridge.py**: LED colors already sync via `led_display`. Optional: forward `phase` / `countdown_step` in WS JSON — not required for hoop color sync.

### In-game red blink (code-side, locked #11)

In `_build_hoops_led_display()`, penalty flash = red `(255,0,0)`, 1–2 toggles (~0.2 s period):

- Set `flashes[(i,j)]` in `try_score_cell` **red** branch (~1335) and **deduct** branch only.
- **Do not** add red blink on goal/scoring branches.
- Change display builder flash color from `[255,255,255]` to `[255,0,0]` for penalty flashes; extend duration to ~0.4–0.5 s for 1–2 visible toggles.

---

## 7. File-by-file change list

### New files

- [ ] `games/source/effects/countdown.led`
- [ ] `games/source/effects/level_clear.led`
- [ ] `games/source/effects/level_fail.led`
- [ ] `api/audio_manager.py` — `AudioManager`
- [ ] `games/audio/transition_stinger.mp3` — shared clear + fail stinger
- [ ] `games/audio/` — BGM, SFX, tick mp3s (or document extract paths)
- [ ] `scripts/build_effect_led.py` — optional one-time authoring helper
- [ ] `tests/test_effects_marathon.py` — transition sequencing tests
- [ ] `tests/test_audio_manager.py` — non-blocking smoke tests

### `api/game_manager.py`

- [ ] `EFFECTS_DIR`, `_effect_path()`, `_load_effect_file()`
- [ ] `_play_led_panel()`, `_build_effect_led_display()`, `_countdown_step_from_pass()`, `_finish_session()`
- [ ] `GameInstance.begin_level_transition()` / `finish_level_transition()` — port from Grid
- [ ] Refactor `_run_level_attempt()` to accept `play_consumer` / BGM boundaries (Grid pattern)
- [ ] Rewire nested `_run_game()` marathon loop (§3 pseudocode)
- [ ] All session-end paths via `_finish_session()` (timer, life≤10s, sequence done, stop)
- [ ] Life restart: play `level_fail.led` + countdown before reload
- [ ] Publish `phase`, `countdown_step`, `accepting_input` in `update_state()` + `current_state` defaults
- [ ] Wire `AudioManager`; score SFX in `try_score_cell()`
- [ ] Penalty flash: red 1–2× on **red/deduct only** — wire `flashes` + display builder
- [ ] Narrow `audio_play` mock to test-only; never import `GameMusic` blocking APIs headlessly

### `games/game_play/game_music.py`

- [ ] Do **not** use blocking `waitting_music_end()` in headless path
- [ ] Optional: extract path resolution helpers for `AudioManager`

### `frontend/src/screens/CountdownScreen.jsx`

- [ ] **Keep** for session-start countdown (locked #4); tune timing to ~match backend step durations

### `frontend/src/screens/SimulatorScreen.jsx`

- [ ] Phase-aware countdown overlay from `gameState.phase` / `countdown_step` (levels 2+)
- [ ] **Mute** local synth beeps when backend audio active (score + countdown ticks)

### `ws_bridge.py`

- [ ] (Optional) Forward `phase`, `countdown_step` in WS frame JSON — LED sync already via `led_display`

### `tests/test_level_preparation.py`

- [ ] Extend transition gating tests for effect panels

### Docs

- [ ] Update `docs/STATUS.md`, `docs/GAPS.md` when implemented

---

## 8. Risks / mitigations

| Risk | Mitigation |
|------|------------|
| Double countdown on level 1 (frontend + backend) | **Locked:** keep both; align step timing; mute FE ticks when backend audio on |
| `_load_level_file` skips `play_order=True` effect shelve | `_load_effect_file()` or single-shelve effect ZIPs |
| Effect `.led` wrong grid size on site | Author at native 1×6; always run `prepare_level_for_platform()`; test on HW |
| BGM stop kills stinger SFX | `stop_bgm()` uses `mixer.music.stop()` only — never `Audio.stop()` |
| BGM/stinger race on rapid restarts | `stop_bgm()` before every transition; idempotent audio service |
| `time.sleep(0.01)` in effect loop blocks thread | Acceptable (same as gameplay); audio must not add waits |
| Life=0 ≤10 s: fail vs clear panel | **Locked:** `level_clear.led` + stinger + black — no fail panel |
| Last level cleared | **Locked:** `level_clear.led` + stinger + black — no countdown |
| Double clear on sequence done | `_finish_session(..., play_clear=False)` after mid-session clear panel |
| `read_game_parameter_game_frag` stub | Not needed if standalone effect `.led` files are authoritative |
| 2P `.ledb` marathon | Effects are visual-only on shared strip; same panels for 1P/2P |
| pytest without pygame display | Mock `AudioManager` in tests |
| Red blink on scoring hoops | **Locked:** penalty/red hoops only — verify in test #7 |

Product decisions: **Locked** — see [LOCKED_DECISIONS.md](../../docs/game-effects/LOCKED_DECISIONS.md).

---

## 9. Test plan

### Simulator (default, `USE_SERIAL_HD=0`)

| # | Scenario | Expected |
|---|----------|----------|
| 1 | Start session, level 1 | UI countdown + `countdown.led` (~sync) → gameplay; `phase` transitions |
| 2 | Clear level with time left | `level_clear.led` ~2.5 s + stinger → countdown → level 2 gameplay |
| 3 | Lose all lives, >10 s left | `level_fail.led` + stinger → countdown → same level reload, score kept |
| 4 | Session timer hits 0 mid-level | Gameplay stops → `level_clear.led` → stinger → LEDs off; **no** countdown |
| 5 | Clear **last** level in sequence (time remaining) | `level_clear.led` → stinger → black; **no** countdown; `result=1` |
| 6 | Score tile | Backend positive SFX; BGM continues; FE synth muted |
| 7 | Red tile penalty | Backend negative SFX; **red** blink 1–2× on penalty hoop only (not scoring hoops) |
| 8 | Stop button mid-countdown | Input locked (`accepting_input=False`); clean stop; floor blank |
| 9 | Lose all lives with ≤10 s session time left | `level_clear.led` → stinger → black; **no** fail panel; **no** countdown; `result=0` |
| 10 | Rapid fail restart (3×) | Each cycle: fail → countdown → replay; BGM never overlaps stinger |

**Commands**

```bash
cd led-hoops
pytest tests/test_effects_marathon.py tests/test_audio_manager.py -q
# Manual: scripts/start-all-games.sh or frontend dev + api/main.py
```

### Hardware (`USE_SERIAL_HD=1`)

| # | Check |
|---|-------|
| 1 | Countdown greens match spec on physical 1×6 strip |
| 2 | Clear = all green; fail = all red; hold ~2–3 s |
| 3 | Timer expire → clear hold → all off |
| 4 | BGM audible only during gameplay; silent during countdown/transitions |
| 5 | Shared stinger audible on clear/fail; no hang on game thread |
| 6 | Session stop / logout blanks floor (`_hw_blank_floor`) |

```bash
USE_SERIAL_HD=1 python -m pytest tests/test_hardware_boot.py -q
# Full smoke: scripts/hw_mode_smoke_test.py (if present) with effects scenarios
```

### State sync

- Poll `/game-state/{id}` during countdown: `countdown_step` decrements 3→2→1→go in sync with `led_display`.
- Simulator iframe shows matching hoop colors via `ws_bridge` `led_display` (no phase field required).
- React HUD overlay reads `phase` / `countdown_step` / `accepting_input` from same poll endpoint.

---

## 10. Implementation order

1. Author three effect `.led` files + loader smoke test
2. `_play_led_panel()` + marathon loop wiring (silent)
3. `AudioManager` + shared `transition_stinger.mp3` + BGM boundaries
4. State fields (`phase`, `accepting_input`, `countdown_step`) + SimulatorScreen overlay
5. Red blink (penalty only) + backend score SFX; mute FE synth
6. Tune level-1 UI + backend countdown ~sync
7. HW validation + pytest coverage

---

*Plan only — no runtime code changes in this commit.*

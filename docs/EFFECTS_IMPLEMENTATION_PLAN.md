# LED Hoops — Effects Implementation Plan

Implementation plan for **transition `.led` panels**, **marathon-loop wiring**, and **non-blocking audio**.

**Locked product decisions:** [docs/game-effects/LOCKED_DECISIONS.md](../../docs/game-effects/LOCKED_DECISIONS.md) — all open questions resolved there; this plan implements those locks.

**Testing / TDD (locked #13, mandatory):** [docs/game-effects/TESTING_CONTRACT.md](../../docs/game-effects/TESTING_CONTRACT.md) — red→green→refactor via API; prove `phase` / `accepting_input` inside the marathon loop; Layer B smoke with FE + sim. No merge without green `tests/test_effects_session_loop.py`.

Specs:
- Global: [activerse_final_changes/docs/game-effects/GLOBAL_RULES.md](../../docs/game-effects/GLOBAL_RULES.md)
- Hoops: [EFFECTS_SPEC.md](./EFFECTS_SPEC.md)

---

## Gap analysis (2026-08-07)

**Verdict:** **Ready for implement** — plan aligns with [LOCKED_DECISIONS.md](../../docs/game-effects/LOCKED_DECISIONS.md); code-audit gaps below are documented with concrete fixes. No product blockers remain.

| ID | Severity | Finding | Resolution |
|----|----------|---------|------------|
| G1 | blocker | Marathon loop timeout at **top** of `for lvl_path` (~L1923–1927) sets `_session_over` and `break`s with **no** `level_clear.led` hold before `_hw_blank_floor`. | **Applied** — §3 `_finish_session()` called on timeout, life≤10 s, sequence done, external stop. |
| G2 | blocker | `AudioManager.stop_bgm()` must **not** call `audio.Audio().stop()` — stops all mixer channels and cuts stingers. | **Applied** — §5 uses `mixer.music.stop()` + `unload()` only. |
| G3 | major | `_restart_level` set True in `_frame_callback` (~L1726) but **never cleared** in restart loop (~L1957–1963) → infinite replay. | **Applied** — §3 pseudocode clears flag after fail panel; test #12; checklist item added. |
| G4 | major | `_consume_cell()` (~L1418) sets white `flashes` on **goal** scoring — violates locked #11 (penalty hoops only). | **Applied** — §6: remove goal flash; red blink only in `try_score_cell` red + deduct branches. |
| G5 | major | Red branch in `try_score_cell()` (~L1335–1344) never sets `flashes`; display builder white-only (~L942–953). | **Applied** — §6 + checklist: wire red `(255,0,0)` 1–2× toggle in penalty paths only. |
| G6 | major | Hoops `GameInstance` lacks `begin_level_transition()` / `finish_level_transition()` (Grid has them ~L1123–1191). | **Applied** — §3 port Grid methods; reuse existing `_set_input_acceptance()` (~L496) inside them. |
| G7 | major | Test plan previously implied countdown after last level clear. | **Applied** — test #5: sequence exhausted → clear → stinger → black, **no countdown**. |
| G8 | minor | `current_state` (~L1201) has no `phase` / `countdown_step` / `accepting_input` keys yet. | **Applied** — §6 defaults + checklist. |
| G9 | minor | `.led` authoring steps lacked concrete model/bootstrap path. | **Applied** — §4 expanded with `NormalLed` / shelve steps and validation commands. |
| G10 | minor | Test plan missing goal-no-flash, deduct penalty blink, restart-flag regression. | **Applied** — tests #11–12 in §9. |
| G11 | minor | [EFFECTS_SPEC.md](./EFFECTS_SPEC.md) L73 says “perfect hoop press” blinks — contradicts locked #11. | **Open** — update spec in a separate doc pass (plan follows locks). |
| G12 | minor | `games/game_play/game_music.py` and mp3 bundles may be absent in partial checkouts. | **Open** — extract paths from onsite `games/` bundle at deploy time; locked filenames in §5. |

### Refinements applied to plan body (this pass)

- Replaced “Plan review” with this gap table; verdict set to **Ready for implement**.
- §3: `_restart_level = False` after fail→countdown restart; `_finish_session` reason mapping uses `_end_reason` / `game_over_reason`.
- §4: concrete `.led` bootstrap steps (`NormalLed`, `Setting.FLOOR_LIGHT`, shelve ZIP, sim validation).
- §5: locked audio paths only — **one** `games/audio/transition_stinger.mp3` (no `stinger_clear` / `stinger_fail` split).
- §6: **remove** goal white flash from `_consume_cell`; penalty-only red blink; `current_state` defaults for sync fields.
- §7 checklist: restart-flag fix, goal-flash removal, `phase` defaults, reuse Grid transition gating.
- §9: tests #11 (goal press → no flash), #12 (`_restart_level` cleared after fail cycle).

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
| Life restart | `_frame_callback` life≤0 branch (~1721–1727); restart loop (~1957–1963) | Refills HP when >10 s session time left; **no fail panel**; **`_restart_level` never cleared** (bug — see G3) |
| Level clear detection | Board time exceeded (~1741–1743); all scoreables done (~1814–1821) | Sets `_level_cleared`; **no clear panel** |
| Timer session end | `session_elapsed > game_time_sec` (~1733–1737, ~1924–1927) | Sets `_session_over`, `result=2`; **no clear panel before blank** |
| In-game flash | `game.flashes` + `_build_hoops_led_display()` (~942–953) | White 0.4 s blink on **goal** consume (~L1418) — **remove** per locked #11; penalty red blink not wired |
| Audio primitives | `games/audio_play/audio.py` | `play()` (SFX channel), `play_bmg()` (mixer.music), non-blocking channels |
| Audio thread | `games/util/audio_play_thread.py` | Dedicated thread for long clips |
| Original fragment model | `games/gui/gui_editor_game2.py` (~903–915) | After gameplay: load `game.clap_light` / `game.game_accomplished` sub-shelve, `running(dict_group_end, True)` |
| Original music map | `games/game_play/game_music.py` | Maps `count_down`, `bmg_video`, `clap_light`, `game_accomplished`, score/blood mp3s; **`waitting_music_end()` blocks** |
| Frontend pre-session countdown | `frontend/src/screens/CountdownScreen.jsx` | 3-2-1-GO with Web Audio synth; **once per session, before `start-game`** — **keep** (locked #4) |
| Frontend gameplay HUD | `frontend/src/screens/SimulatorScreen.jsx` | Polls `/game-state`; synth score/hurt beeps; **no phase/countdown overlay** |
| Input gating helper | `_set_input_acceptance()` (~496), `accepting_input` on `GameInstance` (~1142) | Reuse inside ported `begin_level_transition()` / `finish_level_transition()` |
| Transition gating (reference) | `led-grid/api/game_manager.py` — `begin_level_transition()` / `finish_level_transition()` (~L1123–1191); `transition_consumer` in `_run_level_attempt()` (~L562) | **Port to Hoops** `GameInstance`; do not invent parallel gating |

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
| Red 1–2× blink on penalty press only | `try_score_cell` red branch (~1335–1344) sets no `flashes`; `_consume_cell` white flash on goals (~1418) | Remove goal flash; wire red blink in red + deduct branches only |
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
    game.begin_level_transition()  # GameInstance method — port from Grid ~L1123
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
                reason=game._end_reason or game.get_state().get("game_over_reason") or "timeout",
            )
            break

        if game._restart_level:
            _play_led_panel(game, play, led_table, EFFECT_FAIL,
                            phase="level_fail", settings=_s,
                            audio_mgr=audio_mgr, stinger=audio_mgr.transition_stinger)
            game.life = game.max_life
            game._cell_red_penalty_at.clear()
            game.last_life_loss_time = 0.0
            game._restart_level = False  # G3: must clear or inner while loops forever
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

1. **Programmatic bootstrap (recommended)** — `scripts/build_effect_led.py` (create at implement time):
   - Import `NormalLed` (or equivalent floor group class) and `Setting.FLOOR_LIGHT` from the deployed `games/model/` tree.
   - Build timed groups per tables below; set `game_obj.play_order = True`, `zone_*` to native 1×6.
   - Write shelve + ZIP to `games/source/effects/{name}.led` (single shelve per ZIP).
   - Validate: `_load_effect_file()` → `prepare_level_for_platform()` → sim frame at t=0,1,2 s.
2. **Original LED editor** (if available on-site) — export mini-board with timed `normal_led` groups; ensure `play_order=True`.
3. **Clone + edit** — copy a minimal static `.led` from `games/source/*/` (e.g. tier `14.led`), retime colors in editor.

**Minimum bootstrap command (after script exists):**

```bash
cd led-hoops
python scripts/build_effect_led.py --effect countdown --out games/source/effects/countdown.led
python scripts/build_effect_led.py --effect level_clear --out games/source/effects/level_clear.led
python scripts/build_effect_led.py --effect level_fail --out games/source/effects/level_fail.led
```

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

Extract mp3s from the onsite `games/` bundle (`games/source/*/*/audio/` subfolders, or paths in `games/game_play/game_music.py` when present). Locked canonical names below — do **not** split clear/fail stingers.

| Asset | Path |
|-------|------|
| BGM | `games/audio/bgm_thank_you_not_so_bad.mp3` |
| Positive SFX | `games/audio/score_positive.mp3` (shared cross-game) |
| Negative SFX | `games/audio/score_negative.mp3` |
| Countdown tick | `games/audio/countdown_tick.mp3` |
| **Transition stinger** | **`games/audio/transition_stinger.mp3`** — clear **and** fail (locked #5) |

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
   - `phase`: `"countdown" | "playing" | "level_clear" | "level_fail" | "session_end"` (default `"playing"` before marathon starts)
   - `countdown_step`: `3 | 2 | 1 | "go" | null` (default `null`)
   - `accepting_input`: bool (default `False` until first gameplay frame; mirror existing `GameInstance.accepting_input` ~L1142)
5. **SimulatorScreen.jsx**: When `phase === "countdown"`, render 3-2-1-GO overlay from polled `countdown_step` (not local timer alone).
6. **Mute frontend synth** when backend audio active — score beeps, countdown ticks (locked #10).
7. **ws_bridge.py**: LED colors already sync via `led_display`. Optional: forward `phase` / `countdown_step` in WS JSON — not required for hoop color sync.

### In-game red blink (code-side, locked #11)

In `_build_hoops_led_display()`, penalty flash = red `(255,0,0)`, 1–2 toggles (~0.2 s period):

- Set `flashes[(i,j)]` in `try_score_cell` **red** branch (~1335) and **deduct** branch (~1345) only.
- **Remove** `self.flashes[(i,j)] = time.time()` from `_consume_cell()` (~1418) — goal/scoring presses must **not** flash (locked #11 overrides EFFECTS_SPEC L73 “perfect hoop press”).
- **Do not** add blink on goal/p1/p2 scoring branches.
- Change display builder: penalty flashes use `[255,0,0]` / `[0,0,0]` toggle; extend duration to ~0.4–0.5 s for 1–2 visible toggles.

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
- [ ] `tests/test_effects_session_loop.py` — **TDD gate** — T1–T8 + T10 via API (see §9)
- [ ] `tests/fixtures/effects/` — tiny `.led` fixtures for fast marathon tests (optional env override)
- [ ] `tests/test_audio_manager.py` — non-blocking smoke tests (T9)

### `api/game_manager.py`

- [ ] `EFFECTS_DIR`, `_effect_path()`, `_load_effect_file()`
- [ ] `_play_led_panel()`, `_build_effect_led_display()`, `_countdown_step_from_pass()`, `_finish_session()`
- [ ] `GameInstance.begin_level_transition()` / `finish_level_transition()` — port from Grid ~L1123; call `_set_input_acceptance()` inside
- [ ] Refactor `_run_level_attempt()` to accept `play_consumer` / BGM boundaries (Grid pattern ~L562)
- [ ] Rewire nested `_run_game()` marathon loop (§3 pseudocode)
- [ ] All session-end paths via `_finish_session()` (timer at loop top ~L1923, life≤10s, sequence done, stop)
- [ ] Life restart: play `level_fail.led` + countdown before reload; **`game._restart_level = False`** after fail cycle (G3)
- [ ] Publish `phase`, `countdown_step`, `accepting_input` in `update_state()` + `current_state` defaults (§6)
- [ ] Wire `AudioManager`; score SFX in `try_score_cell()`
- [ ] Penalty flash: red 1–2× on **red/deduct only**; **remove** goal white flash from `_consume_cell()` (~L1418)
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
| Red blink on scoring hoops | **Locked:** penalty/red hoops only — verify in tests #7, #11 |
| `_restart_level` sticky flag | Clear after fail panel (G3); test #12 |

Product decisions: **Locked** — see [LOCKED_DECISIONS.md](../../docs/game-effects/LOCKED_DECISIONS.md).

---

## 9. TDD / verification (locked #13)

**Contract:** [docs/game-effects/TESTING_CONTRACT.md](../../docs/game-effects/TESTING_CONTRACT.md) — mandatory for merge. Effects work is **not done** until automated tests prove behavior runs **inside the marathon loop**, exercised through the **API**, and spot-checked with **frontend + simulator**.

### Required test module

`tests/test_effects_session_loop.py` — one dedicated module covering **T1–T8 + T10** from [TESTING_CONTRACT.md §2](../../docs/game-effects/TESTING_CONTRACT.md#2-what-must-be-proven). T9 lives in `tests/test_audio_manager.py`.

| Contract ID | Scenario | Assert via API (`GET /game-state`) |
|-------------|----------|-------------------------------------|
| **T1** | Session start | After `POST /start-game`, poll until `phase=countdown` (or brief transition) then `phase=playing` with `accepting_input=true` |
| **T2** | Countdown every level | Mid-session clear → next level: `phase` goes `level_clear` → `countdown` → `playing` (not straight into gameplay) |
| **T3** | Level fail restart | Force life=0 with **>10 s** left → `phase=level_fail` → `countdown` → `playing` on **same** level; score preserved |
| **T4** | Session end (timer) | Timer expire → `phase=level_clear` or `session_end` → floor blank; **no** subsequent `countdown` |
| **T5** | Session end (life ≤10 s) | Life=0 with **≤10 s** left → clear path (not fail panel) → black; no countdown |
| **T6** | Last level cleared | Clear final level → session end (clear → black); no countdown |
| **T7** | Input gating | While `accepting_input=false` (countdown / clear / fail), `POST /game-input` does **not** change score / life |
| **T8** | Playing accepts input | During `phase=playing`, valid press **does** affect score or life — proves effects did not break gameplay |
| **T10** | Hoops red blink | Red penalty press sets blink/flash; good/goal press does **not** use red-blink path |

**How to run (Layer A — required, CI-friendly):**

- Start FastAPI in-process (`TestClient` / `httpx.ASGITransport`) **or** spawn uvicorn on a free port.
- Sim mode (`USE_SERIAL_HD=0` or unset).
- Drive `POST /start-game`, poll `GET /game-state` for `phase`, `accepting_input`, `life`, `score`, `current_level`; send `POST /game-input` during gated vs playing phases.
- Use short effect `.led` fixtures under `tests/fixtures/effects/` (tiny `board_time`) or env override so tests finish in seconds.
- **Prove fail / clear / countdown happen inside the marathon loop** — not via isolated mocks of `Play.running` alone.

```bash
cd led-hoops
pytest tests/test_effects_session_loop.py -q   # merge gate
pytest tests/test_audio_manager.py -q          # T9 optional bar
```

### Layer B — API + ws_bridge + simulator (required smoke)

Manual or scripted smoke before merge:

1. Start API + `ws_bridge` + frontend (`scripts/start-dev.sh` or equivalent).
2. Guest login → start session.
3. Watch sim / floor iframe:
   - Countdown pattern on floor before play
   - Gameplay LEDs + scoring works
   - Trigger fail (lose life, >10 s left) → fail panel → countdown → same level
   - Or clear / short timer → clear panel → next countdown or session black
4. Confirm UI countdown and floor stay roughly in sync; UI shows playing when `phase=playing`.

```bash
# From repo root or led-hoops — adjust to local start script
./scripts/start-all-games.sh
# Optional: extend scripts/hw_mode_smoke_test.py / full_hw_sim_smoke.py with phase checks
```

### Layer C — Frontend checklist

- [ ] `SimulatorScreen`: scoring clicks ignored/disabled when backend `phase` is `countdown` / `level_clear` / `level_fail`
- [ ] Synth score/hurt beeps **muted** when backend `AudioManager` active (locked #10)
- [ ] No crash when `phase` / `countdown_step` / `accepting_input` appear on `/game-state`

Automated FE tests are nice-to-have; **Layer A + B** are the merge gate.

### Red→green task order (TESTING_CONTRACT §4)

Follow this order — **write failing tests before wiring each marathon hook**:

1. [ ] **Red:** Add failing tests for **T1 + T7 + T8** (countdown → playing + input gate + gameplay still scores)
2. [ ] **Green:** Implement effect runner + marathon hooks until T1/T7/T8 pass
3. [ ] **Red:** Add failing tests for **T2, T3** (clear / fail loops inside marathon)
4. [ ] **Green:** Implement clear/fail panels + countdown-between-levels
5. [ ] **Red:** Add failing tests for **T4, T5, T6** (session end paths)
6. [ ] **Green:** Implement `_finish_session` / session-end paths
7. [ ] **Red:** Add failing test for **T10** (Hoops red blink; goal no flash)
8. [ ] **Green:** Wire penalty-only red blink; remove goal white flash
9. [ ] Run **Layer B** smoke; fix until sim shows panels inside the real loop
10. [ ] Note smoke date/result in commit message or plan

**Do not** land marathon wiring without tests that would fail on the pre-effects codebase.

### Pre-marathon wiring checklist (write tests FIRST)

- [ ] Create `tests/test_effects_session_loop.py` skeleton + pytest fixtures (`TestClient`, short session config)
- [ ] **Red:** T1 — session start reaches `phase=playing` with `accepting_input=true`
- [ ] **Red:** T7 — input blocked during `phase=countdown` / `level_clear` / `level_fail`
- [ ] **Red:** T8 — valid input works during `phase=playing`
- [ ] Confirm all three fail on current codebase → **then** begin §3 marathon wiring

### Additional regression tests (same module or helpers)

| # | Scenario | Expected |
|---|----------|----------|
| 11 | Goal / scoring press | **No** hoop flash; backend positive SFX only (T10 overlap) |
| 12 | Life restart flag | After fail→countdown cycle, `_restart_level` is **False** before next gameplay (G3) |
| 13 | Stop mid-countdown | Input locked; clean stop; floor blank |
| 14 | Rapid fail restart (3×) | Each cycle: fail → countdown → replay; BGM never overlaps stinger |

### Hardware (`USE_SERIAL_HD=1`) — post-merge validation

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
```

### Definition of done

- [ ] `tests/test_effects_session_loop.py` covers T1–T8 + T10; pytest green in sim mode
- [ ] Layer B smoke documented and run once
- [ ] `/game-state` exposes `phase` + `accepting_input` during live session
- [ ] Gameplay still scores/loses life during `playing` (T8 regression)

---

## 10. Implementation order (TDD-first)

1. **Red:** Create `tests/test_effects_session_loop.py` with failing T1 + T7 + T8 (see §9 pre-marathon checklist)
2. Author three effect `.led` files + loader smoke test (short fixtures for tests)
3. **Green:** `_play_led_panel()` + marathon loop wiring until T1/T7/T8 pass
4. **Red:** Failing T2 + T3 → **Green:** clear/fail panels + countdown-between-levels
5. **Red:** Failing T4 + T5 + T6 → **Green:** `_finish_session` / session-end paths
6. `AudioManager` + shared `transition_stinger.mp3` + BGM boundaries (T9 in `test_audio_manager.py`)
7. State fields (`phase`, `accepting_input`, `countdown_step`) + SimulatorScreen overlay
8. **Red:** Failing T10 → **Green:** red blink (penalty only) + backend score SFX; mute FE synth
9. **Layer B** smoke — API + ws_bridge + FE/sim; fix until panels visible in real loop
10. Tune level-1 UI + backend countdown ~sync
11. HW validation

---

*Plan only — no runtime code changes in this commit.*

---

## Implementation status (2026-08-07)

- [x] `tests/test_effects_session_loop.py` — T1–T8 + T10 green (sim mode)
- [x] `tests/test_audio_manager.py` — T9 non-blocking smoke
- [x] `api/audio_manager.py`, marathon effect runner, `phase` / `accepting_input`
- [x] Production `.led` under `games/source/effects/` (`scripts/build_effect_led.py`)
- [x] Audio placeholders under `games/audio/` (see `games/audio/README.md`)
- [x] Frontend: `SimulatorScreen` phase overlay + synth mute when `backend_audio`

### Layer B smoke (manual)

```bash
cd led-hoops
./scripts/start-dev.sh
# Guest login → pick level → watch sim iframe:
#   countdown greens → gameplay → fail/clear panels between levels
# Confirm UI countdown overlay tracks backend countdown_step on levels 2+

# Optional phase check via API while session runs:
curl -s localhost:8000/game-state | python3 -m json.tool | rg phase
```

**Smoke note:** Layer A pytest green on 2026-08-07; Layer B not run in this agent session (requires interactive sim).

# TODO — Blank the physical floor on game end/stop

> **Status: NOT IMPLEMENTED — needs validation on real hardware.**
> Found by code review only; no local floor to test against. Implement and
> verify during the next on-site hardware session.

---

## Problem

Observed on real hardware: when a game ends via timeout (or presumably
Stop Game), the simulator UI correctly shows the scoreboard and goes
blank, but the **physical LED floor stays lit with whatever pattern was
drawn on the last frame before the game ended** — it never turns off.

## Root cause

The hardware draw call only happens *inside* the active per-level frame
loop, in `_frame_callback` (`api/game_manager.py`, HARDWARE I/O block,
currently ~L1447-1468):

```python
if USE_SERIAL_HD and _hw_led_control is not None and \
        _now - getattr(game, "_hw_last_draw", 0) >= _HW_DRAW_INTERVAL:
    with _hw_serial_lock:
        ...
        _hw_led_control.draw_screen_by_com(_hw_layout_type, _ld2)
```

The moment the callback returns `False` (level cleared, or session ends on
timeout / life-exhausted / sequence-exhausted), this loop stops running.
**Nothing after that point ever writes to the floor again.** The last
frame drawn stays lit on the physical hardware indefinitely — until some
later game's first frame happens to overwrite it.

Checked all 3 places a game/session can end — none of them send a
hardware clear:

1. **Session-end** inside `_run_game`, after the marathon loop exits
   (`api/game_manager.py` ~L1587-1591):
   ```python
   game.update_state(game_over=True, time_left=0,
                      game_over_reason=final_reason, result=final_result,
                      levels_cleared=game.levels_cleared,
                      final_score=final_score, final_score2=final_score2)
   game.running = False
   ```
   `update_state` only updates the simulator-facing state dict — no HW call.

2. **`stop_game()`** (~L1608-1616), user-initiated Stop Game:
   ```python
   def stop_game(self, game_id: str) -> dict:
       game = self.get_game(game_id)
       if not game:
           return {"success": False, "error": f"Game not found: {game_id}"}
       game.running = False
       if game.thread:
           game.thread.join(timeout=5)
       ...
   ```
   No HW call either.

3. **`clear_all()`** (~L1020-1032), called at the start of every new game to
   stop any prior game:
   ```python
   def clear_all(self):
       with self.lock:
           for gid, g in list(self.games.items()):
               g.running = False
           threads = [(gid, g.thread) for gid, g in self.games.items() if getattr(g, "thread", None)]
           self.games.clear()
       for gid, t in threads:
           t.join(timeout=3.0)
           ...
   ```
   Also no HW call — so even starting a *new* game doesn't explicitly
   blank the floor first; it just starts drawing its own frames over
   whatever is stuck.

This matches the observed symptom exactly: the simulator reacts correctly
to `game_over` (frontend state), but the physical floor has no equivalent
signal — it simply stops receiving writes.

## Proposed solution

Add one hardware "blank frame" write at each of the 3 exit points above,
reusing the exact same call already used in the per-frame HW block
(`_hw_led_control.draw_screen_by_com(_hw_layout_type, grid)`), but with an
all-`[0, 0, 0]` grid sized `led_table.led_row × led_table.led_col`, guarded
the same way as the existing draw call (`USE_SERIAL_HD and _hw_led_control
is not None`, inside `_hw_serial_lock`).

Sketch (not yet applied):

```python
def _hw_blank_floor(led_table):
    """Send one all-black frame to the physical floor. Call on every game
    end/stop path so hardware doesn't stay stuck on the last drawn pattern."""
    if not (USE_SERIAL_HD and _hw_led_control is not None):
        return
    try:
        rows, cols = led_table.led_row, led_table.led_col
        blank = [[0, 0, 0] for _ in range(cols)]
        with _hw_serial_lock:
            _hw_led_control.draw_screen_by_com(_hw_layout_type, [blank[:] for _ in range(rows)])
    except Exception as e:
        logger.warning(f"HW blank failed: {e}")
```

Call sites:

1. **Session-end** — call `_hw_blank_floor(led_table)` right after the
   `game.update_state(game_over=True, ...)` call (~L1590), before
   `game.running = False`.
2. **`stop_game()`** — needs access to that game's `led_table` (stored on
   the `GameInstance`, e.g. `game.led_table` — already exposed per
   `game.led_table = led_table` set earlier in `_run_game`). Call
   `_hw_blank_floor(game.led_table)` before/after `game.running = False`.
3. **`clear_all()`** — for each game being cleared, call
   `_hw_blank_floor(g.led_table)` (guard for `None` — a game that never
   got past setup won't have one) before joining its thread.

## Why this isn't implemented yet

This is exactly the class of change that looks correct in code review but
needs a real floor to confirm: whether `draw_screen_by_com` reliably
blanks all channels when called once right as the game thread is winding
down (possible race with the thread's own last in-flight write), whether
the COM ports are still open/valid at each of these 3 call sites, and
whether the blank needs to be sent more than once (some panels have shown
single-write drops in prior on-site testing per
`docs/HARDWARE_LED_RESEARCH.md`).

## Validation checklist (next on-site session)

- [ ] Play a level to timeout (no Stop Game) → confirm floor goes fully
      dark within ~1s of the simulator showing the scoreboard.
- [ ] Play a level to life=0 with <10s left (real game-over, not restart)
      → confirm floor blanks.
- [ ] Manually click Stop Game mid-level → confirm floor blanks.
- [ ] Start a new game while a stale pattern is showing (skip the blank
      steps above to reproduce the stuck state first) → confirm
      `clear_all()`'s blank fires before the new game's first real frame.
- [ ] Confirm no regression: floor still draws normally during active
      gameplay (throttle/lock unaffected).

## Scope

This bug and fix pattern likely applies to all 5 games (same
`game_manager.py` structure — session-end, `stop_game()`, `clear_all()` —
copied across led-hoops/laser/climb/grid/hexagon). Only hoops is
documented here per current focus; repeat this investigation for the
other 4 when their gameplay-mechanics pass comes up.

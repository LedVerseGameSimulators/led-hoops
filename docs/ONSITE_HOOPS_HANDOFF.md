# Onsite Hoops — Work Handoff (pull & start here)

**Date:** 2026-09-09  
**Repo:** `led-hoops` (`main`)  
**Pull:** `git pull origin main` then read this file.

---

## Docs in this repo

| Doc | What to fix |
|-----|-------------|
| **This file** | Order of work + links |
| [PLAN_HOOPS_MAX_10_WAVES.md](./PLAN_HOOPS_MAX_10_WAVES.md) | Product rule: most levels ≤**10** scoreable waves. **Challenge 85 Hoops** levels stay long. Inspect each file before trim; drop excess waves — **don’t** re-time durations. |
| [ONSITE_HOOPS_SP_LEVEL_SWEEP.md](./ONSITE_HOOPS_SP_LEVEL_SWEEP.md) | Wave counts / board vs session for SP + 2P. |
| [ONSITE_LONG_LEVELS_HEX_HOOPS.md](./ONSITE_LONG_LEVELS_HEX_HOOPS.md) | Hex vs Hoops: when “won’t finish” is content length vs code. |

---

## Suggested order

1. **Content trim** — levels over 10 waves per [PLAN_HOOPS_MAX_10_WAVES.md](./PLAN_HOOPS_MAX_10_WAVES.md)
   - **Exempt:** `Challenge - 85 Hoops`, `Challenge -- 85 Hoops` (long by design)
   - Per file: list scoreable waves → drop excess → keep authored `start`/`end` times
   - Fix `--/16` orphan wave at t≈1214s separately (P0 data bug)
2. **Smoke** — a short SP level + one trimmed mid-tier after edit; Challenge left untouched
3. Effects / Grid parity only if onsite still reports missing countdown/clear (separate from wave trim)

---

## Grid / other repos (reference only)

Wave trim is **Hoops content** — Grid code is not required for the ≤10-wave work. Links if needed for shared patterns (effects, session loop):

| What | Link |
|------|------|
| **This Hoops repo** | https://github.com/LedVerseGameSimulators/led-hoops |
| **Grid repo** (effects reference if needed) | https://github.com/LedVerseGameSimulators/led-grid |
| **Grid effects runner** | https://github.com/LedVerseGameSimulators/led-grid/blob/main/api/effects_runner.py |
| **Hex long-level / effects context** | https://github.com/LedVerseGameSimulators/led-hexagon |

---

## Key local files

- Level archives: `games/source/-/`, `games/source/--/`, `games/source/---/`
- Wave / clear logic: `api/game_manager.py` (consume, wave skip, board_time)
- Plan rule of thumb: max **10** waves for normal levels; Challenge marathons exempt

# Onsite SP Level Sweep — LED Hoops

> **Generated:** 2026-09-09  
> **Scope:** Single-player levels under `games/source/-` (casual) and `games/source/--` (level).  
> **Out of scope (noted):** `games/source/---` (2P `.ledb`), `games/source/1casual game/` / `2level game/` / `3advanced game/` (duplicate copies of the same archives), `games/source_group/` (not present in this tree).

---

## Method

### How levels are loaded

Same pipeline as `api/game_manager._load_level_file()` and the Hex sweep (`led-hexagon/docs/ONSITE_HEX_SP_LEVEL_SWEEP.md`):

1. Open `.led` / `.ledb` as a **zip** archive.
2. Extract to a temp directory.
3. Walk for `game_file.dat` (main gameplay shelve has `play_order=False`).
4. **`shelve.open("game_file")`** with `games/` on `sys.path` → read `dict_group` and `para_key_game`.

Analysis: offline Python sweep over all 35 progression levels (25 SP + 10 2P). Classification mirrors `api/game_manager.py` frame logic.

| Field | Source |
|-------|--------|
| `board_time_sec` | `max(group.end_time_sec)` across all groups |
| Scoreable wave | `floor_light` group whose main ring color ∈ `_HOOPS_COLOR_ARR` (1P) or blue/orange (2P) |
| Wave count | Distinct `start_time_sec` values among scoreable floor groups |
| Wave cadence | Delta between consecutive scoreable `start_time_sec` |
| Moving red | `floor_light`, red `(254,0,0)` / `(240,0,0)`, `speed != 0` |

### Session timer defaults

From `api/game_manager.py` → `load_real_settings()` / `_SETTINGS_DEFAULTS`:

| Setting | Default | Source |
|---------|--------:|--------|
| `game_time_sec` | **300** | `game_time_sw` × 60 (default 5 min) |
| `life_value` | 20 | `life_value_sw` |
| `blue_hide_max_time` | 20 s | covered scoreables vanish (disappear mode) |
| `WAVE_SKIP_DELAY_SEC` | 1.0 | pause before auto-jump to next wave |

`api/config.py` also defines `GAME_TIMEOUT_SECONDS = 600` (API process guard); **player-facing session is 300 s**.

Level ends when: all scoreable waves cleared (wave-skip advances `total_pass`) **or** `total_pass > board_time_sec`. Session ends when `session_elapsed > game_time_sec` (300 s) regardless of level progress.

---

## Summary

| Metric | SP (`-` + `--`) | 2P (`---`) | Notes |
|--------|----------------:|-----------:|-------|
| **Total levels scanned** | 25 | 10 | Progression tiers per `_TIERS_1P` / `_TIERS_2P` |
| **board_time > 300 s** | **16 / 25 (64%)** | **5 / 10 (50%)** | Session cap always wins first |
| **board_time = 600 s** | 5 / 25 | 5 / 10 | Same pattern as Hex |
| **Waves ≥ 50** | 5 / 25 | 3 / 10 | Hoops micro-waves (often ~2 s apart) |
| **Waves ≥ 70** | 3 / 25 | 1 / 10 | 007/008 = 106 waves each |
| **Last wave start > 300 s** | **1 / 25** | 0 / 10 | `--/16` only — data bug |
| **Est. clear > 300 s (@ 3 s/wave)** | **2 / 25** | — | 007, 008 borderline |
| **Max cadence gap ≥ 10 s** | 2 / 25 | 0 / 10 | `--/16` (1018 s!), `--/24` (11 s) |

**Key difference from Hex:** Hex SP levels use **goal-indicator windows** (tens of phases); Hoops uses **scoreable floor groups** with much higher wave counts (20–106 per level, often 2–6 s spacing). A “long level” in Hoops is usually **too many micro-waves**, not a 600 s board alone.

---

## Worst offenders (top 10 by wave count)

| Rank | Level | Tier | Waves | board_time | Last wave @ | Scoreable cells | Risk |
|-----:|-------|------|------:|-----------:|------------:|----------------:|------|
| 1 | **007** | `-` | **106** | 220 s | 214 s | 110 | Barely completable @ ~3 s/shot |
| 2 | **008** | `-` | **106** | 226 s | 220 s | 110 | Same as 007 |
| 3 | **011** | `-` | 70 | 252 s | 246 s | 70 | Long; tight vs 300 s session |
| 4 | **001** | `-` | 52 | 260 s | 255 s | 130 | Last wave very late |
| 5 | **Challenge - 85 Hoops** | `-` | 52 | 594 s | 281 s | 130 | Long board + late last wave |
| 6 | **Challenge -- 85 Hoops** | `-` | 48 | 600 s | 235 s | 120 | board = session × 2 |
| 7 | **015** | `--` | 46 | 596 s | 225 s | 230 | Many cells + long board |
| 8 | **009** | `-` | 44 | 595 s | 215 s | 179 | 295 total groups |
| 9 | **004** | `-` | 43 | 595 s | 210 s | 112 | |
| 10 | **005** | `-` | 43 | 594 s | 252 s | 105 | Late last wave |

### Critical outlier — `--/16`

- Wave starts every **6.5 s** from t=0 through t=195 s (31 waves).
- **Final wave at t=1213.5 s** — **1018.5 s dead gap** from previous wave.
- **Uncompletable** in any 300 s session: wave-skip can never reach the last scoreable group.
- **Fix:** content edit — move last wave to ~200 s or remove orphan group (not a code change).

---

## Full SP per-level matrix

| Level | board_t | Waves | Last wave @ | Cells | Groups | Moving red | Flags |
|-------|--------:|------:|------------:|------:|-------:|-----------:|-------|
| 001 | 260 | 52 | 255 | 130 | 52 | 0 | late |
| 002 | 600 | 36 | 192 | 180 | 37 | 1 | E |
| 003 | 600 | 36 | 210 | 109 | 172 | 0 | E |
| 004 | 595 | 43 | 210 | 112 | 162 | 0 | E |
| 005 | 594 | 43 | 252 | 105 | 141 | 0 | E, late |
| 006 | 217 | 37 | 212 | 173 | 37 | 0 | |
| 007 | 220 | **106** | 214 | 110 | 110 | 0 | **W106** |
| 008 | 226 | **106** | 220 | 110 | 110 | 0 | **W106** |
| 009 | 595 | 44 | 215 | 179 | 295 | 0 | E |
| 010 | 595 | 41 | 200 | 123 | 361 | 0 | E |
| 011 | 252 | 70 | 246 | 70 | 70 | 0 | W70, late |
| Challenge - 85 Hoops | 594 | 52 | 281 | 130 | 161 | 0 | E, late |
| Challenge -- 85 Hoops | 600 | 48 | 235 | 120 | 168 | 0 | E |
| 14 | 595 | 41 | 200 | 123 | 242 | 0 | E |
| 15 | 596 | 46 | 225 | 230 | 165 | 0 | E |
| **16** | 598 | 32 | **1214** | 155 | 247 | 0 | **BUG** |
| 17 | 600 | 31 | 178 | 156 | 185 | 30 | E, mred |
| 18 | 186 | 31 | 180 | 157 | 155 | 0 | |
| 19 | 594 | 32 | 186 | 128 | 227 | 0 | E |
| 20 | 198 | 33 | 192 | 156 | 163 | 0 | |
| 21 | 600 | 34 | 198 | 170 | 200 | 30 | E, mred |
| 22 | 590 | 36 | 210 | 180 | 210 | 0 | E |
| 23 | 216 | 36 | 210 | 150 | 36 | 0 | |
| 24 | 214 | 20 | 204 | 100 | 100 | 0 | cad 11 s |
| 25 | 590 | 36 | 210 | 180 | 236 | 0 | E |

E = `board_time > 300 s`. **BUG** = last scoreable wave unreachable within session.

---

## 2P (DK) snapshot

| Level | Waves | board_time | Last wave @ | Cells | board ≥ 590 |
|-------|------:|-----------:|------------:|------:|:-----------:|
| DK05 | 72 | 600 | 246 | 144 | ✓ |
| DK07 | 72 | 600 | 213 | 144 | ✓ |
| DK02 | 68 | 239 | 233 | 136 | |
| DK10 | 64 | 596 | 189 | 128 | ✓ |
| DK09 | 58 | 600 | 228 | 116 | ✓ |
| DK06 | 54 | 272 | 264 | 108 | |
| DK04 | 52 | 600 | 255 | 104 | ✓ |
| DK03 | 48 | 240 | 235 | 96 | |
| DK08 | 38 | 586 | 222 | 152 | |
| DK01 | 36 | 215 | 210 | 144 | |

2P progression uses respawn (8 s) rather than wave-skip; long `board_time` still matters for marathon sessions.

---

## Implications — content trim vs code

| Issue | Root | Fix owner |
|-------|------|-----------|
| **`--/16` last wave @ 1214 s** | Level data — misplaced group `start_time_sec` | **Content** — move/remove orphan wave |
| **007, 008 — 106 micro-waves** | Level design — ~2 s cadence × 106 shots | **Content** — halve waves or widen cadence |
| **011, 001, Challenge — last wave > 250 s** | Stagger pushes finale near session end | **Content** — shorten tail or reduce waves |
| **16 SP levels board > 300 s** | Authored `end_time_sec` up to 600 | **Content** (optional trim) — lower `end_time` on worst rows; session timer is product constant |
| **017, 021 — 30 moving-red groups** | Hazard overlap during scoreables | **Code** — priority display (Grid/Hoops already has rank map; verify HW) |
| **Wave skip / level clear** | `game_manager` auto-jump + `_level_cleared` | **Code** — verify on long levels; no new game mode |
| **Session ends before level clears** | 300 s marathon cap vs wave count | **Content** for chronic cases; **config** only if product extends session |

**Do not invent a new game mode.** Trim waves / shorten `end_time_sec` on flagged levels first.

### Content-trim priority (SP)

1. **`--/16`** — fix 1214 s orphan wave (blocking)
2. **`007`, `008`** — reduce from 106 → ~50 waves
3. **`011`** — reduce from 70 waves or shorten last-wave start
4. **`001`, `Challenge - 85 Hoops`** — last wave > 255–281 s
5. **`002`–`005`, `009`, `010`, `014`, `015`** — `board_time` 594–600 with 40+ waves

---

## Suggested onsite test order

1. **`--/16`** — confirm level never clears (orphan wave); validate fix after content edit.
2. **`007` or `008`** — time a full clear; expect ~220 s minimum with perfect wave-skip, >300 s at normal pace.
3. **`011`** — late last wave (246 s) under session pressure.
4. **`002`** — `board_time=600`, moving red (1 group), wave-skip feel.
5. **`017` or `021`** — 30 moving-red groups + disappear mode.
6. **`024`** — only level with intentional 11 s cadence gap; verify skip.
7. **Baselines** — `006`, `018`, `020`, `023` (board < 220 s, no E flag).
8. **2P `DK05`** — 72 waves, board 600 s, respawn pacing.

---

## Hex cross-reference

See `led-hexagon/docs/ONSITE_HEX_SP_LEVEL_SWEEP.md` and `docs/ONSITE_LONG_LEVELS_HEX_HOOPS.md`.

| Metric | Hex SP | Hoops SP |
|--------|-------:|---------:|
| Levels | 35 | 25 |
| board_time = 600 s | **35 / 35 (100%)** | 5 / 25 (20%) |
| board_time > 300 s | 35 / 35 | 16 / 25 |
| Typical wave model | Goal-indicator windows (~4–300 per level) | Scoreable floor groups (**20–106**) |
| Cadence ≥ 10 s | 5 / 35 (pro stagger) | 2 / 25 (`16` bug, `24` design) |
| Unreachable last wave | 0 | **1 (`16`)** |
| Moving red + scoreable | 12 / 35 | 2 SP with heavy mred (`17`, `21`) |

Hex conclusion: **600 s board vs 300 s session is normal** — levels finish by clearing scoreables. Hoops shares that model but adds **much higher wave counts**; “level not finishing” onsite is more often **too many waves / one bad timestamp** than missing level-clear code.

---

## Related docs

- `docs/ONSITE_LONG_LEVELS_HEX_HOOPS.md` — cross-game long-level guide
- `docs/ONSITE_HEX_WORK_INDEX.md` — Hex onsite index
- `docs/HOOPS_DEVELOPMENT_PLAYBOOK.md` — tiers, session marathon
- `api/game_manager.py` — `_load_level_file`, wave skip, `_level_cleared`

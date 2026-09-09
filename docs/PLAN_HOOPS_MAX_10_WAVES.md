# Hoops — Max 10 Waves (Content Trim Plan)

> **Approach:** Edit level archives only — no engine rewrite, no new game mode.

---

## 1. Product rule

**Most Hoops levels:** no more than **10 scoreable waves**.

**Exceptions (keep as-is — long by design):**

| Level file | Waves | Notes |
|------------|------:|-------|
| `-/Challenge - 85 Hoops.led` | 52 | Marathon level; exempt from ≤10 trim |
| `-/Challenge -- 85 Hoops.led` | 48 | Marathon level; exempt from ≤10 trim |

Wave timing is **authored per group** (`start_time_sec`, `end_time_sec`). The engine does not impose one stay-until-scored pattern — each level can differ. **Inspect that file before editing.**

---

## 2. Levels over 10 waves today

From [ONSITE_HOOPS_SP_LEVEL_SWEEP.md](./ONSITE_HOOPS_SP_LEVEL_SWEEP.md) (2026-09-09). **33 levels** are candidates for trim (35 total over 10, minus 2 Challenge exceptions).

### SP — `games/source/-` and `--` (23 trim candidates)

| ID | Waves | ID | Waves | ID | Waves |
|----|------:|----|------:|----|------:|
| 007 | 106 | 011 | 70 | 006 | 37 |
| 008 | 106 | 001 | 52 | 002–003, 022–023, 025 | 36 each |
| 015 (`--/`) | 46 | 009 | 44 | 021 | 34 |
| 004–005 | 43 each | 010, 014 (`--/`) | 41 each | 020 | 33 |
| 016 (`--/`) | 32 ⚠️ | 019 | 32 | 017, 018 | 31 each |
| 024 (`--/`) | 20 | | | | |

⚠️ `--/16` has a broken orphan wave at t=1214 s — fix that separately (not a trim issue).

### 2P — `games/source/---` (10 levels)

| ID | Waves | ID | Waves |
|----|------:|----|------:|
| DK05, DK07 | 72 each | DK03 | 48 |
| DK02 | 68 | DK04 | 52 |
| DK10 | 64 | DK01 | 36 |
| DK09 | 58 | DK08 | 38 |
| DK06 | 54 | | |

---

## 3. How to trim

Open `.led` / `.ledb` as zip → edit main `game_file` shelve (`dict_group`) → re-pack.

**Before changing anything:** list scoreable `floor_light` groups for that file — note each wave’s `start_time_sec`, `end_time_sec`, and how long tiles actually stay. Do not assume all levels behave the same.

**Default approach (when a level must go ≤10 waves):**

1. Sort scoreable groups by `start_time_sec`.
2. **Keep a sensible subset** (often early waves + finale, or evenly spaced picks — judgment per level).
3. **Drop excess later waves** (or middle repeats) by removing those groups.
4. **Do not rewrite durations** on waves you keep — leave authored `start_time_sec` / `end_time_sec` unchanged unless a human designer decides otherwise for that level.

Do **not** re-time micro-waves to a fixed 4–5 s cadence. Do **not** merge many waves into one bin unless a designer asks for it.

**Do not** change session length (`game_time_sec` = 300 s) or add engine modes.

---

## 4. Engine behavior (for context)

Tiles are active only inside each group’s time window. After `end_time_sec`, they disappear even if not scored. Wave-skip jumps to the next wave when the current one is empty. Level clears when no scoreables remain in-window and no future wave exists.

This is why trim must respect **that file’s** authored windows — shortening or re-spacing `end_time_sec` changes how the level plays.

---

## 5. Checklist

1. Script or hand pass: list scoreable waves per level → per-level trim note.
2. **P0:** Fix `--/16` orphan wave.
3. **P1:** Trim `007` / `008` (106 → ≤10) using drop-excess approach.
4. **P2:** Remaining SP (`-`, `--`) except Challenge exceptions.
5. **P3:** 2P `DK*.ledb` if product owner wants 2P under same cap.
6. Re-run wave sweep — confirm non-exempt levels ≤ 10.
7. Sim smoke + onsite on `016`, `007`, short baseline (`006` or `018`).

---

## 6. Out of scope

- `game_time_sec` (300 s), new game modes, `game_manager` changes
- Challenge marathon levels (exception list above)
- Hex levels; duplicate source folders — edit progression paths only (`-`, `--`, `---`)

---

## Related

- [ONSITE_HOOPS_SP_LEVEL_SWEEP.md](./ONSITE_HOOPS_SP_LEVEL_SWEEP.md)
- [ONSITE_LONG_LEVELS_HEX_HOOPS.md](./ONSITE_LONG_LEVELS_HEX_HOOPS.md)

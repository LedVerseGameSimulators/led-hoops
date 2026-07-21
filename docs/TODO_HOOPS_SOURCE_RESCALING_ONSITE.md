# TODO — Onsite validation for Hoops source-parity 1×5→1×6 scaling

> **Status: SOFTWARE COMPLETE — physical floor revalidation PENDING.**
> Source-parity scaling, hardware fail-closed config, and diagnostic manual
> confirmation are implemented and covered by automated tests. This checklist
> is what still must be run on the real 1×6 hoop strip.

---

## What is already done (do not re-litigate onsite)

| Item | Evidence |
|------|----------|
| Pure scaler `api/level_scaling.py` with golden `both` / `none` mapping | `tests/test_level_scaling.py` |
| Load → reset → scale-once → setup → Play wiring | `api/game_manager.py`, `tests/test_level_preparation.py`, `tests/test_hoop6_gameplay.py` |
| Shared strict 1×6 / COM validator | `hardware_config.py` + `tests/test_hardware_config.py` |
| Hardware init failure aborts before Play/level load | `tests/test_hardware_boot.py` |
| Diagnostic seven-phase manual confirm + six-column input | `games/test_hardware.py`, `tests/test_hardware_diagnostic.py` |
| Docs describe exact mapping and exit-0 contract | `HARDWARE_VALIDATION.md`, `ONSITE.md`, `WINDOWS_HARDWARE_INTEGRATION.md`, `AGENT_PROMPT.md` |

Branch tip for this work: `fix/hoops-source-rescaling`.

### Exact source mapping (`scale='both'`, 1×5 → 1×6)

| Authored col | Physical col(s) |
|---|---|
| 0 | 0 |
| 1 | 1 |
| 2 | 2 **and** 3 |
| 3 | 4 |
| 4 | **5** (hoop 6) |

`activity_area` / zone end: authored `5` → physical `6`.

---

## Onsite checklist (PENDING)

Copy pass/fail into the session report. Full procedure lives in
`HARDWARE_VALIDATION.md` §4.

- [ ] Standalone `python games\test_hardware.py` with stack stopped
  - [ ] All seven output phases manually confirmed (`yes` only when lights match)
  - [ ] All six sensor cycles complete → exit code `0`
  - [ ] Floor blanks and COM closes after the run
- [ ] Start stack via `scripts\start-dev.bat`, then start a game
  - [ ] Log shows `Hardware ready: ... 1x6 ...` (not `Hardware init failed`)
- [ ] Gameplay matrix on physical columns 0–5
  - [ ] Static level (e.g. `001`): hoop 6 (col 5) lights and scores
  - [ ] Moving level (e.g. `24`): motion uses scaled bounds including col 5
  - [ ] 2P level (e.g. `DK03`): P1 owns 0/1, P2 owns 4/5 after source shift
  - [ ] Simulator UI and floor show the same 1×6 frame
- [ ] Marathon / lives / blank-on-stop still correct after the mapping change
  - [ ] life=0 mid-session restarts a freshly scaled board
  - [ ] timeout / stop / clear_all blank the floor

---

## Out of scope (known independent defects)

Do not mix these into the scaling sign-off unless they block the matrix:

- dual wave-skip behavior
- incomplete 2P respawn
- unwired `pressed_tiles` overlay state

---

## Done criteria

Mark this TODO complete only when the onsite checklist above has explicit
PASS/FAIL lines recorded (not “looks fine”). Software green alone is not
enough.

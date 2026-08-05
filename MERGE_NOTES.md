# led-hoops onsite merge notes — 2026-08-03

**Branch:** `merge/onsite-takeaway-2026-08-03` (from `fix/hoops-source-rescaling` @ `95c85a7`)  
**Takeaway zip:** `led-hoops-onsite-takeaway-2026-08-03_1825.zip`  
**Onsite extract:** `.onsite-analysis/led-hoops/led-hoops/` (parent monorepo)

## Verdict

Low-risk confirmation merge. Application code, shelve, and frontend already matched local tip. Only operator tooling was missing locally.

## Changes committed

| File | Action |
|------|--------|
| `START_GAME.bat` | Added — one-click hardware start (API 8000, bridge 8765, UI 5173) |
| `STOP_GAME.bat` | Added — kills titled windows + frees ports 8000/8765/5173 |
| `scripts/run-api-hardware.bat` | Added — launches API with `USE_SERIAL_HD=1` |
| `OPERATOR_GUIDE.md` | Added — floor-staff start/play/stop guide |

## Verified identical (no copy)

| Path | Result |
|------|--------|
| `api/` | Identical (except `__pycache__`) |
| `games/led/` | Identical (except `__pycache__`) |
| `hardware_config.py`, `ws_bridge.py` | Identical |
| `frontend/src/**` | Identical |
| `games/setting/led_parameter.*` | Identical — COM3, `value_width=6` |
| `games/setting/debug_parameter.*` | Identical |
| `games/setting/language_parameter.*` | Identical |
| `games/setting/program_params.*` | Identical |

## Not committed (by design)

| Path | Reason |
|------|--------|
| `frontend/.env` | Deploy-only — onsite uses `VITE_RFID_API_URL=http://192.168.1.18:9000`; confirm live RFID IP on LAN before deploy |
| `ledplaydb.sqlite` | Runtime score DB — keep on venue PC (onsite had 65 rows vs 10 local) |
| `games/source/**`, `games/source_group/**` | Onsite extract incomplete; local zip-equivalent copies kept |

## Blockers

**None.** No unexpected RFID URL, COM port, or gameplay differences in code paths reviewed.

## Tests

```text
pytest tests/ -q
87 passed, 163 subtests passed in ~2s
```

Hardware checklist (site revalidation — not run here):

- [ ] `START_GAME.bat` → HARDWARE MODE ON, `/hw-debug` `use_serial_hd: true`
- [ ] UI `:5173`, RFID validate hits correct host
- [ ] Group mode from `source_group/`
- [ ] Physical hoop 6 + floor animates; game ends cleanly
- [ ] `STOP_GAME.bat` frees ports

## Deploy notes

1. On site PC: `git pull` on merged branch (after push to `LedVerseGameSimulators/led-hoops`).
2. Create `frontend/.env` with venue RFID IP (onsite used `.18`; LAN docs also mention `.106`).
3. Keep venue `ledplaydb.sqlite` if leaderboard history matters.
4. First run may trigger `npm install` via `START_GAME.bat`.

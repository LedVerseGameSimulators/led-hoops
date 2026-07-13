# Locked baseline — simulator-ready headless stack

**Tag:** `sim-ready-2026-06-07`  
**Date:** 2026-06-07

This tag marks the **Hoops** headless migration at simulator parity. Game logic, React UI, ws_bridge, and parallel ports are stable for dev. Hardware serial I/O was **not yet** integrated at this tag (by design).

> **Update (post-tag):** Hardware serial I/O (`USE_SERIAL_HD`, `_hw_init()`, per-frame `led_control.draw_screen_by_com`/`update_screen_state_by_com`) was added in commit `f86d7dd` (2026-06-30) and validated on the real physical LED floor during on-site testing that landed in commit `9cf58ff`, "Merge Windows hardware validation fixes" (2026-07-07) — see `WINDOWS_HARDWARE_INTEGRATION.md` for the fixes found during that session. Since then, this session's cross-tier marathon loop, 5-heart lives, RFID card-scan login, credit-gated sessions, pushable settings, and persistent player badge work (commits `966e77c` through `4aaf708`, 2026-07-11 to 2026-07-13) have landed on top of that validated hardware layer but have **not** been re-validated on real hardware. See `HARDWARE_VALIDATION.md` for current status and the onsite re-validation checklist.

| Service | Port |
|---------|------|
| UI | 5173 |
| API | 8000 |
| ws_bridge | 8765 |

**Canonical doc:** [`docs/HOOPS_DEVELOPMENT_PLAYBOOK.md`](./HOOPS_DEVELOPMENT_PLAYBOOK.md)

**Checkout this baseline:**
```bash
git checkout sim-ready-2026-06-07
```

**Next game migration:** Laser — see `../led-laser/docs/LASER_MIGRATION.md`

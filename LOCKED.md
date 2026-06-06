# Locked baseline — simulator-ready headless stack

**Tag:** `sim-ready-2026-06-07`  
**Date:** 2026-06-07

This tag marks the **Hoops** headless migration at simulator parity. Game logic, React UI, ws_bridge, and parallel ports are stable for dev. Hardware serial I/O is **not** integrated (by design).

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

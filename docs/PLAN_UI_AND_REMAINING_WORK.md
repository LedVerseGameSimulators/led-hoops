# Hoops — UI redesign + remaining work

**Date:** 2026-09-16  
**Repo:** `led-hoops`  
**Parent:** `docs/PLAN_FE_REDESIGN_AND_WORK_INDEX.md`

---

## Locked FE decisions

| Topic | Decision |
|-------|----------|
| Journey | **Mode → Settings\* → Login → Play** (*Tournament skips Settings) |
| Modes | **Quick Play** / **Team Battle** / **Tournament** |
| Levels | QP + TB: **20 + 20** placeholders, Medium; Tournament: existing **~10**, **no level select** |
| Login | **Always** — RFID **or** play without RFID → **random names**; **no** name-typing form |
| Tournament names | UI **1, 2, 3…** on HUD + results/leaderboards (never file names) |
| Orientation | **Landscape only** |
| Video | **One** bg loop per game (reuse across Mode / Login / Results) |
| How-to-play | **We write** short copy; client can edit later |
| Countdown | **Both** — TV overlay on play **and** floor `countdown.led` |
| Screen order | **Locked = today’s order** (mock Login→Setup→Countdown is visual ref only) |

---

## Implementation status

- [x] Decisions locked (2026-09-16)
- [x] Score/RFID logical level labels (Hex contract): `levelPlaylists.js`, guest skip save, `level_file` columns
- [ ] **After Hex FE shell** is the template — apply same shell here
- [ ] Wire modes + 20+20 placeholders + Tournament skip Settings
- [ ] Login: RFID path + guest random names
- [ ] Copy `hoops_background.mp4` → `frontend/public/media/` + wire bg
- [ ] Restyle Play HUD + Results; Tournament labels 1, 2, 3…

---

## Non-FE leftovers

- [ ] Shared **2P rules** — **FE goal-color swatches only** this pass (no scoring/wave changes)
- [ ] ~~Content: max ~10 waves / long-level sweeps~~ — **deprioritized**
- [ ] Optional: delete dead FE screens
- [ ] Full Hoops 2P scoring/wave — **deferred**

---

## Assets

| Asset | Path (not in repo yet) |
|-------|------------------------|
| Loop | `~/Downloads/activerse_redesign/hoops_background.mp4` |
| Still | `~/Downloads/activerse_redesign/hoops.jpeg` |

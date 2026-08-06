# LED Hoops — effects spec

Audio, countdown, and LED behavior for **LED Hoops**.

Global rules: [activerse_final_changes/docs/game-effects/GLOBAL_RULES.md](../../docs/game-effects/GLOBAL_RULES.md)

---

## Audio assets

| Asset | File / source |
|-------|---------------|
| **BGM** | *Thank You Not So Bad* — level play only |
| **Positive score SFX** | Shared positive MP3 (cross-game) |
| **Negative score SFX** | Shared negative MP3 (cross-game) |
| **Countdown** | Tick/noise during 3-2-1; **no BGM** |
| **Level transition** | Short stinger ~2–3 s (asset TBD / stock OK) |

---

## Countdown (game start only)

Runs **once** per session at game start. **Not** repeated on level change or level restart.

All countdown hoops use **green** LEDs. Tick/noise audio; no BGM.

| Step | LED pattern |
|------|-------------|
| **3** | 2 middle hoops on |
| **2** | Left + right of those middle hoops (4 total) |
| **1** | All hoops green |
| **GO** | Level play begins |

UI countdown and hoop LEDs stay in sync.

---

## Level clear

1. All hoops **green**
2. ~2–3 s transition with stinger SFX (not BGM)
3. **Next level** starts directly — **no countdown**

---

## Level fail

Triggered when **all lives are lost**.

1. All hoops **red**
2. ~2–3 s transition with stinger SFX (not BGM)
3. **Same level restart** directly — **no countdown**

---

## Timer expire

Same LED treatment as **level clear**.

If the timer expires on the **final level** and the session ends → all LEDs **black / off** after the clear transition.

---

## In-game (Hoops-only)

| Event | LED behavior |
|-------|--------------|
| Penalty / perfect hoop press | Red hoop **blinks 1–2×** on press |

---

## Reference media

Capture and timing reference: **`~/Downloads/Hoops 2/`**

Use for LED pattern design only — not frontend video playback.

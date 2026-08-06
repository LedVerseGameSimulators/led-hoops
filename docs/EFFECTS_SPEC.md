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

## Countdown (every level start)

Runs before **every level** — first level of the session, after level clear,
and after level fail restart. **Not** repeated when the session has ended.

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
3. **Countdown** (3-2-1-GO)
4. **Next level** play begins

---

## Level fail

Triggered when **all lives are lost**.

1. All hoops **red**
2. ~2–3 s transition with stinger SFX (not BGM)
3. **Countdown** (3-2-1-GO)
4. **Same level** restart play begins

---

## Timer expire (= session end)

Same LED treatment as **level clear** (e.g. all green for Hoops).

1. Hold clear pattern ~2–3 s with transition stinger (not BGM)
2. All LEDs **black / off**
3. **No countdown** — session is over

---

## In-game (Hoops-only)

| Event | LED behavior |
|-------|--------------|
| Penalty / perfect hoop press | Red hoop **blinks 1–2×** on press |

---

## Reference media

Capture and timing reference: **`~/Downloads/Hoops 2/`**

Use for LED pattern design only — not frontend video playback.

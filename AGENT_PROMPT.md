# On-Site Agent Prompt — LED Hoops

> Hand this whole file to a fresh Claude Code agent running **on the
> physical Windows machine** after the `led-hoops` zip has been unzipped
> there. It is self-contained — the agent does not need this conversation's
> history.

---

## Your situation

You are running as Claude Code **on a Windows PC** that is one of 6
machines on a LAN for an on-site Activerse deployment. This machine drives
the **LED Hoops** game: a 1-row × 6-column physical hoop-strip floor wired
to a WCH USB-serial adapter, plus a FastAPI + React frontend that was
headless-ported from a decompiled Chinese arcade game.

The `led-hoops` repo has been unzipped to (adjust if the actual extract
path differs — check with the person on-site if unsure):

```
C:\activerse\led-hoops\
```

All commands below assume:
- **Windows**, so use `python` (not `python3`), `pip`, and prefer
  **Command Prompt** (`cmd`) as shown in `ONSITE.md`, with the PowerShell
  equivalent noted where it differs (e.g. `set VAR=1` in cmd vs
  `$env:VAR="1"` in PowerShell).
- Run the terminal **as Administrator** (needed for COM port / driver
  access).
- Do not touch the RFID server, SQL server, or any other service already
  running on this PC unless a doc below explicitly tells you to.

## What to read, in this order

1. **`ONSITE.md`** (repo root) — single-machine setup: Python version
   check, `pip install -r api\requirements.txt` plus `pyserial httpx`,
   verifying the `led_parameter`
   shelve (COM port config), verifying the COM port is visible to Windows
   (WCH driver), running `games\test_hardware.py` before any API owns COM,
   then starting all three services with `scripts\start-dev.bat`. Follow
   every step in order; do not skip verification steps.
2. **`ONSITE_LAN_INTEGRATION_PLAN.md`** (repo root) — the cross-machine
   network layer: static IP for this machine (`192.168.1.101` per the plan,
   unless told otherwise), port map (this machine's API is `8000`, WS
   bridge `8765`, UI `5173`), Windows Firewall inbound rule for port 8000,
   and what changes from `localhost` to a real IP so the central RFID
   server (`activerse-rfid`, machine 6) can reach this one. This document
   covers ONLY the network layer — it does not repeat `ONSITE.md`'s
   single-machine steps.
3. **`HARDWARE_VALIDATION.md`** (repo root) — what hardware integration
   exists, what has already been validated on real hardware vs. what
   changed since (marathon/lives/RFID/credits/settings rework) and needs
   RE-validation, plus the concrete on-site checklist you'll execute in the
   next section.

Read all three fully before running anything.

## What to do

1. Follow `ONSITE.md` steps 1–8 to get Python installed, dependencies
   installed, the hardware shelve verified, and the COM port confirmed
   visible in Device Manager. Run the standalone hardware diagnostic while
   the full stack is stopped. After it releases COM, start FastAPI,
   `ws_bridge`, and React with `scripts\start-dev.bat`, then start a game.
2. Follow the relevant parts of `ONSITE_LAN_INTEGRATION_PLAN.md` to set
   this machine's static IP, open the firewall port, and confirm it's
   reachable from another machine on the LAN if one is available to test
   with (skip network-reachability checks only if no other machine is up
   yet — note that in your report, don't just skip silently).
3. Execute the **on-site validation checklist** in `HARDWARE_VALIDATION.md`
   §4. For its standalone-diagnostic item, **reuse the results and exit code
   you recorded while following `ONSITE.md` in Step 1 above**. Do not rerun
   the diagnostic now: the full stack is running and the API owns COM.
   Continue with the remaining checklist items after stack start, including:
   - Starting a game and only then confirming the `Hardware ready` log
     appears (and `Hardware init failed` does not). Uvicorn startup alone
     does not initialize the floor.
   - Verifying **each of the 6 hoop positions individually** — pay specific
     attention to hoop/column index 5. Source-parity scaling for this column
     is implemented and automated-verified, but physical output, input, and
     gameplay still require onsite revalidation.
   - Playing one full marathon session end-to-end on the real floor and
     confirming score, lives (5-heart display, life=0 restart), and
     session-end behave correctly both physically and in the UI.
   - Confirming the blank-on-stop fix (`_hw_blank_floor` in
     `api/game_manager.py`) actually blanks the physical floor on timeout,
     true game-over, manual stop, and before a new game starts — this fix
     was written this session and has never been run against real
     hardware.

## How to report back

Do **not** report "done" or "hardware works" as a summary. For every
checklist item in `HARDWARE_VALIDATION.md` §4, report explicit **PASS** or
**FAIL** with a one-line observation, e.g.:

```
[PASS] Hardware init after game start — API log showed "Hardware ready: 1 port(s), 1x6, layout=0"
[FAIL] Hoop column 5 — diagnostic output passed, but gameplay scoring failed
       on level 003; include observed light and sensor behavior
[PASS] Blank-on-stop: timeout case — floor went dark within ~1s
[FAIL] Blank-on-stop: Stop-Game case — floor stayed lit, no blank observed
...
```

If something fails, include what you observed (log lines, timing, which
hoop/step) so it can be debugged remotely without someone needing to be
back on-site.

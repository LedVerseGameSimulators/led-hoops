"""Debug simulator: start a game and poll led_display."""
import time
import httpx

BASE = "http://localhost:8000"


def main():
    r = httpx.post(
        f"{BASE}/start-game",
        json={
            "card_id": "debug",
            "level": "17",
            "difficulty": "normal",
            "player_count": 1,
        },
        timeout=30,
    )
    print("start:", r.status_code, r.text[:400])
    d = r.json()
    if not d.get("success"):
        return 1
    gid = d["game_id"]
    print("game_id:", gid)

    prev_lit = -1
    for i in range(30):
        s = httpx.get(f"{BASE}/game-state/{gid}", timeout=5).json()
        if not s.get("success"):
            print(f"poll {i}: game-state failed:", s)
            break
        st = s["state"]
        ld = st.get("led_display", [])
        lit = sum(
            1 for c in ld
            if isinstance(c, (list, tuple)) and len(c) >= 3 and sum(c[:3]) > 0
        )
        changed = lit != prev_lit
        prev_lit = lit
        print(
            f"poll {i}: game_over={st.get('game_over')} "
            f"t={st.get('time_elapsed', 0):.2f} "
            f"lit={lit}/{len(ld)} "
            f"grid={st.get('grid_rows')}x{st.get('grid_cols')} "
            f"score={st.get('score')} "
            f"reason={st.get('game_over_reason')} "
            f"{'CHANGED' if changed else ''}"
        )
        if ld and lit > 0 and i == 0:
            print("  sample colors:", ld[:6])
        if st.get("game_over"):
            break
        time.sleep(0.5)

    ag = httpx.get(f"{BASE}/active-game", timeout=5).json()
    print("active-game:", ag.get("success"), "id:", ag.get("game_id"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

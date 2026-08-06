"""API session-loop tests for LED transition effects (TESTING_CONTRACT T1–T8, T10)."""
from __future__ import annotations

import os
import sys
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

# Ensure repo root is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

import api.game_manager as game_manager
from tests.effect_fixtures import EFFECTS_DIR, LEVELS_DIR, ensure_all_fixtures

FIXTURES = ensure_all_fixtures()
TINY_A = str(FIXTURES["tiny"])
TINY_B = str(FIXTURES["tiny_b"])
TINY_FAST = str(FIXTURES["tiny_fast"])

FAST_SETTINGS = {
    "game_time_sec": 120.0,
    "life_value": 8,
    "life_value_count_time": 0.05,
    "leval_span": 0.8,
    "tread_red_time": 0.01,
    "grid_rows": 1,
    "grid_cols": 6,
    "floor_layout_coors_no_use": [],
    "blue_hide_max_time": 20.0,
    "scode_divide_person": False,
    "scode_divide_time": False,
    "player_num": 1,
}

_ORIG_SLEEP = time.sleep


def _fast_sleep(seconds):
    _ORIG_SLEEP(min(float(seconds), 0.002))


@contextmanager
def session_test_env(*, level_sequence=None, game_time_sec=120.0, life_value=8):
    settings = dict(FAST_SETTINGS)
    settings["game_time_sec"] = game_time_sec
    settings["life_value"] = life_value
    seq = level_sequence or [TINY_A]
    game_manager._settings_cache = None

    with mock.patch("api.game_manager.load_real_settings", return_value=settings), \
         mock.patch("api.game_manager._build_level_sequence", return_value=list(seq)), \
         mock.patch.dict(os.environ, {"HOOPS_EFFECTS_DIR": str(EFFECTS_DIR)}, clear=False), \
         mock.patch("api.game_manager.time.sleep", side_effect=_fast_sleep):
        game_manager.get_manager().clear_all()
        yield


def _poll_state(client: TestClient, game_id: str, timeout: float = 8.0):
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        resp = client.get(f"/game-state/{game_id}")
        if resp.status_code == 200 and resp.json().get("success"):
            last = resp.json()["state"]
            yield last
        time.sleep(0.01)
    return last


def _wait_phase(client, game_id, phase, *, timeout=8.0):
    for state in _poll_state(client, game_id, timeout):
        if state.get("phase") == phase:
            return state
    raise AssertionError(f"Timed out waiting for phase={phase!r}")


def _wait_until(client, game_id, predicate, *, timeout=8.0):
    for state in _poll_state(client, game_id, timeout):
        if predicate(state):
            return state
    raise AssertionError("Timed out waiting for predicate")


def _start_session(client: TestClient, *, game_time_sec: float | None = None):
    resp = client.post(
        "/start-game",
        json={
            "card_id": "TEST-CARD",
            "level": "tiny",
            "difficulty": "normal",
            "player_count": 1,
        },
    )
    data = resp.json()
    assert data.get("success"), data
    game_id = data["game_id"]
    if game_time_sec is not None:
        game = game_manager.get_manager().get_game(game_id)
        if game is not None:
            game.game_time_sec = float(game_time_sec)
            game.update_state(time_left=float(game_time_sec))
    return game_id


def _collect_phases(client, game_id, *, timeout=12.0, stop_on=None):
    phases = []
    last = {}
    for state in _poll_state(client, game_id, timeout):
        last = state
        phase = state.get("phase")
        if phase and (not phases or phases[-1] != phase):
            phases.append(phase)
        if stop_on and stop_on(state, phases):
            return phases, state
    return phases, last


class EffectsSessionLoopTests(unittest.TestCase):
    def setUp(self):
        game_manager._settings_cache = None
        game_manager.get_manager().clear_all()

    def tearDown(self):
        game_manager._settings_cache = None
        game_manager.get_manager().clear_all()

    # ── T1: session start reaches playing with input enabled ──────────────

    def test_t1_session_start_countdown_then_playing(self):
        with session_test_env():
            from api.main import app

            with TestClient(app) as client:
                game_id = _start_session(client)
                seen = set()
                final = None
                for state in _poll_state(client, game_id, timeout=10):
                    phase = state.get("phase")
                    if phase:
                        seen.add(phase)
                    if phase == "playing" and state.get("accepting_input") is True:
                        final = state
                        break
                self.assertIn("countdown", seen)
                self.assertIsNotNone(final, f"phases seen: {seen}")
                self.assertEqual(final.get("phase"), "playing")
                self.assertTrue(final.get("accepting_input"))

    # ── T7: input gated during transitions ────────────────────────────────

    def test_t7_input_blocked_during_countdown(self):
        with session_test_env():
            from api.main import app

            with TestClient(app) as client:
                game_id = _start_session(client)
                gated_state = _wait_phase(client, game_id, "countdown")
                self.assertFalse(gated_state.get("accepting_input", True))
                score_before = gated_state.get("score", 0)
                life_before = gated_state.get("life", FAST_SETTINGS["life_value"])
                resp = client.post(
                    "/game-input",
                    json={"game_id": game_id, "row": 0, "col": 4, "type": "press"},
                )
                # Blocked input may return success=False; score/life must not change.
                mid = client.get(f"/game-state/{game_id}").json()["state"]
                self.assertEqual(mid.get("score"), score_before)
                self.assertEqual(mid.get("life"), life_before)

    # ── T8: gameplay still scores during playing ──────────────────────────

    def test_t8_playing_accepts_input_and_scores(self):
        with session_test_env():
            from api.main import app

            with TestClient(app) as client:
                game_id = _start_session(client)
                playing = _wait_until(
                    client,
                    game_id,
                    lambda s: s.get("phase") == "playing"
                    and s.get("accepting_input") is True,
                )
                score_before = playing.get("score", 0)
                resp = client.post(
                    "/game-input",
                    json={"game_id": game_id, "row": 0, "col": 4, "type": "press"},
                )
                self.assertTrue(resp.json().get("success"))
                scored = _wait_until(
                    client,
                    game_id,
                    lambda s: s.get("score", 0) > score_before,
                )
                self.assertGreater(scored.get("score", 0), score_before)

    # ── T2: countdown between levels after clear ─────────────────────────

    def test_t2_clear_advances_through_countdown_to_next_level(self):
        with session_test_env(level_sequence=[TINY_FAST, TINY_B]):
            from api.main import app

            with TestClient(app) as client:
                game_id = _start_session(client)
                _wait_until(
                    client,
                    game_id,
                    lambda s: s.get("phase") == "playing"
                    and s.get("accepting_input") is True,
                )
                phases = []
                for state in _poll_state(client, game_id, timeout=12):
                    phase = state.get("phase")
                    if phase and (not phases or phases[-1] != phase):
                        phases.append(phase)
                    if (
                        phase == "playing"
                        and state.get("current_level") == "tiny_b"
                        and state.get("accepting_input") is True
                    ):
                        break
                self.assertIn("level_clear", phases)
                clear_idx = phases.index("level_clear")
                self.assertEqual(phases[clear_idx + 1], "countdown")
                self.assertIn("playing", phases[clear_idx + 2 :])

    # ── T3: life=0 with >10s left → fail → countdown → same level ────────

    def test_t3_life_restart_plays_fail_then_countdown_same_level(self):
        with session_test_env(level_sequence=[TINY_A], life_value=4):
            from api.main import app

            with TestClient(app) as client:
                game_id = _start_session(client)
                _wait_until(
                    client,
                    game_id,
                    lambda s: s.get("phase") == "playing"
                    and s.get("accepting_input") is True,
                )
                score_before = client.get(f"/game-state/{game_id}").json()["state"]["score"]
                phases = []
                final = {}
                for state in _poll_state(client, game_id, timeout=15):
                    final = state
                    phase = state.get("phase")
                    if phase and (not phases or phases[-1] != phase):
                        phases.append(phase)
                    if phase == "playing" and state.get("accepting_input"):
                        client.post(
                            "/game-input",
                            json={"game_id": game_id, "row": 0, "col": 0, "type": "press"},
                        )
                    if (
                        phase == "playing"
                        and phases.count("level_fail") == 1
                        and state.get("accepting_input") is True
                    ):
                        break
                self.assertIn("level_fail", phases)
                fail_idx = phases.index("level_fail")
                self.assertEqual(phases[fail_idx + 1], "countdown")
                self.assertEqual(final.get("current_level"), "tiny")
                self.assertEqual(final.get("score"), score_before - 4)
                self.assertEqual(final.get("life"), 4)

    # ── T4: timer expire → session end, no countdown after ─────────────

    def test_t4_timer_expire_session_end_no_countdown(self):
        with session_test_env(level_sequence=[TINY_A]):
            from api.main import app

            with TestClient(app) as client:
                game_id = _start_session(client, game_time_sec=0.6)
                phases, final = _collect_phases(
                    client,
                    game_id,
                    timeout=10,
                    stop_on=lambda s, _p: bool(s.get("game_over")),
                )
                self.assertTrue(final.get("game_over"))
                self.assertIn("session_end", phases)
                if "countdown" in phases:
                    last_cd = max(i for i, p in enumerate(phases) if p == "countdown")
                    self.assertNotIn("countdown", phases[last_cd + 1 :])

    # ── T5: life=0 with ≤10s left → clear path, no fail/countdown ────────

    def test_t5_life_zero_near_timer_uses_clear_session_end(self):
        with session_test_env(level_sequence=[TINY_A], life_value=4):
            from api.main import app

            with TestClient(app) as client:
                game_id = _start_session(client, game_time_sec=12)
                _wait_until(
                    client,
                    game_id,
                    lambda s: s.get("phase") == "playing"
                    and s.get("accepting_input") is True,
                )
                _ORIG_SLEEP(3.0)
                for _ in range(20):
                    client.post(
                        "/game-input",
                        json={"game_id": game_id, "row": 0, "col": 0, "type": "press"},
                    )
                    _ORIG_SLEEP(0.03)
                phases, final = _collect_phases(
                    client,
                    game_id,
                    timeout=10,
                    stop_on=lambda s, _p: bool(s.get("game_over")),
                )
                self.assertTrue(final.get("game_over"))
                self.assertNotIn("level_fail", phases)
                self.assertIn("session_end", phases)

    # ── T6: last level cleared → session end, no countdown ───────────────

    def test_t6_last_level_cleared_session_end_no_countdown(self):
        with session_test_env(level_sequence=[TINY_FAST]):
            from api.main import app

            with TestClient(app) as client:
                game_id = _start_session(client)
                phases = []
                for state in _poll_state(client, game_id, timeout=10):
                    phase = state.get("phase")
                    if phase:
                        phases.append(phase)
                    if state.get("game_over"):
                        break
                self.assertIn("level_clear", phases)
                clear_idx = max(i for i, p in enumerate(phases) if p == "level_clear")
                self.assertNotIn("countdown", phases[clear_idx + 1 :])
                self.assertIn("session_end", phases)


class HoopsRedBlinkTests(unittest.TestCase):
    """T10 — penalty-only red blink (not scoring hoops)."""

    def test_t10_red_penalty_blinks_goal_does_not(self):
        from tests.effect_fixtures import build_tiny_gameplay_led

        path = LEVELS_DIR / "blink_test.led"
        build_tiny_gameplay_led(path)
        groups, game_obj = game_manager._load_level_file(path)
        game_manager.prepare_level_for_platform(groups, game_obj, FAST_SETTINGS)
        settings = dict(FAST_SETTINGS)
        with mock.patch("api.game_manager.load_real_settings", return_value=settings):
            session = game_manager.GameInstance("t", "c", 1, "normal", 1)
        session.dict_group = groups
        session.led_table = game_manager.HeadlessLedTable(10, 1, 6)
        session.zone = (0, 1, 0, 6)
        session.accepting_input = True
        session.play = SimpleNamespace(total_pass=0.0)

        session.try_score_cell(0, 4)
        self.assertNotIn((0, 4), session.flashes)

        before = dict(session.flashes)
        session.try_score_cell(0, 0)
        self.assertIn((0, 0), session.flashes)
        self.assertNotEqual(session.flashes, before)


if __name__ == "__main__":
    unittest.main()

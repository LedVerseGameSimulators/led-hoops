"""API session-loop tests for LED transition effects (TESTING_CONTRACT T1–T8, T10)."""
from __future__ import annotations

import os
import sys
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
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
        time.sleep(0.02)
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


def _start_session(client: TestClient):
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
    return data["game_id"]


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


if __name__ == "__main__":
    unittest.main()

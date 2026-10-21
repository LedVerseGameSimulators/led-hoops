"""POST /start-game playlist id validation (mirrors Grid)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient


class StartGamePlaylistValidationTests(unittest.TestCase):
    def _client(self):
        from api.main import app

        return TestClient(app)

    def _payload(self, level: str, **extra):
        body = {
            "card_id": "TEST-CARD",
            "level": level,
            "difficulty": "normal",
            "player_count": 1,
        }
        body.update(extra)
        return body

    def test_unknown_playlist_id_rejected_before_game_created(self):
        with (
            mock.patch("api.main.db.check_session_remaining", return_value=3600.0),
            mock.patch("api.main.game_manager.start_game"),
            mock.patch("api.main.game_manager.create_game") as create_game,
        ):
            resp = self._client().post(
                "/start-game",
                json=self._payload("not-a-real-playlist-id"),
            )
        data = resp.json()
        self.assertFalse(data.get("success"))
        self.assertIn("Unknown playlist", data.get("error", ""))
        create_game.assert_not_called()

    def test_valid_playlist_id_starts_game(self):
        with (
            mock.patch("api.main.db.check_session_remaining", return_value=3600.0),
            mock.patch("api.main.game_manager.start_game"),
            mock.patch("api.main.game_manager.create_game", return_value="abc12345"),
        ):
            resp = self._client().post("/start-game", json=self._payload("006"))
        data = resp.json()
        self.assertTrue(data.get("success"), data)
        self.assertEqual(data.get("game_id"), "abc12345")


if __name__ == "__main__":
    unittest.main()

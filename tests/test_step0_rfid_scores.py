"""Step 0 RFID play-fact columns on hex_scores (hoops)."""
from __future__ import annotations

import importlib
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _fresh_db_module(games_root: str):
    root = str(Path(games_root).resolve())
    os.environ["GAMES_ROOT"] = root
    import api.config as config_mod
    import api.database as db_mod

    importlib.reload(config_mod)
    importlib.reload(db_mod)
    return db_mod


def test_record_and_poll_new_fields_and_same_second_cursor():
    with tempfile.TemporaryDirectory() as td:
        db_mod = _fresh_db_module(td)
        db = db_mod.Database()

        shared_ts = "2026-10-20T12:00:00"
        with db._scores_lock:
            con = db._scores_conn()
            con.execute(
                """
                INSERT INTO hex_scores (
                    card_id, level, score, life, time_used, ts, game
                ) VALUES (?,?,?,?,?,?,?)
                """,
                ("OLD1", "1", 10, 3, 1.0, shared_ts, db_mod.GAME_NAME),
            )
            con.execute(
                """
                INSERT INTO hex_scores (
                    card_id, level, score, life, time_used, ts, game,
                    play_mode, session_id, group_id, roster_size_at_play, roster_player_ids
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "CARD1",
                    "1",
                    100,
                    2,
                    30.0,
                    shared_ts,
                    db_mod.GAME_NAME,
                    "quick_play",
                    7,
                    3,
                    4,
                    "[10, 11, 12, 13]",
                ),
            )
            con.commit()
            con.close()

        rows = db.get_scores_since(shared_ts)
        assert len(rows) >= 2
        new_row = next(r for r in rows if r["card_id"] == "CARD1")
        assert new_row["play_mode"] == "quick_play"
        assert new_row["session_id"] == 7
        assert new_row["group_id"] == 3
        assert new_row["roster_size_at_play"] == 4
        assert new_row["roster_player_ids"] == "[10, 11, 12, 13]"

        old_row = next(r for r in rows if r["card_id"] == "OLD1")
        assert old_row["play_mode"] is None

        ok = db.record_game_score(
            {
                "card_id": "CARD2",
                "level": "2",
                "score": 55,
                "life": 1,
                "time_used": 5.0,
                "play_mode": "tournament",
                "session_id": 99,
            }
        )
        assert ok
        polled = db.get_scores_since("2000-01-01T00:00:00")
        assert any(r["card_id"] == "CARD2" and r["play_mode"] == "tournament" for r in polled)


def test_save_score_endpoint_old_and_new_payloads():
    with tempfile.TemporaryDirectory() as td:
        _fresh_db_module(td)
        import api.main as main_mod

        importlib.reload(main_mod)
        client = TestClient(main_mod.app)

        r_old = client.post(
            "/save-score",
            json={
                "card_id": "LEGACY",
                "level": "2",
                "score": 50,
                "life": 1,
                "time_used": 12.0,
            },
        )
        assert r_old.status_code == 200
        assert r_old.json()["success"] is True

        r_new = client.post(
            "/save-score",
            json={
                "card_id": "TB1",
                "card_id2": "TB2",
                "multiplayer": True,
                "level": "1",
                "score": 80,
                "score2": 70,
                "play_mode": "team_battle",
                "session_id": 1,
                "group_id": 10,
                "roster_size_at_play": 2,
                "roster_player_ids": [1, 2],
                "session_id2": 2,
                "group_id2": 20,
                "roster_size_at_play2": 3,
                "roster_player_ids2": [3, 4, 5],
            },
        )
        assert r_new.status_code == 200
        assert r_new.json()["success"] is True

        scores = client.get("/scores", params={"since": "2000-01-01T00:00:00"}).json()
        assert scores["success"] is True
        tb = next(s for s in scores["scores"] if s["card_id"] == "TB1")
        assert tb["play_mode"] == "team_battle"
        assert tb["session_id2"] == 2
        assert tb["roster_player_ids2"] == "[3, 4, 5]"


def test_alter_adds_columns_on_legacy_table():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        setting = root / "setting"
        setting.mkdir(parents=True)
        db_path = setting / "ledplaydb.sqlite"
        con = sqlite3.connect(db_path)
        con.execute(
            """
            CREATE TABLE hex_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id TEXT, level TEXT, score INTEGER, life INTEGER,
                time_used REAL, ts TEXT, game TEXT
            )
            """
        )
        con.commit()
        con.close()

        db_mod = _fresh_db_module(str(root))
        db_mod.Database()

        con = sqlite3.connect(db_path)
        cols = {row[1] for row in con.execute("PRAGMA table_info(hex_scores)")}
        con.close()
        for name in (
            "play_mode",
            "session_id",
            "group_id",
            "roster_size_at_play",
            "roster_player_ids",
            "session_id2",
            "group_id2",
            "roster_size_at_play2",
            "roster_player_ids2",
        ):
            assert name in cols


def _score_row_count(db_mod) -> int:
    db = db_mod.Database()
    with db._scores_lock:
        con = db._scores_conn()
        n = con.execute("SELECT COUNT(*) FROM hex_scores").fetchone()[0]
        con.close()
    return n


def test_logout_does_not_insert_hex_scores_after_save_score():
    with tempfile.TemporaryDirectory() as td:
        db_mod = _fresh_db_module(td)
        import api.main as main_mod

        importlib.reload(main_mod)
        main_mod.game_manager.stop_game = lambda _gid: {
            "success": True,
            "state": {"score": 999},
        }
        client = TestClient(main_mod.app)

        client.post(
            "/save-score",
            json={
                "card_id": "SAVE1",
                "level": "1",
                "score": 10,
                "life": 1,
                "time_used": 1.0,
                "play_mode": "quick_play",
            },
        )
        after_save = _score_row_count(db_mod)
        assert after_save == 1

        client.post(
            "/logout",
            json={"card_id": "SAVE1", "game_id": "fake-game-id"},
        )
        after_logout = _score_row_count(db_mod)
        assert after_logout == after_save


def test_logout_alone_does_not_write_guest_or_empty_card_row():
    with tempfile.TemporaryDirectory() as td:
        db_mod = _fresh_db_module(td)
        import api.main as main_mod

        importlib.reload(main_mod)
        main_mod.game_manager.stop_game = lambda _gid: {
            "success": True,
            "state": {"score": 50},
        }
        client = TestClient(main_mod.app)

        before = _score_row_count(db_mod)
        client.post(
            "/logout",
            json={"card_id": "", "game_id": "guest-session"},
        )
        after = _score_row_count(db_mod)
        assert after == before == 0

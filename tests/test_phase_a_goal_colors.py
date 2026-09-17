"""Phase A smoke: publish P1/P2 goal colors only; hazard scoring unchanged."""
from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import api.game_manager as game_manager


SETTINGS = {
    "grid_rows": 1,
    "grid_cols": 6,
    "floor_layout_coors_no_use": [],
}
SOURCE = Path(game_manager.GAMES_ROOT) / "source"
P1_BLUE = [0, 0, 254]
P2_ORANGE = [254, 128, 0]


def rings(rgb):
    return [rgb, rgb, rgb]


def source_game():
    return SimpleNamespace(
        row=1,
        col=5,
        zone_row_from=0,
        zone_row_to=1,
        zone_col_from=0,
        zone_col_to=5,
        corner_line_start=0,
        wall_light=False,
        screen=False,
        cover_action=False,
        play_order=False,
    )


def controlled_group(rgb, *, start=(0, 4)):
    return SimpleNamespace(
        start_member={start},
        scale="both",
        type="floor_light",
        speed=0,
        start_area=1,
        activity_area=[(0, 1), (0, 5)],
        color=rings(rgb),
        start_time_sec=0.0,
        end_time_sec=10.0,
        direct="right",
        edge_run_into="back",
        move_distance=0.0,
    )


class PhaseAGoalColorPublishTests(unittest.TestCase):
    def load_prepared(self, relative_path):
        groups, game_obj = game_manager._load_level_file(SOURCE / relative_path)
        self.assertTrue(groups, f"failed to load: {relative_path}")
        game_manager.prepare_level_for_platform(groups, game_obj, SETTINGS)
        return groups, game_obj

    def new_session(self, groups, *, multiplayer=False, total_pass=1.0, player_count=None):
        if player_count is None:
            player_count = 2 if multiplayer else 1
        fake_settings = {
            "game_time_sec": 300.0,
            "life_value": 20,
            "life_value_count_time": 1.2,
            "blue_hide_max_time": 20.0,
            "scode_divide_person": False,
            "scode_divide_time": False,
        }
        with mock.patch.object(
            game_manager, "load_real_settings", return_value=fake_settings
        ):
            session = game_manager.GameInstance(
                "phase-a", "card", 1, "normal", player_count
            )
        session.dict_group = groups
        session.led_table = game_manager.HeadlessLedTable(10, 1, 6)
        session.zone = (0, 1, 0, 6)
        session.accepting_input = True
        session.play = SimpleNamespace(total_pass=total_pass)
        session.multiplayer = multiplayer
        return session

    def test_ledb_2p_session_uses_2p_scoring(self):
        ledb = SOURCE / "---" / "DK01.ledb"
        self.assertTrue(ledb.exists())
        self.assertTrue(
            game_manager._level_uses_2p_scoring(str(ledb), 2)
        )
        self.assertFalse(
            game_manager._level_uses_2p_scoring(str(ledb), 1)
        )
        led = SOURCE / "-" / "001.led"
        self.assertFalse(
            game_manager._level_uses_2p_scoring(str(led), 2)
        )

    def test_mp_session_publishes_blue_orange_swatches(self):
        """Full runtime path: .ledb + player_count=2 → goal_color / goal2_color."""
        level_path = SOURCE / "---" / "DK01.ledb"
        fake_settings = {
            "game_time_sec": 300.0,
            "life_value": 20,
            "life_value_count_time": 1.2,
            "blue_hide_max_time": 20.0,
            "scode_divide_person": False,
            "scode_divide_time": False,
            "grid_rows": 1,
            "grid_cols": 6,
            "floor_layout_coors_no_use": [],
            "leval_span": 0.8,
        }

        class FakePlay:
            def __init__(self, led_table, setting, callback, game_level):
                self.obj_led_table = led_table
                self.callback = callback
                self.total_pass = 0
                self.running_state = True

            def running(self, groups):
                # Some .ledb may set play_order=True; both paths must publish.
                self.total_pass = 1.0
                return self.callback(self, groups, 0.01, self.total_pass)

            def running_by_blue(self, groups):
                # DK .ledb typically play_order=False → running_by_blue.
                self.total_pass = 1.0
                return self.callback(self, groups, 0.01, self.total_pass)

        class ImmediateThread:
            def __init__(self, target, daemon):
                self.target = target

            def start(self):
                self.target()

            def join(self, timeout=None):
                pass

            def is_alive(self):
                return False

        with mock.patch.object(
            game_manager, "load_real_settings", return_value=fake_settings
        ):
            session = game_manager.GameInstance(
                "phase-a-mp", "card", 1, "normal", 2
            )
        manager = game_manager.GameManager()
        manager.games[session.game_id] = session

        with (
            mock.patch.object(game_manager, "USE_SERIAL_HD", False),
            mock.patch.object(
                game_manager, "_build_level_sequence", return_value=[level_path]
            ),
            mock.patch.object(
                game_manager, "load_real_settings", return_value=fake_settings
            ),
            mock.patch.object(game_manager, "_hw_blank_floor"),
            mock.patch.object(game_manager.time, "time", return_value=100.0),
            mock.patch.object(game_manager.time, "sleep"),
            mock.patch.object(game_manager.threading, "Thread", ImmediateThread),
            mock.patch("game_play.Play.Play", FakePlay),
        ):
            manager.start_game(session.game_id)

        self.assertTrue(session.multiplayer)
        self.assertEqual(list(session.goal_color), P1_BLUE)
        self.assertEqual(list(session.goal2_color), P2_ORANGE)
        state = session.get_state()
        self.assertTrue(state.get("multiplayer"))
        self.assertEqual(state.get("goal_color"), P1_BLUE)
        self.assertEqual(state.get("goal2_color"), P2_ORANGE)

    def test_1p_led_session_publishes_null_goal_colors(self):
        level_path = SOURCE / "-" / "001.led"
        fake_settings = {
            "game_time_sec": 300.0,
            "life_value": 20,
            "life_value_count_time": 1.2,
            "blue_hide_max_time": 20.0,
            "scode_divide_person": False,
            "scode_divide_time": False,
            "grid_rows": 1,
            "grid_cols": 6,
            "floor_layout_coors_no_use": [],
            "leval_span": 0.8,
        }

        class FakePlay:
            def __init__(self, led_table, setting, callback, game_level):
                self.obj_led_table = led_table
                self.callback = callback
                self.total_pass = 0
                self.running_state = True

            def running(self, groups):
                raise AssertionError("001.led must use running_by_blue")

            def running_by_blue(self, groups):
                self.total_pass = 1.0
                return self.callback(self, groups, 0.01, self.total_pass)

        class ImmediateThread:
            def __init__(self, target, daemon):
                self.target = target

            def start(self):
                self.target()

            def join(self, timeout=None):
                pass

            def is_alive(self):
                return False

        with mock.patch.object(
            game_manager, "load_real_settings", return_value=fake_settings
        ):
            session = game_manager.GameInstance(
                "phase-a-1p", "card", 1, "normal", 1
            )
        manager = game_manager.GameManager()
        manager.games[session.game_id] = session

        with (
            mock.patch.object(game_manager, "USE_SERIAL_HD", False),
            mock.patch.object(
                game_manager, "_build_level_sequence", return_value=[level_path]
            ),
            mock.patch.object(
                game_manager, "load_real_settings", return_value=fake_settings
            ),
            mock.patch.object(game_manager, "_hw_blank_floor"),
            mock.patch.object(game_manager.time, "time", return_value=100.0),
            mock.patch.object(game_manager.time, "sleep"),
            mock.patch.object(game_manager.threading, "Thread", ImmediateThread),
            mock.patch("game_play.Play.Play", FakePlay),
        ):
            manager.start_game(session.game_id)

        self.assertFalse(session.multiplayer)
        self.assertIsNone(session.goal_color)
        self.assertIsNone(session.goal2_color)
        state = session.get_state()
        self.assertFalse(state.get("multiplayer"))
        self.assertIsNone(state.get("goal_color"))
        self.assertIsNone(state.get("goal2_color"))

    def test_mp_red_still_changes_scores_not_lives_only(self):
        """CRITICAL regression: Hoops MP red still deducts score (+ score2) and life."""
        red = controlled_group((254, 0, 0))
        groups = {"red": red}
        game_manager.prepare_level_for_platform(groups, source_game(), SETTINGS)
        session = self.new_session(groups, multiplayer=True)

        session.try_score_cell(0, 5)

        self.assertEqual(session.score, -1)
        self.assertEqual(session.score2, -1)
        self.assertEqual(session.life, session.max_life - 1)

    def test_1p_red_still_penalizes_score_and_life(self):
        hazard_groups, _ = self.load_prepared(Path("-") / "003.led")
        hazard = self.new_session(hazard_groups, multiplayer=False)
        hazard.try_score_cell(0, 5)
        self.assertEqual(hazard.score, -1)
        self.assertEqual(hazard.score2, 0)
        self.assertEqual(hazard.life, hazard.max_life - 1)


if __name__ == "__main__":
    unittest.main()

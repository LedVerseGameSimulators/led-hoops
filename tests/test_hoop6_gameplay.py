import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import api.game_manager as game_manager
from game_play.Play import Play


SETTINGS = {
    "grid_rows": 1,
    "grid_cols": 6,
    "floor_layout_coors_no_use": [],
}
SOURCE = Path(game_manager.GAMES_ROOT) / "source"


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
    )


def controlled_group(rgb, *, start=(0, 4), scale="both", speed=0):
    return SimpleNamespace(
        start_member={start},
        scale=scale,
        type="floor_light",
        speed=speed,
        start_area=1,
        activity_area=[(0, 1), (0, 5)],
        color=rings(rgb),
        start_time_sec=0.0,
        end_time_sec=10.0,
        direct="right",
        edge_run_into="back",
        move_distance=0.0,
    )


class HoopSixGameplayTests(unittest.TestCase):
    def load_prepared(self, relative_path):
        groups, game_obj = game_manager._load_level_file(SOURCE / relative_path)
        self.assertTrue(groups, f"representative archive failed to load: {relative_path}")
        game_manager.prepare_level_for_platform(groups, game_obj, SETTINGS)
        return groups, game_obj

    def new_session(self, groups, *, multiplayer=False, total_pass=1.0):
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
                "test", "card", 1, "normal", 2 if multiplayer else 1
            )
        session.dict_group = groups
        session.led_table = game_manager.HeadlessLedTable(10, 1, 6)
        session.zone = (0, 1, 0, 6)
        session.accepting_input = True
        session.play = SimpleNamespace(total_pass=total_pass)
        session.multiplayer = multiplayer
        return session

    def test_real_level_output_keeps_physical_column_five_and_serializes_one_by_six(self):
        groups, game_obj = game_manager._load_level_file(SOURCE / "-" / "001.led")
        authored = [
            group
            for group in groups.values()
            if (0, 4) in group.start_member
            and group.start_time_sec <= 1.0 <= group.end_time_sec
        ]
        self.assertTrue(authored)

        game_manager.prepare_level_for_platform(groups, game_obj, SETTINGS)
        table = game_manager.HeadlessLedTable(10, 1, 6)
        classified = game_manager._classify_hoops_frame(
            groups, 1.0, table, multiplayer=False
        )
        cell_win, goal_cells, _, _, _, _ = classified
        display = game_manager._build_hoops_led_display(
            cell_win, table, 1.0, {}, now=100.0
        )

        self.assertTrue(all((0, 5) in group.start_member for group in authored))
        self.assertIn((0, 5), goal_cells)
        self.assertEqual((table.led_row, table.led_col), (1, 6))
        self.assertEqual(len(table.led_table), 1)
        self.assertEqual(len(table.led_table[0]), 6)
        self.assertEqual(len(display), 6)
        self.assertNotEqual(display[5], [0, 0, 0])

        driver = mock.Mock()
        hardware_state = SimpleNamespace(_hw_last_draw=0, _hw_draw_count=0)
        table.state_table[0][5] = True
        game_manager._write_hoops_hardware_frame(
            hardware_state, driver, 7, table, display, draw_time=123.0
        )
        layout, hardware_buffer = driver.draw_screen_by_com.call_args.args
        self.assertEqual(layout, 7)
        self.assertEqual((len(hardware_buffer), len(hardware_buffer[0])), (1, 6))
        self.assertEqual(hardware_buffer[0][5], display[5])
        self.assertEqual(hardware_state._hw_last_draw, 123.0)
        self.assertEqual(hardware_state._hw_draw_count, 1)
        driver.update_screen_state_by_com.assert_called_once_with(
            7, table.state_table, table.state_table
        )
        current, previous = driver.update_screen_state_by_com.call_args.args[1:]
        self.assertIs(current, table.state_table)
        self.assertIs(previous, table.state_table)
        self.assertTrue(current[0][5])

    def test_out_of_range_flash_preserves_frame_failure_semantics(self):
        table = game_manager.HeadlessLedTable(10, 1, 6)

        with self.assertRaises(IndexError):
            game_manager._build_hoops_led_display(
                {}, table, 1.0, {(0, 6): 99.9}, now=100.0
            )

    def test_hardware_bookkeeping_occurs_after_draw_before_sensor_failure(self):
        table = game_manager.HeadlessLedTable(10, 1, 6)
        state = SimpleNamespace(_hw_last_draw=0, _hw_draw_count=2)
        events = []

        class FailingDriver:
            def draw_screen_by_com(self, layout, display):
                events.append(("draw", state._hw_last_draw, state._hw_draw_count))

            def update_screen_state_by_com(self, layout, current, previous):
                events.append(("sensor", state._hw_last_draw, state._hw_draw_count))
                raise RuntimeError("sensor failed")

        with self.assertRaisesRegex(RuntimeError, "sensor failed"):
            game_manager._write_hoops_hardware_frame(
                state,
                FailingDriver(),
                7,
                table,
                [[0, 0, 0]] * 6,
                draw_time=123.0,
            )

        self.assertEqual(events, [("draw", 0, 2), ("sensor", 123.0, 3)])
        self.assertEqual((state._hw_last_draw, state._hw_draw_count), (123.0, 3))

    def test_real_runtime_callback_scores_sensor_column_five_on_next_frame(self):
        groups, _ = self.load_prepared(Path("-") / "001.led")
        session = self.new_session(groups)
        session.level = 1
        manager = game_manager.GameManager()
        manager.games[session.game_id] = session
        events = []
        callback_results = []

        class HardwareDriver:
            def draw_screen_by_com(self, layout, display):
                events.append(
                    ("draw", session.score, getattr(session, "_hw_draw_count", 0))
                )
                self_test.assertEqual(layout, 7)
                self_test.assertEqual((len(display), len(display[0])), (1, 6))
                self_test.assertNotEqual(display[0][5], [0, 0, 0])

            def update_screen_state_by_com(self, layout, current, previous):
                events.append(
                    ("sensor", session.score, session._hw_draw_count)
                )
                self_test.assertIs(current, session.led_table.state_table)
                self_test.assertIs(previous, session.led_table.state_table)
                current[0][5] = True

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
                callback_results.append(
                    self.callback(self, groups, 0.01, self.total_pass)
                )
                self_test.assertEqual(session.score, 0)
                self_test.assertTrue(session.led_table.state_table[0][5])

                callback_results.append(
                    self.callback(self, groups, 0.01, self.total_pass)
                )
                self_test.assertEqual(session.score, 1)

        class ImmediateThread:
            def __init__(self, target, daemon):
                self.target = target

            def start(self):
                self.target()

            def join(self, timeout=None):
                pass

            def is_alive(self):
                return False

        runtime_settings = {
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
        driver = HardwareDriver()
        self_test = self
        level_path = SOURCE / "-" / "001.led"
        with (
            mock.patch.object(game_manager, "USE_SERIAL_HD", True),
            mock.patch.object(game_manager, "_hw_led_control", driver),
            mock.patch.object(game_manager, "_hw_layout_type", 7),
            mock.patch.object(game_manager, "_HW_DRAW_INTERVAL", 0),
            mock.patch.object(game_manager, "_hw_init", return_value=driver),
            mock.patch.object(game_manager, "_build_level_sequence", return_value=[level_path]),
            mock.patch.object(game_manager, "load_real_settings", return_value=runtime_settings),
            mock.patch.object(game_manager, "_hw_blank_floor"),
            mock.patch.object(game_manager.time, "time", return_value=100.0),
            mock.patch.object(game_manager.time, "sleep"),
            mock.patch.object(game_manager.threading, "Thread", ImmediateThread),
            mock.patch("game_play.Play.Play", FakePlay),
        ):
            manager.start_game(session.game_id)

        self.assertEqual(callback_results, [True, True])
        self.assertEqual(
            events,
            [
                ("draw", 0, 0),
                ("sensor", 0, 1),
                ("draw", 1, 1),
                ("sensor", 1, 2),
            ],
        )
        self.assertEqual(session.score, 1)
        self.assertIn((0, 5), session.scored_active)
        self.assertIn((0, 5), session.flashes)
        self.assertNotIn((0, 4), session.flashes)

    def test_simulator_input_scores_column_five_once_releases_and_rejects_six(self):
        groups, game_obj = self.load_prepared(Path("-") / "001.led")
        session = self.new_session(groups)
        self.assertEqual(
            (
                game_obj.zone_row_from,
                game_obj.zone_row_to,
                game_obj.zone_col_from,
                game_obj.zone_col_to,
            ),
            (0, 1, 0, 6),
        )

        self.assertTrue(session.apply_input(0, 5, "press"))
        self.assertTrue(session.led_table.state_table[0][5])
        self.assertEqual(session.score, 1)
        self.assertIn((0, 5), session.scored_active)

        self.assertTrue(session.apply_input(0, 5, "press"))
        self.assertEqual(session.score, 1)
        self.assertTrue(session.apply_input(0, 5, "release"))
        self.assertFalse(session.led_table.state_table[0][5])
        self.assertFalse(session.apply_input(0, 6, "press"))
        self.assertEqual(session.score, 1)

    def test_hardware_state_column_five_uses_same_scoring_coordinate(self):
        groups, _ = self.load_prepared(Path("-") / "001.led")
        session = self.new_session(groups)
        session.led_table.state_table[0][5] = True

        game_manager._score_pressed_hoops_cells(session, session.led_table)

        self.assertEqual(session.score, 1)
        self.assertIn((0, 5), session.scored_active)
        self.assertIn((0, 5), session.flashes)
        self.assertNotIn((0, 4), session.flashes)

        game_manager._score_pressed_hoops_cells(session, session.led_table)
        self.assertEqual(session.score, 1)

    def test_real_static_goal_and_red_hazard_apply_at_physical_column_five(self):
        goal_groups, _ = self.load_prepared(Path("-") / "007.led")
        goal = self.new_session(goal_groups)
        goal.try_score_cell(0, 5)
        self.assertEqual(goal.score, 1)
        self.assertIn((0, 5), goal.flashes)

        hazard_groups, _ = self.load_prepared(Path("-") / "003.led")
        hazard = self.new_session(hazard_groups)
        hazard.try_score_cell(0, 5)
        self.assertEqual(hazard.score, -1)
        self.assertEqual(hazard.life, hazard.max_life - 1)
        self.assertEqual(hazard._cell_red_penalty_at.keys(), {(0, 5)})

    def test_deduct_hazard_maps_to_five_penalizes_and_consumes(self):
        deduct = controlled_group((254, 0, 48))
        groups = {"deduct": deduct}
        game_manager.prepare_level_for_platform(groups, source_game(), SETTINGS)
        session = self.new_session(groups)

        session.try_score_cell(0, 5)

        self.assertEqual(session.score, -1)
        self.assertEqual(session.life, session.max_life)
        self.assertNotIn((0, 5), deduct.start_member)
        self.assertIn((0, 5), session.scored_active)

    def test_moving_group_reaches_and_is_consumed_at_physical_column_five(self):
        moving = controlled_group((0, 254, 254), start=(0, 0), speed=1)
        groups = {"moving": moving}
        game_manager.prepare_level_for_platform(groups, source_game(), SETTINGS)
        self.assertEqual(moving.activity_area, [(0, 1), (0, 6)])

        play = Play.__new__(Play)
        for expected_col in range(1, 6):
            moving.direct, moved = play.deal_all_direction(moving)
            moving.start_member = set(moved)
            self.assertIn((0, expected_col), moving.start_member)

        session = self.new_session(groups)
        session.try_score_cell(0, 5)
        self.assertEqual(session.score, 1)
        self.assertNotIn((0, 5), moving.start_member)
        self.assertIn((0, 5), session.flashes)

    def test_real_multiplayer_player_two_owns_scaled_column_five(self):
        groups, _ = self.load_prepared(Path("---") / "DK01.ledb")
        session = self.new_session(groups, multiplayer=True)

        session.try_score_cell(0, 5)

        self.assertEqual((session.score, session.score2), (0, 1))
        self.assertIn((0, 5), session.scored_active2)
        self.assertIn((0, 5), session.flashes)

    def test_real_dk03_player_two_owns_scaled_column_five(self):
        groups, _ = self.load_prepared(Path("---") / "DK03.ledb")
        session = self.new_session(groups, multiplayer=True, total_pass=6.0)

        category = session._live_cell_category(0, 5)
        session.try_score_cell(0, 5)

        self.assertEqual(category, "p2")
        self.assertEqual((session.score, session.score2), (0, 1))
        self.assertIn((0, 5), session.scored_active2)
        self.assertIn((0, 5), session.flashes)

    def test_fresh_reload_recreates_consumed_column_five_without_reuse(self):
        first_groups, _ = self.load_prepared(Path("-") / "001.led")
        first = self.new_session(first_groups)
        first.try_score_cell(0, 5)
        self.assertFalse(
            any(
                (0, 5) in group.start_member
                for group in first_groups.values()
                if group.start_time_sec <= 1.0 <= group.end_time_sec
                and game_manager._group_main_color(group.color)
                in game_manager._HOOPS_COLOR_ARR
            )
        )

        second_groups, second_game = self.load_prepared(Path("-") / "001.led")

        self.assertIsNot(first_groups, second_groups)
        self.assertNotEqual(
            {id(group) for group in first_groups.values()},
            {id(group) for group in second_groups.values()},
        )
        self.assertEqual(second_game.zone_col_to, 6)
        self.assertTrue(
            any(
                (0, 5) in group.start_member
                for group in second_groups.values()
                if group.start_time_sec <= 1.0 <= group.end_time_sec
                and game_manager._group_main_color(group.color)
                in game_manager._HOOPS_COLOR_ARR
            )
        )


if __name__ == "__main__":
    unittest.main()

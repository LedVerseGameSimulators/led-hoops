import unittest
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import api.game_manager as game_manager
from api.level_scaling import LevelScalingError


LEVEL_001 = Path(game_manager.GAMES_ROOT) / "source" / "-" / "001.led"


class LevelPreparationTests(unittest.TestCase):
    def _prepare(self, dict_group, game_obj, settings):
        prepare = getattr(game_manager, "prepare_level_for_platform", None)
        self.assertIsNotNone(prepare, "level preparation boundary is missing")
        return prepare(dict_group, game_obj, settings)

    def test_real_level_is_prepared_in_place_for_configured_platform(self):
        dict_group, game_obj = game_manager._load_level_file(LEVEL_001)
        self.assertTrue(dict_group)

        prepared_group, prepared_game = self._prepare(
            dict_group,
            game_obj,
            {"grid_rows": 1, "grid_cols": 6, "floor_layout_coors_no_use": []},
        )

        self.assertIs(prepared_group, dict_group)
        self.assertIs(prepared_game, game_obj)
        self.assertEqual(
            (
                game_obj.zone_row_from,
                game_obj.zone_row_to,
                game_obj.zone_col_from,
                game_obj.zone_col_to,
            ),
            (0, 1, 0, 6),
        )
        occupied = {
            tuple(cell)
            for group in dict_group.values()
            if float(getattr(group, "speed", -1)) == 0
            for cell in group.start_member
        }
        self.assertEqual(occupied, {(0, col) for col in range(6)})

    def test_fresh_reload_can_be_prepared_but_same_objects_cannot(self):
        settings = {
            "grid_rows": 1,
            "grid_cols": 6,
            "floor_layout_coors_no_use": [],
        }
        first_group, first_game = game_manager._load_level_file(LEVEL_001)
        second_group, second_game = game_manager._load_level_file(LEVEL_001)

        self._prepare(first_group, first_game, settings)
        with self.assertRaisesRegex(LevelScalingError, "already scaled"):
            self._prepare(first_group, first_game, settings)

        self._prepare(second_group, second_game, settings)
        self.assertEqual(second_game.zone_col_to, 6)

    def test_no_use_coordinates_are_rejected_for_six_hoop_platform(self):
        dict_group, game_obj = game_manager._load_level_file(LEVEL_001)

        with self.assertRaisesRegex(ValueError, "Hoops hardware"):
            self._prepare(
                dict_group,
                game_obj,
                {
                    "grid_rows": 1,
                    "grid_cols": 6,
                    "floor_layout_coors_no_use": [(0, 3)],
                },
            )

    def test_invalid_configured_dimensions_are_rejected(self):
        for rows, cols in ((0, 6), (1.5, 6), (True, 6), (1, 5), (1, 7)):
            with self.subTest(rows=rows, cols=cols):
                dict_group, game_obj = game_manager._load_level_file(LEVEL_001)
                with self.assertRaisesRegex(ValueError, "Hoops hardware"):
                    self._prepare(
                        dict_group,
                        game_obj,
                        {
                            "grid_rows": rows,
                            "grid_cols": cols,
                            "floor_layout_coors_no_use": [],
                        },
                    )


class SettingsTests(unittest.TestCase):
    def tearDown(self):
        game_manager._settings_cache = None

    def test_load_real_settings_retains_floor_layout_no_use(self):
        class FakeShelf(dict):
            def close(self):
                pass

        led_settings = FakeShelf(
            value_high="1",
            value_width="6",
            floor_layout_coors_no_use=[(0, 3)],
        )
        debug_settings = FakeShelf()

        def open_shelf(path, flag):
            return led_settings if path == game_manager._LED_PARAM else debug_settings

        game_manager._settings_cache = None
        with mock.patch.object(game_manager._shelve, "open", side_effect=open_shelf):
            settings = game_manager.load_real_settings()

        self.assertEqual(settings["grid_rows"], 1)
        self.assertEqual(settings["grid_cols"], 6)
        self.assertIn("floor_layout_coors_no_use", settings)
        self.assertEqual(settings["floor_layout_coors_no_use"], [(0, 3)])

    def test_load_real_settings_preserves_present_invalid_platform_values(self):
        class FakeShelf(dict):
            def close(self):
                pass

        led_settings = FakeShelf(
            value_high="1.5",
            value_width=True,
            floor_layout_coors_no_use="invalid-no-use",
        )
        debug_settings = FakeShelf()

        def open_shelf(path, flag):
            return led_settings if path == game_manager._LED_PARAM else debug_settings

        with mock.patch.object(game_manager._shelve, "open", side_effect=open_shelf):
            settings = game_manager.load_real_settings()

        self.assertEqual(settings["grid_rows"], "1.5")
        self.assertIs(settings["grid_cols"], True)
        self.assertEqual(
            settings["floor_layout_coors_no_use"],
            "invalid-no-use",
        )


class HeadlessLedTableStateTests(unittest.TestCase):
    def test_clear_input_state_clears_same_and_changed_size_aliases(self):
        for target_rows, target_cols in ((1, 6), (2, 4)):
            with self.subTest(target=(target_rows, target_cols)):
                table = game_manager.HeadlessLedTable(10, 1, 6)
                table.press_cell(0, 3)
                table.resize(target_rows, target_cols)

                clear = getattr(table, "clear_input_state", None)
                self.assertIsNotNone(clear, "input-state clear boundary is missing")
                clear()

                self.assertIs(table._state_table, table.state_table)
                self.assertIs(table._state_table, table.table_state)
                self.assertFalse(any(any(row) for row in table._state_table))


class LifecycleOrderingTests(unittest.TestCase):
    SETTINGS = {
        "grid_rows": 1,
        "grid_cols": 6,
        "floor_layout_coors_no_use": [],
    }

    def _helper(self):
        helper = getattr(game_manager, "_run_level_attempt", None)
        self.assertIsNotNone(helper, "full level-attempt boundary is missing")
        return helper

    def test_attempt_orders_load_reset_scale_setup_then_selected_play_once(self):
        for play_order, selected in ((True, "running"), (False, "running_by_blue")):
            with self.subTest(play_order=play_order):
                events = []
                dict_group = {"group": SimpleNamespace()}
                game_obj = SimpleNamespace()

                class Session:
                    _play_order = play_order
                    input_lock = threading.Lock()
                    accepting_input = True
                    _input_epoch = 0

                    def reset_for_level(self):
                        events.append("reset")

                class Play:
                    running_state = False
                    total_pass = None

                    def running(self, dg):
                        events.append("running")
                        self.assert_prepared(dg)

                    def running_by_blue(self, dg):
                        events.append("running_by_blue")
                        self.assert_prepared(dg)

                    def assert_prepared(self, dg):
                        self_test.assertIs(dg, dict_group)

                self_test = self

                def loader(path):
                    events.append("load")
                    return dict_group, game_obj

                def scaler(go, dg, rows, cols, no_use):
                    events.append("scale")
                    self.assertIs(go, game_obj)
                    self.assertIs(dg, dict_group)
                    self.assertEqual((rows, cols, no_use), (1, 6, []))
                    return go, dg

                def setup(dg, go, path):
                    events.append("setup")
                    self.assertIs(dg, dict_group)
                    self.assertIs(go, game_obj)

                play = Play()
                with mock.patch.object(
                    game_manager, "scale_level_to_platform", side_effect=scaler
                ) as scale:
                    result = self._helper()(
                        "001.led",
                        Session(),
                        self.SETTINGS,
                        setup,
                        play,
                        loader=loader,
                    )

                self.assertEqual(
                    events, ["load", "reset", "scale", "setup", selected]
                )
                self.assertEqual(scale.call_count, 1)
                self.assertEqual(result, (dict_group, game_obj))
                self.assertTrue(play.running_state)
                self.assertEqual(play.total_pass, 0)

    def test_fresh_attempts_scale_and_play_once_for_restart_and_progression(self):
        loaded = []
        scaled = []
        played = []

        class Session:
            _play_order = False
            input_lock = threading.Lock()
            accepting_input = True
            _input_epoch = 0

            def reset_for_level(self):
                pass

        class Play:
            running_state = False
            total_pass = None

            def running_by_blue(self, dg):
                played.append(dg)

        def loader(path):
            fresh = ({"group": SimpleNamespace(path=path)}, SimpleNamespace(path=path))
            loaded.append(fresh)
            return fresh

        def scaler(go, dg, rows, cols, no_use):
            scaled.append((dg, go))
            return go, dg

        def setup(dg, go, path):
            self.assertEqual((next(iter(dg.values())).path, go.path), (path, path))

        helper = self._helper()
        play = Play()
        session = Session()
        with mock.patch.object(
            game_manager, "scale_level_to_platform", side_effect=scaler
        ) as scale:
            for path in ("001.led", "001.led", "002.led"):
                helper(
                    path,
                    session,
                    self.SETTINGS,
                    setup,
                    play,
                    loader=loader,
                )

        self.assertEqual(scale.call_count, 3)
        self.assertEqual(len(played), 3)
        self.assertEqual([dg for dg, _ in loaded], played)
        self.assertEqual(len({id(dg) for dg, _ in scaled}), 3)
        self.assertEqual(len({id(go) for _, go in scaled}), 3)

    def test_preparation_failure_does_not_run_setup(self):
        helper = self._helper()
        setup = mock.Mock()
        play = SimpleNamespace(running=mock.Mock(), running_by_blue=mock.Mock())
        session = SimpleNamespace(
            reset_for_level=mock.Mock(),
            update_state=mock.Mock(),
            _session_over=False,
            _end_reason=None,
            input_lock=threading.Lock(),
            accepting_input=True,
            _input_epoch=0,
        )

        with mock.patch.object(
            game_manager,
            "scale_level_to_platform",
            side_effect=LevelScalingError("bad platform"),
        ):
            result = helper(
                "bad.led",
                session,
                self.SETTINGS,
                setup,
                play,
                loader=lambda path: ({"group": object()}, SimpleNamespace()),
            )

        self.assertIsNone(result)
        session.reset_for_level.assert_called_once_with()
        setup.assert_not_called()
        play.running.assert_not_called()
        play.running_by_blue.assert_not_called()
        self.assertTrue(session._session_over)
        self.assertEqual(session._end_reason, "level_error")
        session.update_state.assert_called_once_with(
            game_over_reason="level_error", result=0
        )

    def test_load_failure_aborts_session_before_reset_setup_or_play(self):
        session = SimpleNamespace(
            reset_for_level=mock.Mock(),
            update_state=mock.Mock(),
            _session_over=False,
            _end_reason=None,
            input_lock=threading.Lock(),
            accepting_input=True,
            _input_epoch=0,
        )
        setup = mock.Mock()
        play = SimpleNamespace(running=mock.Mock(), running_by_blue=mock.Mock())

        result = self._helper()(
            "missing.led",
            session,
            self.SETTINGS,
            setup,
            play,
            loader=lambda path: (None, None),
        )

        self.assertIsNone(result)
        session.reset_for_level.assert_not_called()
        setup.assert_not_called()
        play.running.assert_not_called()
        play.running_by_blue.assert_not_called()
        self.assertTrue(session._session_over)
        self.assertEqual(session._end_reason, "level_error")
        session.update_state.assert_called_once_with(
            game_over_reason="level_error", result=0
        )

    def test_setup_exception_marks_level_error_before_propagating(self):
        session = SimpleNamespace(
            reset_for_level=mock.Mock(),
            update_state=mock.Mock(),
            _session_over=False,
            _end_reason=None,
            _play_order=False,
            input_lock=threading.Lock(),
            accepting_input=True,
            _input_epoch=0,
        )
        setup = mock.Mock(side_effect=RuntimeError("setup exploded"))
        play = SimpleNamespace(running=mock.Mock(), running_by_blue=mock.Mock())

        with mock.patch.object(
            game_manager, "scale_level_to_platform", return_value=(object(), object())
        ):
            with self.assertRaisesRegex(RuntimeError, "setup exploded"):
                self._helper()(
                    "001.led",
                    session,
                    self.SETTINGS,
                    setup,
                    play,
                    loader=lambda path: ({"group": object()}, SimpleNamespace()),
                )

        play.running.assert_not_called()
        play.running_by_blue.assert_not_called()
        self.assertTrue(session._session_over)
        self.assertEqual(session._end_reason, "level_error")
        session.update_state.assert_called_once_with(
            game_over_reason="level_error", result=0
        )

    def test_selected_play_exception_marks_level_error_before_propagating(self):
        for play_order, selected in ((True, "running"), (False, "running_by_blue")):
            with self.subTest(play_order=play_order):
                session = SimpleNamespace(
                    reset_for_level=mock.Mock(),
                    update_state=mock.Mock(),
                    _session_over=False,
                    _end_reason=None,
                    _play_order=play_order,
                    input_lock=threading.Lock(),
                    accepting_input=True,
                    _input_epoch=0,
                )
                setup = mock.Mock()
                play = SimpleNamespace(
                    running=mock.Mock(),
                    running_by_blue=mock.Mock(),
                    running_state=False,
                    total_pass=None,
                )
                getattr(play, selected).side_effect = RuntimeError(
                    f"{selected} exploded"
                )

                with mock.patch.object(
                    game_manager,
                    "scale_level_to_platform",
                    return_value=(object(), object()),
                ):
                    with self.assertRaisesRegex(RuntimeError, f"{selected} exploded"):
                        self._helper()(
                            "001.led",
                            session,
                            self.SETTINGS,
                            setup,
                            play,
                            loader=lambda path: (
                                {"group": object()},
                                SimpleNamespace(),
                            ),
                        )

                getattr(play, selected).assert_called_once()
                other = "running_by_blue" if selected == "running" else "running"
                getattr(play, other).assert_not_called()
                self.assertTrue(session._session_over)
                self.assertEqual(session._end_reason, "level_error")
                session.update_state.assert_called_once_with(
                    game_over_reason="level_error", result=0
                )

    def test_frame_callback_exception_logs_marks_level_error_and_stops(self):
        handler = getattr(game_manager, "_handle_frame_callback_error", None)
        self.assertIsNotNone(handler, "frame callback failure boundary is missing")
        session = SimpleNamespace(
            update_state=mock.Mock(),
            _session_over=False,
            _end_reason=None,
        )
        error = RuntimeError("frame exploded")

        with mock.patch.object(game_manager.logger, "error") as log_error:
            result = handler(session, "game-123", error)

        self.assertFalse(result)
        self.assertTrue(session._session_over)
        self.assertEqual(session._end_reason, "level_error")
        session.update_state.assert_called_once_with(
            game_over_reason="level_error", result=0
        )
        log_error.assert_called_once()
        self.assertIn("Frame callback error game-123: frame exploded", log_error.call_args.args[0])

    def test_loader_and_reset_exceptions_mark_failure_and_leave_input_disabled(self):
        for failing_stage in ("loader", "reset"):
            with self.subTest(failing_stage=failing_stage):
                reset = mock.Mock()
                if failing_stage == "reset":
                    reset.side_effect = RuntimeError("reset exploded")
                session = SimpleNamespace(
                    reset_for_level=reset,
                    update_state=mock.Mock(),
                    _session_over=False,
                    _end_reason=None,
                    _play_order=False,
                    input_lock=threading.Lock(),
                    accepting_input=True,
                    _input_epoch=0,
                    dict_group={"stale": object()},
                    zone=(0, 1, 0, 6),
                )

                def loader(path):
                    if failing_stage == "loader":
                        raise RuntimeError("loader exploded")
                    return {"group": object()}, SimpleNamespace()

                with self.assertRaisesRegex(RuntimeError, f"{failing_stage} exploded"):
                    self._helper()(
                        "001.led",
                        session,
                        self.SETTINGS,
                        mock.Mock(),
                        SimpleNamespace(running=mock.Mock(), running_by_blue=mock.Mock()),
                        loader=loader,
                    )

                self.assertFalse(session.accepting_input)
                self.assertIsNone(session.dict_group)
                self.assertIsNone(session.zone)
                self.assertTrue(session._session_over)
                self.assertEqual(session._end_reason, "level_error")
                session.update_state.assert_called_once_with(
                    game_over_reason="level_error", result=0
                )

    def test_attempt_synchronizes_transition_then_enables_before_play(self):
        class ProbeLock:
            def __init__(self):
                self.lock = threading.Lock()
                self.held = False

            def __enter__(self):
                self.lock.acquire()
                self.held = True
                return self

            def __exit__(self, *args):
                self.held = False
                self.lock.release()

        probe = ProbeLock()
        events = []
        session = SimpleNamespace(
            input_lock=probe,
            accepting_input=True,
            _input_epoch=0,
            _play_order=False,
            _session_over=False,
            _end_reason=None,
            update_state=mock.Mock(),
            dict_group={"stale": object()},
            zone=(0, 1, 0, 6),
        )

        def assert_transition(stage):
            self.assertTrue(probe.held)
            self.assertFalse(session.accepting_input)
            events.append(stage)

        def loader(path):
            assert_transition("load")
            return {"group": object()}, SimpleNamespace()

        def reset():
            assert_transition("reset")

        session.reset_for_level = reset

        def scaler(*args):
            assert_transition("scale")

        def setup(*args):
            assert_transition("setup")

        def play(dg):
            self.assertFalse(probe.held)
            self.assertTrue(session.accepting_input)
            events.append("play")

        with mock.patch.object(
            game_manager, "scale_level_to_platform", side_effect=scaler
        ):
            self._helper()(
                "001.led",
                session,
                self.SETTINGS,
                setup,
                SimpleNamespace(
                    running=mock.Mock(),
                    running_by_blue=play,
                    running_state=False,
                    total_pass=None,
                ),
                loader=loader,
            )

        self.assertEqual(events, ["load", "reset", "scale", "setup", "play"])

    def test_apply_input_rejects_request_waiting_across_transition(self):
        class GateLock:
            def __init__(self):
                self.lock = threading.Lock()
                self.entered = threading.Event()

            def __enter__(self):
                self.entered.set()
                self.lock.acquire()

            def __exit__(self, *args):
                self.lock.release()

        gate = GateLock()
        led_table = SimpleNamespace(press_cell=mock.Mock(), release_cell=mock.Mock())
        game = SimpleNamespace(
            input_lock=gate,
            accepting_input=False,
            _input_epoch=1,
            led_table=led_table,
            zone=(0, 1, 0, 6),
            try_score_cell=mock.Mock(),
        )
        result = []

        gate.lock.acquire()
        try:
            thread = threading.Thread(
                target=lambda: result.append(
                    game_manager.GameInstance.apply_input(game, 0, 5, "press")
                )
            )
            thread.start()
            self.assertTrue(gate.entered.wait(timeout=1))
            game.accepting_input = True
            game._input_epoch = 2
        finally:
            gate.lock.release()
        thread.join(timeout=1)

        self.assertEqual(result, [False])
        led_table.press_cell.assert_not_called()
        game.try_score_cell.assert_not_called()

    def test_apply_input_checks_board_and_scores_under_lock(self):
        class ProbeLock:
            held = False

            def __enter__(self):
                self.held = True

            def __exit__(self, *args):
                self.held = False

        lock = ProbeLock()

        class InputGame:
            input_lock = lock
            accepting_input = True
            _input_epoch = 4

            @property
            def led_table(self):
                self_test.assertTrue(lock.held)
                return SimpleNamespace(press_cell=lambda row, col: None)

            @property
            def zone(self):
                self_test.assertTrue(lock.held)
                return (0, 1, 0, 6)

            def try_score_cell(self, row, col):
                self_test.assertTrue(lock.held)

        self_test = self
        self.assertTrue(
            game_manager.GameInstance.apply_input(InputGame(), 0, 5, "press")
        )

    def test_final_outcome_and_session_markers_are_stable_non_successes(self):
        resolve = getattr(game_manager, "_resolve_session_outcome", None)
        mark = getattr(game_manager, "_mark_session_error", None)
        self.assertIsNotNone(resolve, "final session outcome helper is missing")
        self.assertIsNotNone(mark, "session error marker is missing")

        for reason in ("no_levels", "game_error"):
            with self.subTest(reason=reason):
                session = SimpleNamespace(
                    input_lock=threading.Lock(),
                    accepting_input=True,
                    _input_epoch=0,
                    _session_over=False,
                    _end_reason=None,
                    update_state=mock.Mock(),
                    get_state=lambda: {"result": None, "game_over_reason": ""},
                )
                mark(session, reason)
                self.assertEqual(resolve(session), (0, reason))
                self.assertFalse(session.accepting_input)
                session.update_state.assert_called_once_with(
                    game_over_reason=reason, result=0
                )

    def test_transition_clears_stuck_press_before_play(self):
        table = game_manager.HeadlessLedTable(10, 1, 6)
        table.press_cell(0, 5)
        session = SimpleNamespace(
            input_lock=threading.Lock(),
            accepting_input=True,
            _input_epoch=0,
            _play_order=False,
            _session_over=False,
            _end_reason=None,
            update_state=mock.Mock(),
            reset_for_level=mock.Mock(),
            dict_group={"stale": object()},
            zone=(0, 1, 0, 6),
            led_table=table,
        )

        def setup(*args):
            table.resize(1, 6)

        def play(dg):
            self.assertFalse(any(any(row) for row in table.state_table))
            self.assertIs(table._state_table, table.state_table)
            self.assertIs(table._state_table, table.table_state)

        with mock.patch.object(game_manager, "scale_level_to_platform"):
            self._helper()(
                "001.led",
                session,
                self.SETTINGS,
                setup,
                SimpleNamespace(
                    running=mock.Mock(),
                    running_by_blue=play,
                    running_state=False,
                    total_pass=None,
                ),
                loader=lambda path: ({"group": object()}, SimpleNamespace()),
            )

    def test_stopped_outcome_is_failure_and_clean_exhaustion_is_success(self):
        stopped = getattr(game_manager, "_handle_stopped_session", None)
        self.assertIsNotNone(stopped, "stopped-session boundary is missing")
        session = SimpleNamespace(
            input_lock=threading.Lock(),
            accepting_input=True,
            _input_epoch=0,
            _session_over=False,
            _end_reason=None,
            update_state=mock.Mock(),
            get_state=lambda: {"result": None, "game_over_reason": ""},
        )

        self.assertFalse(stopped(session))
        self.assertEqual(game_manager._resolve_session_outcome(session), (0, "stopped"))
        session.update_state.assert_called_once_with(
            game_over_reason="stopped", result=0
        )

        completed = SimpleNamespace(
            _end_reason=None,
            get_state=lambda: {"result": None, "game_over_reason": ""},
        )
        self.assertEqual(
            game_manager._resolve_session_outcome(completed),
            (1, "session_end"),
        )


if __name__ == "__main__":
    unittest.main()

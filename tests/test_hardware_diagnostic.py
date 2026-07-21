import io
import unittest
from unittest import mock

from games import test_hardware
from games.led import led_control as real_led_control


class FakeTime:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.now += duration


class JumpingTime:
    def __init__(self, readings):
        self.readings = iter(readings)
        self.last = readings[-1]
        self.sleeps = []

    def monotonic(self):
        try:
            self.last = next(self.readings)
        except StopIteration:
            pass
        return self.last

    def sleep(self, duration):
        if duration <= 0:
            raise AssertionError(f"invalid sleep duration: {duration}")
        self.sleeps.append(duration)


class FakeDriver:
    def __init__(self, frames=(), init_errors=()):
        self.frames = iter(frames)
        self.init_errors = list(init_errors)
        self.g_has_open = not self.init_errors
        self.draws = []
        self.updates = 0
        self.closed = False
        self.layout = None

    def init_layout(self, layout_type, rows, cols, no_use):
        self.layout = (layout_type, rows, cols, list(no_use))

    def init_com(self, com_info):
        return self.init_errors

    def draw_screen_by_com(self, layout_type, buffer):
        self.draws.append(
            (layout_type, [[list(color) for color in row] for row in buffer])
        )

    def update_screen_state_by_com(self, layout_type, current, previous):
        self.updates += 1
        try:
            frame = next(self.frames)
        except StopIteration:
            return
        if frame is None:
            return
        current[0][:] = frame

    def close_com(self):
        self.closed = True


class ConfigValidationTests(unittest.TestCase):
    def test_accepts_exactly_one_by_six_and_rejects_other_dimensions(self):
        test_hardware.validate_hardware_config(1, 6, [])
        for dimensions in ((2, 6), (1, 5), (1, 7), (0, 6)):
            with self.subTest(dimensions=dimensions):
                with self.assertRaisesRegex(
                    test_hardware.DiagnosticConfigError, "exactly 1x6"
                ):
                    test_hardware.validate_hardware_config(*dimensions, [])

    def test_rejects_disabled_sixth_hoop(self):
        with self.assertRaisesRegex(
            test_hardware.DiagnosticConfigError, r"\(0, 5\).*disabled"
        ):
            test_hardware.validate_hardware_config(1, 6, [(0, 5)])

    def test_dimension_parser_accepts_only_finite_positive_integer_values(self):
        for value, expected in ((1, 1), (1.0, 1), ("1", 1), ("6.0", 6)):
            with self.subTest(value=value):
                self.assertEqual(
                    test_hardware.parse_dimension(value, "grid_rows"), expected
                )

        for value in (1.5, 6.9, "1.5", float("nan"), float("inf"), True, "six", 0, -1):
            with self.subTest(value=value):
                with self.assertRaises(test_hardware.DiagnosticConfigError):
                    test_hardware.parse_dimension(value, "grid_rows")

    def test_load_rejects_fractional_dimensions_and_closes_shelf(self):
        class FakeShelf(dict):
            closed = False

            def close(self):
                self.closed = True

        shelf = FakeShelf(
            list_com_info=[["serial", 1, 6]],
            led_layout_type=3,
            floor_layout_coors_no_use=[],
            value_high="1.5",
            value_width="6",
        )

        with mock.patch.object(test_hardware.shelve, "open", return_value=shelf):
            with self.assertRaisesRegex(
                test_hardware.DiagnosticConfigError, "value_high"
            ):
                test_hardware.load_hardware_config("unused")

        self.assertTrue(shelf.closed)


class OutputMatrixTests(unittest.TestCase):
    def test_rejects_nonfinite_output_timings_before_driver_calls(self):
        for argument in ("phase_duration", "repeat_interval"):
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(argument=argument, value=value):
                    driver = FakeDriver()
                    kwargs = {
                        "phase_duration": 0,
                        "repeat_interval": 0.05,
                        argument: value,
                    }
                    with self.assertRaises(ValueError):
                        test_hardware.run_output_matrix(
                            driver,
                            layout_type=3,
                            monotonic=mock.Mock(
                                side_effect=AssertionError("clock must not run")
                            ),
                            sleep=mock.Mock(),
                            output=io.StringIO(),
                            **kwargs,
                        )
                    self.assertEqual(driver.draws, [])

    def test_sends_six_unambiguous_per_column_buffers(self):
        driver = FakeDriver()
        clock = FakeTime()

        test_hardware.run_output_matrix(
            driver,
            layout_type=3,
            phase_duration=0,
            repeat_interval=0.05,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            output=io.StringIO(),
            confirm=lambda _prompt: True,
        )

        self.assertEqual(len(driver.draws), 7)
        all_columns = driver.draws[0][1]
        self.assertEqual(len({tuple(color) for color in all_columns[0]}), 6)
        for column, (_, buffer) in enumerate(driver.draws[1:]):
            lit = [index for index, color in enumerate(buffer[0]) if any(color)]
            self.assertEqual(lit, [column])

    def test_requires_confirmation_for_all_seven_phases_and_continues_after_failure(self):
        driver = FakeDriver()
        clock = FakeTime()
        output = io.StringIO()
        prompts = []
        answers = iter((True, False, True, True, True, True, True))

        result = test_hardware.run_output_matrix(
            driver,
            layout_type=3,
            phase_duration=0,
            repeat_interval=0.05,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            output=output,
            confirm=lambda prompt: prompts.append(prompt) or next(answers),
        )

        self.assertFalse(result)
        self.assertEqual(len(driver.draws), 7)
        self.assertEqual(len(prompts), 7)
        self.assertIn("all six", prompts[0].lower())
        for column in range(6):
            self.assertIn(f"column {column}", prompts[column + 1].lower())
        self.assertEqual(output.getvalue().count("OUTPUT MANUAL PASS"), 6)
        self.assertEqual(output.getvalue().count("OUTPUT MANUAL FAIL"), 1)

    def test_default_confirmation_treats_yes_only_as_pass_and_eof_as_fail(self):
        for answer, expected in (
            ("yes", True),
            ("Y", True),
            ("", False),
            ("no", False),
        ):
            with self.subTest(answer=answer):
                with mock.patch("builtins.input", return_value=answer):
                    self.assertEqual(
                        test_hardware.confirm_output_phase("confirm?"),
                        expected,
                    )
        with mock.patch("builtins.input", side_effect=EOFError):
            self.assertFalse(test_hardware.confirm_output_phase("confirm?"))

    def test_send_phase_does_not_sleep_after_monotonic_jump_past_deadline(self):
        driver = FakeDriver()
        clock = JumpingTime([0.0, 0.1, 2.0])

        test_hardware._send_phase(
            driver,
            layout_type=3,
            pattern=test_hardware.all_columns_pattern(),
            duration=1.0,
            repeat_interval=0.05,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )

        self.assertEqual(len(driver.draws), 2)
        self.assertEqual(clock.sleeps, [0.05])


class InputMatrixTests(unittest.TestCase):
    def test_rejects_nonfinite_input_timings_before_driver_calls(self):
        for argument in ("duration", "poll_interval"):
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(argument=argument, value=value):
                    driver = FakeDriver()
                    kwargs = {"duration": 0, "poll_interval": 0.01, argument: value}
                    with self.assertRaises(ValueError):
                        test_hardware.run_input_matrix(
                            driver,
                            layout_type=3,
                            monotonic=mock.Mock(
                                side_effect=AssertionError("clock must not run")
                            ),
                            sleep=mock.Mock(),
                            output=io.StringIO(),
                            **kwargs,
                        )
                    self.assertEqual(driver.updates, 0)

    def test_reports_press_and_release_edges_without_repeating_held_press(self):
        driver = FakeDriver(
            frames=[
                [False, False, False, False, False, False],
                [True, False, False, False, False, False],
                [True, False, False, False, False, False],
                [False, False, False, False, False, False],
            ]
        )
        clock = FakeTime()
        output = io.StringIO()

        result = test_hardware.run_input_matrix(
            driver,
            layout_type=3,
            duration=0.04,
            poll_interval=0.01,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            output=output,
        )

        self.assertFalse(result)
        self.assertEqual(output.getvalue().count("PRESS (0,0)"), 1)
        self.assertEqual(output.getvalue().count("RELEASE (0,0)"), 1)

    def test_complete_and_incomplete_input_matrices_set_exit_result(self):
        complete_frames = [[False] * 6]
        for column in range(6):
            pressed = [False] * 6
            pressed[column] = True
            complete_frames.extend((pressed, [False] * 6))

        for frames, expected in (
            (complete_frames, True),
            (complete_frames[:-2], False),
        ):
            with self.subTest(expected=expected):
                driver = FakeDriver(frames=frames)
                clock = FakeTime()
                result = test_hardware.run_input_matrix(
                    driver,
                    layout_type=3,
                    duration=len(frames) * 0.01,
                    poll_interval=0.01,
                    monotonic=clock.monotonic,
                    sleep=clock.sleep,
                    output=io.StringIO(),
                )
                self.assertEqual(result, expected)

    def test_permanently_stuck_high_column_remains_missing(self):
        frames = [[True, False, False, False, False, False]] * 3
        driver = FakeDriver(frames=frames)
        clock = FakeTime()
        output = io.StringIO()

        result = test_hardware.run_input_matrix(
            driver,
            layout_type=3,
            duration=len(frames) * 0.01,
            poll_interval=0.01,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            output=output,
        )

        self.assertFalse(result)
        self.assertIn("(0, 0): MISSING", output.getvalue())
        self.assertNotIn("PRESS (0,0)", output.getvalue())

    def test_no_data_then_held_release_requires_a_new_complete_cycle(self):
        held = [True, False, False, False, False, False]
        released = [False] * 6
        cases = (
            ([None, held, released], "MISSING"),
            ([None, held, released, held, released], "PASS"),
        )
        for frames, expected in cases:
            with self.subTest(expected=expected):
                driver = FakeDriver(frames=frames)
                clock = FakeTime()
                output = io.StringIO()

                test_hardware.run_input_matrix(
                    driver,
                    layout_type=3,
                    duration=len(frames) * 0.01,
                    poll_interval=0.01,
                    monotonic=clock.monotonic,
                    sleep=clock.sleep,
                    output=output,
                )

                self.assertIn(f"(0, 0): {expected}", output.getvalue())
                expected_presses = 0 if expected == "MISSING" else 1
                self.assertEqual(
                    output.getvalue().count("PRESS (0,0)"), expected_presses
                )

    def test_real_driver_read_preserves_unknown_then_replaces_it_with_frame(self):
        class FakeSerial:
            def __init__(self, payload):
                self.payload = bytearray(payload)
                self.in_waiting = len(self.payload)

            def read_all(self):
                payload = self.payload
                self.payload = bytearray()
                self.in_waiting = 0
                return payload

        state = [[None] * 6]
        coordinates = [(0, column) for column in range(6)]
        with mock.patch.object(real_led_control, "rect_position_arr", coordinates):
            real_led_control.read(FakeSerial([]), state, 0, read_size=6)
            self.assertEqual(state, [[None] * 6])

            packet = [0, 0, 0, 0, 0, 10, 252, 0]
            real_led_control.read(FakeSerial(packet), state, 0, read_size=6)

        self.assertEqual(state, [[True, False, False, False, False, False]])

    def test_initially_held_column_passes_only_after_new_complete_cycle(self):
        frames = [
            [True, False, False, False, False, False],
            [False, False, False, False, False, False],
            [True, False, False, False, False, False],
            [False, False, False, False, False, False],
        ]
        driver = FakeDriver(frames=frames)
        clock = FakeTime()
        output = io.StringIO()

        test_hardware.run_input_matrix(
            driver,
            layout_type=3,
            duration=len(frames) * 0.01,
            poll_interval=0.01,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            output=output,
        )

        self.assertIn("(0, 0): PASS", output.getvalue())
        self.assertEqual(output.getvalue().count("PRESS (0,0)"), 1)
        self.assertEqual(output.getvalue().count("RELEASE (0,0)"), 2)

    def test_press_without_release_remains_missing(self):
        frames = [
            [False, False, False, False, False, False],
            [True, False, False, False, False, False],
            [True, False, False, False, False, False],
        ]
        driver = FakeDriver(frames=frames)
        clock = FakeTime()
        output = io.StringIO()

        test_hardware.run_input_matrix(
            driver,
            layout_type=3,
            duration=len(frames) * 0.01,
            poll_interval=0.01,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            output=output,
        )

        self.assertIn("(0, 0): MISSING", output.getvalue())
        self.assertEqual(output.getvalue().count("PRESS (0,0)"), 1)
        self.assertNotIn("RELEASE (0,0)", output.getvalue())

    def test_all_six_complete_post_baseline_cycles_pass(self):
        frames = [[False] * 6]
        for column in range(6):
            pressed = [False] * 6
            pressed[column] = True
            frames.extend((pressed, [False] * 6))
        driver = FakeDriver(frames=frames)
        clock = FakeTime()
        output = io.StringIO()

        result = test_hardware.run_input_matrix(
            driver,
            layout_type=3,
            duration=len(frames) * 0.01,
            poll_interval=0.01,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            output=output,
        )

        self.assertTrue(result)
        for column in range(6):
            self.assertIn(f"(0, {column}): PASS", output.getvalue())

    def test_input_loop_does_not_sleep_after_monotonic_jump_past_deadline(self):
        driver = FakeDriver(frames=[[False] * 6])
        clock = JumpingTime([0.0, 0.1, 2.0])

        test_hardware.run_input_matrix(
            driver,
            layout_type=3,
            duration=1.0,
            poll_interval=0.01,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            output=io.StringIO(),
        )

        self.assertEqual(clock.sleeps, [0.01])

    def test_nonzero_numeric_sensor_values_create_one_press_edge(self):
        driver = FakeDriver(
            frames=[
                [0, 0, 0, 0, 0, 0],
                [1, 0, 0, 0, 0, 255],
                [255, 0, 0, 0, 0, 1],
                [0, 0, 0, 0, 0, 0],
            ]
        )
        clock = FakeTime()
        output = io.StringIO()

        test_hardware.run_input_matrix(
            driver,
            layout_type=3,
            duration=0.04,
            poll_interval=0.01,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            output=output,
        )

        self.assertEqual(output.getvalue().count("PRESS (0,0)"), 1)
        self.assertEqual(output.getvalue().count("PRESS (0,5)"), 1)


class LifecycleTests(unittest.TestCase):
    def config(self):
        return test_hardware.HardwareConfig(
            com_info=[["serial", 1, 6]],
            layout_type=3,
            no_use=[],
            rows=1,
            cols=6,
        )

    def test_initialization_failure_is_non_successful(self):
        driver = FakeDriver(init_errors=["COM9"])
        output = io.StringIO()

        result = test_hardware.run_diagnostic(
            self.config(),
            driver,
            output_duration=0,
            input_duration=0,
            output=output,
            confirm_output=lambda _prompt: True,
        )

        self.assertNotEqual(result, 0)
        self.assertEqual(driver.draws[-1][1], [[[0, 0, 0] for _ in range(6)]])
        self.assertNotIn("Floor blanked.", output.getvalue())
        self.assertIn("blank", output.getvalue().lower())
        self.assertIn("unconfirmed", output.getvalue().lower())
        self.assertTrue(driver.closed)

    def test_nonfinite_timings_are_rejected_before_hardware_initialization(self):
        defaults = {
            "output_duration": 0,
            "input_duration": 0,
            "repeat_interval": 0.05,
            "poll_interval": 0.01,
        }
        for argument in defaults:
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(argument=argument, value=value):
                    driver = FakeDriver()
                    kwargs = dict(defaults)
                    kwargs[argument] = value
                    with self.assertRaises(ValueError):
                        test_hardware.run_diagnostic(
                            self.config(),
                            driver,
                            monotonic=mock.Mock(
                                side_effect=AssertionError("clock must not run")
                            ),
                            sleep=mock.Mock(),
                            output=io.StringIO(),
                            confirm_output=lambda _prompt: True,
                            **kwargs,
                        )
                    self.assertIsNone(driver.layout)
                    self.assertEqual(driver.draws, [])
                    self.assertEqual(driver.updates, 0)
                    self.assertFalse(driver.closed)

    def test_blanks_and_closes_when_diagnostic_raises(self):
        driver = FakeDriver()
        black = [[[0, 0, 0] for _ in range(6)]]

        with mock.patch.object(
            test_hardware,
            "run_output_matrix",
            side_effect=RuntimeError("output failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "output failed"):
                test_hardware.run_diagnostic(
                    self.config(),
                    driver,
                    output_duration=0,
                    input_duration=0,
                    output=io.StringIO(),
                    confirm_output=lambda _prompt: True,
                )

        self.assertEqual(driver.draws[-1][1], black)
        self.assertTrue(driver.closed)

    def test_keyboard_interrupt_still_blanks_and_closes(self):
        driver = FakeDriver()
        black = [[[0, 0, 0] for _ in range(6)]]

        with mock.patch.object(
            test_hardware,
            "run_output_matrix",
            side_effect=KeyboardInterrupt,
        ):
            with self.assertRaises(KeyboardInterrupt):
                test_hardware.run_diagnostic(
                    self.config(),
                    driver,
                    output_duration=0,
                    input_duration=0,
                    output=io.StringIO(),
                    confirm_output=lambda _prompt: True,
                )

        self.assertEqual(driver.draws[-1][1], black)
        self.assertTrue(driver.closed)

    def test_exit_zero_requires_all_output_confirmations_and_all_input_cycles(self):
        complete_frames = [[False] * 6]
        for column in range(6):
            pressed = [False] * 6
            pressed[column] = True
            complete_frames.extend((pressed, [False] * 6))

        cases = (
            ("all confirmed", [True] * 7, complete_frames, 0),
            ("swapped output", [True, True, False, True, True, True, True], complete_frames, 1),
            ("dead output", [False, True, True, True, True, True, True], complete_frames, 1),
            ("missing input", [True] * 7, complete_frames[:-2], 1),
        )
        for name, answers, frames, expected in cases:
            with self.subTest(name=name):
                driver = FakeDriver(frames=frames)
                clock = FakeTime()
                answers_iter = iter(answers)
                result = test_hardware.run_diagnostic(
                    self.config(),
                    driver,
                    output_duration=0,
                    input_duration=len(frames) * 0.01,
                    poll_interval=0.01,
                    monotonic=clock.monotonic,
                    sleep=clock.sleep,
                    output=io.StringIO(),
                    confirm_output=lambda _prompt: next(answers_iter),
                )
                self.assertEqual(result, expected)


class CliValidationTests(unittest.TestCase):
    def test_cli_rejects_nonfinite_timings_before_loading_hardware(self):
        options = (
            "--output-duration",
            "--input-duration",
            "--repeat-interval",
            "--poll-interval",
        )
        for option in options:
            for value in ("nan", "inf", "-inf"):
                with self.subTest(option=option, value=value):
                    with (
                        mock.patch.object(test_hardware, "load_hardware_config") as load,
                        mock.patch.object(test_hardware.sys, "stderr", io.StringIO()),
                    ):
                        result = test_hardware.main([f"{option}={value}"])
                    self.assertNotEqual(result, 0)
                    load.assert_not_called()


if __name__ == "__main__":
    unittest.main()

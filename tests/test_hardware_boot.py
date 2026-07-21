import os
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from api import game_manager


REPO_ROOT = Path(__file__).resolve().parents[1]


class HardwareModeImportTests(unittest.TestCase):
    def test_hardware_mode_imports_in_clean_subprocess_without_opening_serial(self):
        script = """
import sys
import types

driver = types.ModuleType("led.led_control")
driver.init_com = lambda *_args, **_kwargs: (_ for _ in ()).throw(
    AssertionError("serial initialization must not run during import")
)
led = types.ModuleType("led")
led.__path__ = []
led.led_control = driver
sys.modules["led"] = led
sys.modules["led.led_control"] = driver

import api.game_manager
print("hardware-mode import passed")
"""
        env = os.environ.copy()
        env["USE_SERIAL_HD"] = "1"

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("hardware-mode import passed", result.stdout)


class StartupScriptTests(unittest.TestCase):
    def test_batch_script_quotes_hardware_assignment_and_starts_three_services(self):
        script = (REPO_ROOT / "scripts" / "start-dev.bat").read_text(
            encoding="utf-8"
        )
        lines = script.splitlines()
        api_line = next(line for line in lines if 'start "LED Hoops API"' in line)

        self.assertIn('set "USE_SERIAL_HD=1" && python -m uvicorn', api_line)
        self.assertNotIn("set USE_SERIAL_HD=1", api_line)
        self.assertEqual(
            sum(
                line.startswith('start "LED Hoops ')
                for line in lines
            ),
            3,
        )
        self.assertTrue(
            any("python ws_bridge.py" in line for line in lines)
        )
        self.assertTrue(
            any("npm run dev" in line for line in lines)
        )


class FakeShelf(dict):
    def __init__(self, com_info):
        super().__init__(
            list_com_info=com_info,
            led_layout_type=3,
        )
        self.closed = False

    def close(self):
        self.closed = True


class FakeDriver(types.ModuleType):
    def __init__(self, *, errors=(), has_open=True, close_error=None):
        super().__init__("led.led_control")
        self.errors = list(errors)
        self.g_has_open = has_open
        self.close_error = close_error
        self.closed = False
        self.init_com_calls = []
        self.layouts = []

    def init_layout(self, layout_type, rows, cols, no_use):
        self.layouts.append((layout_type, rows, cols, list(no_use)))

    def init_com(self, com_info):
        self.init_com_calls.append(list(com_info))
        return self.errors

    def close_com(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class HardwareInitializationTests(unittest.TestCase):
    def setUp(self):
        self.previous_driver = game_manager._hw_led_control
        self.previous_layout = game_manager._hw_layout_type
        game_manager._hw_led_control = None
        game_manager._hw_layout_type = 0

    def tearDown(self):
        game_manager._hw_led_control = self.previous_driver
        game_manager._hw_layout_type = self.previous_layout

    def run_init(self, driver, com_info):
        led_package = types.ModuleType("led")
        led_package.__path__ = []
        led_package.led_control = driver
        shelf = FakeShelf(com_info)
        settings = {
            "floor_layout_coors_no_use": [],
            "grid_rows": 1,
            "grid_cols": 6,
        }
        with (
            mock.patch.dict(
                sys.modules,
                {"led": led_package, "led.led_control": driver},
            ),
            mock.patch("shelve.open", return_value=shelf),
            mock.patch.object(game_manager, "load_real_settings", return_value=settings),
            mock.patch.object(game_manager, "logger") as logger,
        ):
            result = game_manager._hw_init()
        return result, shelf, logger

    def test_empty_com_configuration_fails_without_caching_driver(self):
        driver = FakeDriver()

        result, shelf, logger = self.run_init(driver, [])

        self.assertIsNone(result)
        self.assertIsNone(game_manager._hw_led_control)
        self.assertEqual(driver.init_com_calls, [])
        self.assertTrue(shelf.closed)
        self.assertTrue(
            any("Hardware init failed" in str(call) for call in logger.error.call_args_list)
        )
        self.assertFalse(
            any("Hardware ready" in str(call) for call in logger.info.call_args_list)
        )

    def test_invalid_com_coverage_fails_before_layout_or_serial_open(self):
        invalid_com_configs = (
            [["COM3", 1, 5]],
            [["COM3", 1, 4], ["COM4", 4, 6]],
            [["COM3", 1.5, 6]],
            [["", 1, 6]],
        )
        for com_info in invalid_com_configs:
            with self.subTest(com_info=com_info):
                driver = FakeDriver()
                result, shelf, _ = self.run_init(driver, com_info)
                self.assertIsNone(result)
                self.assertEqual(driver.layouts, [])
                self.assertEqual(driver.init_com_calls, [])
                self.assertFalse(driver.closed)
                self.assertTrue(shelf.closed)

    def test_com_errors_fail_close_partial_ports_and_do_not_cache_driver(self):
        driver = FakeDriver(errors=["COM4"], has_open=True)

        result, shelf, logger = self.run_init(
            driver, [["COM3", 1, 3], ["COM4", 4, 6]]
        )

        self.assertIsNone(result)
        self.assertIsNone(game_manager._hw_led_control)
        self.assertTrue(driver.closed)
        self.assertTrue(shelf.closed)
        self.assertTrue(
            any("Hardware init failed" in str(call) for call in logger.error.call_args_list)
        )

    def test_false_open_flag_fails_and_closes_driver(self):
        driver = FakeDriver(has_open=False)

        result, _, logger = self.run_init(driver, [["COM3", 1, 6]])

        self.assertIsNone(result)
        self.assertIsNone(game_manager._hw_led_control)
        self.assertTrue(driver.closed)
        self.assertTrue(
            any("Hardware init failed" in str(call) for call in logger.error.call_args_list)
        )

    def test_cleanup_error_does_not_turn_failed_init_into_success(self):
        driver = FakeDriver(
            errors=["COM4"],
            has_open=True,
            close_error=RuntimeError("close failed"),
        )

        result, _, logger = self.run_init(driver, [["COM3", 1, 3], ["COM4", 4, 6]])

        self.assertIsNone(result)
        self.assertIsNone(game_manager._hw_led_control)
        self.assertTrue(driver.closed)
        self.assertTrue(
            any("close failed" in str(call) for call in logger.warning.call_args_list)
        )

    def test_successful_init_caches_driver_and_logs_ready(self):
        driver = FakeDriver(has_open=True)

        result, shelf, logger = self.run_init(driver, [["COM3", 1, 6]])

        self.assertIs(result, driver)
        self.assertIs(game_manager._hw_led_control, driver)
        self.assertEqual(game_manager._hw_layout_type, 3)
        self.assertFalse(driver.closed)
        self.assertTrue(shelf.closed)
        self.assertTrue(
            any("Hardware ready" in str(call) for call in logger.info.call_args_list)
        )
        self.assertFalse(
            any("Hardware init failed" in str(call) for call in logger.error.call_args_list)
        )


class HardwareStartFailureTests(unittest.TestCase):
    def test_hardware_init_failure_aborts_before_import_play_or_load_levels(self):
        manager = game_manager.GameManager()
        with mock.patch.object(
            game_manager,
            "load_real_settings",
            return_value=dict(game_manager._SETTINGS_DEFAULTS),
        ):
            game_id = manager.create_game("card", 1, "normal")
        game = manager.get_game(game_id)
        forbidden_imports = []
        real_import = __import__

        def guarded_import(name, *args, **kwargs):
            if name.startswith(("game_play", "model.setting")):
                forbidden_imports.append(name)
                raise AssertionError(f"forbidden game import: {name}")
            return real_import(name, *args, **kwargs)

        with (
            mock.patch.object(game_manager, "USE_SERIAL_HD", True),
            mock.patch.object(game_manager, "_hw_init", return_value=None),
            mock.patch.object(
                game_manager,
                "_build_level_sequence",
                side_effect=AssertionError("levels must not load"),
            ),
            mock.patch("builtins.__import__", side_effect=guarded_import),
        ):
            manager.start_game(game_id)
            game.thread.join(timeout=2)

        self.assertFalse(game.thread.is_alive())
        self.assertEqual(forbidden_imports, [])
        self.assertIsNone(game.play)
        self.assertIsNone(game.led_table)
        self.assertFalse(game.running)
        self.assertFalse(game.accepting_input)
        self.assertTrue(game._session_over)
        self.assertEqual(game._end_reason, "hardware_error")
        self.assertEqual(
            game.get_state()["game_over_reason"],
            "hardware_error",
        )
        self.assertEqual(game.get_state()["result"], 0)
        self.assertTrue(game.get_state()["game_over"])


if __name__ == "__main__":
    unittest.main()

"""Six-column output/input diagnostic for Hoops hardware.

Run from ``led-hoops/games`` with ``python test_hardware.py``.
"""
import argparse
import math
import os
import shelve
import sys
import time
from dataclasses import dataclass

_GAMES_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_GAMES_DIR)
sys.path.insert(0, _GAMES_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from led import led_control
from hardware_config import (
    HardwareConfigError,
    parse_dimension as shared_parse_dimension,
    validate_com_info,
    validate_hardware_config as shared_validate_hardware_config,
    validate_platform_config,
)

SHELVE = os.path.join(_GAMES_DIR, 'setting', 'led_parameter')
DEFAULT_ROWS, DEFAULT_COLS = 1, 6
EXPECTED_COORDINATES = tuple((0, column) for column in range(DEFAULT_COLS))
BLACK = [0, 0, 0]
COLUMN_COLORS = (
    [254, 0, 0],
    [0, 254, 0],
    [0, 80, 254],
    [254, 180, 0],
    [180, 0, 254],
    [0, 254, 254],
)


class DiagnosticConfigError(ValueError):
    """Raised when settings cannot describe the six physical hoops."""


class DiagnosticTimingError(ValueError):
    """Raised when a diagnostic timing argument is unsafe."""


@dataclass(frozen=True)
class HardwareConfig:
    com_info: list
    layout_type: int
    no_use: list
    rows: int
    cols: int


def parse_dimension(value, field_name):
    """Parse a positive, finite, integer-valued hardware dimension."""
    try:
        return shared_parse_dimension(value, field_name)
    except HardwareConfigError as error:
        raise DiagnosticConfigError(str(error)) from error


def validate_hardware_config(rows, cols, no_use):
    """Require the exact Hoops matrix and all six enabled physical columns."""
    try:
        validate_platform_config(rows, cols, no_use)
    except HardwareConfigError as error:
        message = str(error)
        if "disabled" in message and "(0, 5)" in message:
            raise DiagnosticConfigError(
                "Expected hoop column (0, 5) is disabled by no-use configuration"
            ) from error
        if "disabled" in message:
            raise DiagnosticConfigError(message) from error
        raise DiagnosticConfigError(
            f"Hoops hardware must be exactly 1x6; {message}"
            if "exactly 1x6" not in message
            else message
        ) from error


def load_hardware_config(settings_path=SHELVE):
    db = shelve.open(settings_path, flag="r")
    try:
        try:
            rows = parse_dimension(
                db.get("value_high", DEFAULT_ROWS), "value_high"
            )
            cols = parse_dimension(
                db.get("value_width", DEFAULT_COLS), "value_width"
            )
            validated = shared_validate_hardware_config(
                rows,
                cols,
                db.get("floor_layout_coors_no_use", []),
                db.get("led_layout_type", 0),
                db.get("list_com_info", []),
            )
            config = HardwareConfig(
                com_info=validated["com_info"],
                layout_type=validated["layout_type"],
                no_use=validated["no_use"],
                rows=validated["rows"],
                cols=validated["cols"],
            )
        except DiagnosticConfigError:
            raise
        except HardwareConfigError as error:
            raise DiagnosticConfigError(str(error)) from error
        except (TypeError, ValueError) as error:
            raise DiagnosticConfigError(
                f"Hardware settings contain non-numeric dimensions or layout: {error}"
            ) from error
    finally:
        db.close()
    return config


def _copy_pattern(pattern):
    return [[list(color) for color in row] for row in pattern]


def all_columns_pattern():
    return [[list(color) for color in COLUMN_COLORS]]


def single_column_pattern(column):
    if column not in range(DEFAULT_COLS):
        raise ValueError(f"Hoop column must be 0..5, got {column}")
    row = [BLACK[:] for _ in range(DEFAULT_COLS)]
    row[column] = list(COLUMN_COLORS[column])
    return [row]


def validate_timing_arguments(**arguments):
    """Validate supplied diagnostic durations and intervals before I/O."""
    rules = {
        "output_duration": True,
        "input_duration": True,
        "repeat_interval": False,
        "poll_interval": False,
    }
    unknown = set(arguments) - set(rules)
    if unknown:
        raise TypeError(f"Unknown timing argument(s): {sorted(unknown)}")

    validated = {}
    for name, value in arguments.items():
        if isinstance(value, bool):
            raise DiagnosticTimingError(f"{name} must be a finite number")
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise DiagnosticTimingError(
                f"{name} must be a finite number"
            ) from error
        allow_zero = rules[name]
        valid_range = numeric >= 0 if allow_zero else numeric > 0
        if not math.isfinite(numeric) or not valid_range:
            qualifier = "nonnegative" if allow_zero else "positive"
            raise DiagnosticTimingError(
                f"{name} must be a finite {qualifier} number"
            )
        validated[name] = numeric
    return validated


def _send_phase(
    driver,
    layout_type,
    pattern,
    duration,
    repeat_interval,
    monotonic,
    sleep,
):
    timings = validate_timing_arguments(
        output_duration=duration, repeat_interval=repeat_interval
    )
    duration = timings["output_duration"]
    repeat_interval = timings["repeat_interval"]
    started = monotonic()
    while True:
        driver.draw_screen_by_com(layout_type, _copy_pattern(pattern))
        remaining = duration - (monotonic() - started)
        if remaining <= 0:
            return
        sleep(min(repeat_interval, remaining))


def confirm_output_phase(prompt):
    """Ask an operator to confirm one output phase.

    Only ``yes`` / ``y`` (any case) counts as pass. Blank input, other text,
    and EOF all fail. Never auto-passes.
    """
    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        return False
    return answer in {"yes", "y"}


def run_output_matrix(
    driver,
    layout_type,
    phase_duration=1.0,
    repeat_interval=0.05,
    monotonic=time.monotonic,
    sleep=time.sleep,
    output=sys.stdout,
    confirm=confirm_output_phase,
):
    timings = validate_timing_arguments(
        output_duration=phase_duration, repeat_interval=repeat_interval
    )
    phase_duration = timings["output_duration"]
    repeat_interval = timings["repeat_interval"]

    phases = [
        (
            "OUTPUT all columns: verify six distinct colors, including column 5",
            all_columns_pattern(),
            "Confirm all six distinct colors are visible (yes/no): ",
        )
    ]
    for column in range(DEFAULT_COLS):
        phases.append(
            (
                f"OUTPUT column {column}: only physical (0,{column}) should be lit",
                single_column_pattern(column),
                f"Confirm only column {column} is lit (yes/no): ",
            )
        )

    all_confirmed = True
    for description, pattern, prompt in phases:
        print(description, file=output)
        _send_phase(
            driver,
            layout_type,
            pattern,
            phase_duration,
            repeat_interval,
            monotonic,
            sleep,
        )
        if "all columns" in description:
            print("  SENT all-six color phase", file=output)
        else:
            column = description.split("column ", 1)[1].split(":", 1)[0]
            print(f"  SENT column {column} phase", file=output)
        if confirm(prompt):
            print("OUTPUT MANUAL PASS", file=output)
        else:
            all_confirmed = False
            print("OUTPUT MANUAL FAIL", file=output)
    return all_confirmed


def run_input_matrix(
    driver,
    layout_type,
    duration=15.0,
    poll_interval=0.01,
    monotonic=time.monotonic,
    sleep=time.sleep,
    output=sys.stdout,
):
    timings = validate_timing_arguments(
        input_duration=duration, poll_interval=poll_interval
    )
    duration = timings["input_duration"]
    poll_interval = timings["poll_interval"]

    print(
        "INPUT: release, press, and release every hoop column 0..5",
        file=output,
    )
    state = [[None] * DEFAULT_COLS]
    previous = [None] * DEFAULT_COLS
    armed = [False] * DEFAULT_COLS
    pressed_after_arming = [False] * DEFAULT_COLS
    completed = set()
    started = monotonic()
    remaining = duration

    while remaining > 0:
        driver.update_screen_state_by_com(layout_type, state, state)
        for column in range(DEFAULT_COLS):
            coordinate = (0, column)
            raw_value = state[0][column]
            if raw_value is None:
                continue
            current_value = bool(raw_value)
            previous_value = previous[column]
            if previous_value is None:
                if current_value:
                    print(
                        f"  BASELINE HELD (0,{column}); release to arm",
                        file=output,
                    )
                else:
                    armed[column] = True
                    print(f"  ARMED (0,{column}); baseline released", file=output)
                previous[column] = current_value
                continue

            if current_value and not previous_value:
                if armed[column]:
                    pressed_after_arming[column] = True
                    print(f"  PRESS (0,{column})", file=output)
            elif previous_value and not current_value:
                print(f"  RELEASE (0,{column})", file=output)
                if pressed_after_arming[column]:
                    completed.add(coordinate)
                    pressed_after_arming[column] = False
                    print(f"  CYCLE COMPLETE (0,{column})", file=output)
                else:
                    armed[column] = True
                    print(f"  ARMED (0,{column}); released", file=output)
            previous[column] = current_value
        remaining = duration - (monotonic() - started)
        if remaining > 0:
            sleep(min(poll_interval, remaining))

    print("INPUT RESULT", file=output)
    for coordinate in EXPECTED_COORDINATES:
        status = "PASS" if coordinate in completed else "MISSING"
        print(f"  {coordinate}: {status}", file=output)
    return completed == set(EXPECTED_COORDINATES)


def _blank_floor(driver, layout_type, output, serial_usable=True):
    try:
        driver.draw_screen_by_com(
            layout_type, [[BLACK[:] for _ in range(DEFAULT_COLS)]]
        )
        if serial_usable:
            print("Floor blanked.", file=output)
        else:
            print(
                "Floor blank command attempted; serial was not usable, "
                "so delivery is unconfirmed.",
                file=output,
            )
    except Exception as error:
        print(f"WARNING: failed to blank floor: {error}", file=output)


def run_diagnostic(
    config,
    driver=led_control,
    output_duration=1.0,
    input_duration=15.0,
    repeat_interval=0.05,
    poll_interval=0.01,
    monotonic=time.monotonic,
    sleep=time.sleep,
    output=sys.stdout,
    confirm_output=confirm_output_phase,
):
    timings = validate_timing_arguments(
        output_duration=output_duration,
        input_duration=input_duration,
        repeat_interval=repeat_interval,
        poll_interval=poll_interval,
    )
    output_duration = timings["output_duration"]
    input_duration = timings["input_duration"]
    repeat_interval = timings["repeat_interval"]
    poll_interval = timings["poll_interval"]
    validate_hardware_config(config.rows, config.cols, config.no_use)
    try:
        validate_com_info(config.com_info)
    except HardwareConfigError as error:
        raise DiagnosticConfigError(str(error)) from error
    layout_ready = False
    serial_usable = False
    try:
        print("=== Hoops Six-Column Hardware Diagnostic ===", file=output)
        print(
            f"Grid {config.rows}x{config.cols}; layout={config.layout_type}; "
            f"COM={config.com_info}",
            file=output,
        )
        layout_ready = True
        driver.init_layout(
            config.layout_type, config.rows, config.cols, config.no_use
        )
        serial_errors = driver.init_com(config.com_info)
        serial_open = bool(getattr(driver, "g_has_open", False))
        serial_usable = bool(config.com_info and serial_open and not serial_errors)
        if not serial_usable:
            print(
                "ERROR: serial initialization failed"
                + (f" for {serial_errors}" if serial_errors else ""),
                file=output,
            )
            return 2
        print("Serial initialization passed.", file=output)

        output_ok = run_output_matrix(
            driver,
            config.layout_type,
            phase_duration=output_duration,
            repeat_interval=repeat_interval,
            monotonic=monotonic,
            sleep=sleep,
            output=output,
            confirm=confirm_output,
        )
        complete = run_input_matrix(
            driver,
            config.layout_type,
            duration=input_duration,
            poll_interval=poll_interval,
            monotonic=monotonic,
            sleep=sleep,
            output=output,
        )
        return 0 if (output_ok and complete) else 1
    finally:
        if layout_ready:
            _blank_floor(
                driver,
                config.layout_type,
                output,
                serial_usable=serial_usable,
            )
        try:
            driver.close_com()
        except Exception as error:
            print(f"WARNING: failed to close serial connection: {error}", file=output)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", default=SHELVE, help="led_parameter shelve path")
    parser.add_argument(
        "--output-duration",
        type=float,
        default=1.0,
        help="seconds for each of seven output phases",
    )
    parser.add_argument(
        "--input-duration",
        type=float,
        default=15.0,
        help="seconds to observe all six input columns",
    )
    parser.add_argument(
        "--repeat-interval",
        type=float,
        default=0.05,
        help="seconds between repeated output frames",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.01,
        help="seconds between sensor reads",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        timings = validate_timing_arguments(
            output_duration=args.output_duration,
            input_duration=args.input_duration,
            repeat_interval=args.repeat_interval,
            poll_interval=args.poll_interval,
        )
        config = load_hardware_config(args.settings)
        return run_diagnostic(
            config,
            **timings,
        )
    except DiagnosticTimingError as error:
        print(f"ARGUMENT ERROR: {error}", file=sys.stderr)
        return 2
    except DiagnosticConfigError as error:
        print(f"CONFIG ERROR: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nDiagnostic interrupted.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"DIAGNOSTIC ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

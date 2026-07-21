"""Strict shared Hoops hardware/platform configuration validation.

Used by both the headless API (`api/game_manager.py`) and the standalone
diagnostic (`games/test_hardware.py`). Pure: no serial or GUI imports.
"""

from decimal import Decimal, InvalidOperation
from numbers import Integral

EXPECTED_ROWS = 1
EXPECTED_COLS = 6
EXPECTED_TILES = 6
SUPPORTED_LAYOUT_TYPES = frozenset(range(8))
EXPECTED_COORDINATES = tuple((0, column) for column in range(EXPECTED_COLS))


class HardwareConfigError(ValueError):
    """Raised when Hoops hardware settings are unsafe or incomplete."""


def parse_dimension(value, field_name):
    """Parse a finite, positive, integer-valued dimension.

    Accepts ints and integer-valued floats/strings such as ``1``, ``1.0``,
    or ``"6.0"``. Rejects bools, fractions, NaN/Inf, and non-numeric values.
    """
    if isinstance(value, bool) or value is None:
        raise HardwareConfigError(
            f"{field_name} must be a finite positive integer, got {value!r}"
        )
    try:
        numeric = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError) as error:
        raise HardwareConfigError(
            f"{field_name} must be a finite positive integer, got {value!r}"
        ) from error
    if (
        not numeric.is_finite()
        or numeric <= 0
        or numeric != numeric.to_integral_value()
    ):
        raise HardwareConfigError(
            f"{field_name} must be a finite positive integer, got {value!r}"
        )
    return int(numeric)


def _normalize_no_use_coordinate(coordinate):
    if (
        not isinstance(coordinate, (list, tuple))
        or len(coordinate) != 2
        or not all(
            isinstance(value, Integral) and not isinstance(value, bool)
            for value in coordinate
        )
    ):
        raise HardwareConfigError(
            f"Hoops hardware no-use coordinate {coordinate!r} must be an "
            "integer (row, col) pair"
        )
    return (int(coordinate[0]), int(coordinate[1]))


def validate_platform_config(rows, cols, no_use):
    """Require exactly 1×6 with all six hoop columns enabled."""
    try:
        rows = parse_dimension(rows, "grid_rows")
        cols = parse_dimension(cols, "grid_cols")
    except HardwareConfigError as error:
        raise HardwareConfigError(
            f"Hoops hardware must be exactly 1x6; {error}"
        ) from error

    if (rows, cols) != (EXPECTED_ROWS, EXPECTED_COLS):
        raise HardwareConfigError(
            f"Hoops hardware must be exactly 1x6; configured {rows}x{cols}"
        )

    if no_use is None:
        normalized_no_use = []
    elif not isinstance(no_use, (list, tuple)):
        raise HardwareConfigError(
            "Hoops hardware no-use list must be a sequence of coordinates"
        )
    else:
        normalized_no_use = []
        disabled = set()
        for coordinate in no_use:
            cell = _normalize_no_use_coordinate(coordinate)
            if cell not in EXPECTED_COORDINATES:
                raise HardwareConfigError(
                    f"Hoops hardware no-use coordinate {cell} is outside "
                    "the 1x6 matrix"
                )
            disabled.add(cell)
            normalized_no_use.append(cell)
        if disabled:
            raise HardwareConfigError(
                "Hoops hardware must enable all six hoop columns; disabled: "
                + ", ".join(map(str, sorted(disabled)))
            )

    return rows, cols, normalized_no_use


def validate_com_info(com_info):
    """Normalize COM metadata and require exact coverage of tiles 1..6.

    Driver semantics use inclusive one-based ranges via Python slice
    ``[start-1:end)``, so a range ``[start, end]`` covers positions
    ``start`` through ``end`` inclusive.
    """
    if not isinstance(com_info, (list, tuple)) or not com_info:
        raise HardwareConfigError(
            "Hoops hardware requires at least one COM port entry"
        )

    normalized = []
    covered = set()
    seen_names = set()

    for entry in com_info:
        if not isinstance(entry, (list, tuple)) or len(entry) < 3:
            raise HardwareConfigError(
                f"Hoops hardware COM entry {entry!r} must include "
                "name, start, and end"
            )

        name = entry[0]
        if not isinstance(name, str) or not name.strip():
            raise HardwareConfigError(
                f"Hoops hardware COM name must be a non-empty string, got {name!r}"
            )
        if name in seen_names:
            raise HardwareConfigError(
                f"Hoops hardware COM port {name!r} is duplicated"
            )
        seen_names.add(name)

        try:
            start = parse_dimension(entry[1], "COM start")
            end = parse_dimension(entry[2], "COM end")
        except HardwareConfigError as error:
            raise HardwareConfigError(
                f"Hoops hardware COM range for {name!r} is invalid; {error}"
            ) from error

        if not (1 <= start <= end <= EXPECTED_TILES):
            raise HardwareConfigError(
                f"Hoops hardware COM range for {name!r} must satisfy "
                f"1 <= start <= end <= {EXPECTED_TILES}; got {start}..{end}"
            )

        span = set(range(start, end + 1))
        overlap = covered & span
        if overlap:
            raise HardwareConfigError(
                f"Hoops hardware COM ranges overlap at tile(s) "
                f"{sorted(overlap)}"
            )
        covered |= span

        normalized_entry = [name, start, end]
        if len(entry) > 3:
            normalized_entry.extend(entry[3:])
        normalized.append(normalized_entry)

    expected = set(range(1, EXPECTED_TILES + 1))
    if covered != expected:
        missing = sorted(expected - covered)
        extra = sorted(covered - expected)
        details = []
        if missing:
            details.append(f"missing {missing}")
        if extra:
            details.append(f"extra {extra}")
        raise HardwareConfigError(
            "Hoops hardware COM ranges must cover tiles 1..6 exactly; "
            + ", ".join(details)
        )

    return normalized


def validate_hardware_config(rows, cols, no_use, layout_type, com_info=None):
    """Validate full hardware settings used by production init and diagnostics."""
    rows, cols, no_use = validate_platform_config(rows, cols, no_use)

    if isinstance(layout_type, bool) or layout_type is None:
        raise HardwareConfigError(
            f"Hoops hardware layout type must be an integer 0..7, got {layout_type!r}"
        )
    try:
        if isinstance(layout_type, str):
            layout = parse_dimension(layout_type, "layout type")
        elif isinstance(layout_type, Integral):
            layout = int(layout_type)
        elif isinstance(layout_type, float):
            layout = parse_dimension(layout_type, "layout type")
        else:
            raise HardwareConfigError(
                f"Hoops hardware layout type must be an integer 0..7, got {layout_type!r}"
            )
    except HardwareConfigError as error:
        raise HardwareConfigError(
            f"Hoops hardware layout type is invalid; {error}"
        ) from error

    if layout not in SUPPORTED_LAYOUT_TYPES:
        raise HardwareConfigError(
            f"Hoops hardware layout type must be an integer 0..7, got {layout!r}"
        )

    validated = {
        "rows": rows,
        "cols": cols,
        "no_use": no_use,
        "layout_type": layout,
    }
    if com_info is not None:
        validated["com_info"] = validate_com_info(com_info)
    return validated

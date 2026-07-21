"""Headless, source-parity level scaling for Hoops.

This module ports the coordinate scaling used by the original Python 3.7
``GameRunning`` implementation without importing its GUI or hardware stack.
"""

from decimal import Decimal, ROUND_HALF_UP
from numbers import Integral


FLOOR_LIGHT = "floor_light"
SUPPORTED_SCALES = {"both", "row", "col", "none", "none2edge"}
_SCALED_MARKER = "_hoops_level_scaled_to_platform"


class LevelScalingError(ValueError):
    """Raised when a level cannot be safely scaled to a platform."""


def _is_int(value):
    return isinstance(value, Integral) and not isinstance(value, bool)


def _positive_dimension(value, name):
    if not _is_int(value) or value <= 0:
        raise LevelScalingError(f"{name} must be a positive integer, got {value!r}")
    return int(value)


def _half_up(value):
    return int(Decimal(value).quantize(Decimal("0"), rounding=ROUND_HALF_UP))


def _coordinate(value, rows, cols, label):
    if (
        not isinstance(value, (tuple, list))
        or len(value) != 2
        or not _is_int(value[0])
        or not _is_int(value[1])
    ):
        raise LevelScalingError(f"{label} must be an integer (row, col) pair")
    cell = (int(value[0]), int(value[1]))
    if not (0 <= cell[0] < rows and 0 <= cell[1] < cols):
        raise LevelScalingError(
            f"{label} {cell!r} is outside the {rows}x{cols} layout"
        )
    return cell


def _activity_area(value, rows, cols, label):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise LevelScalingError(f"{label} must contain row and column ranges")
    ranges = []
    for axis, limit in zip(value, (rows, cols)):
        if (
            not isinstance(axis, (tuple, list))
            or len(axis) != 2
            or not _is_int(axis[0])
            or not _is_int(axis[1])
        ):
            raise LevelScalingError(f"{label} ranges must contain integer endpoints")
        start, end = int(axis[0]), int(axis[1])
        if not (0 <= start <= end <= limit):
            raise LevelScalingError(
                f"{label} range {(start, end)!r} is outside 0..{limit}"
            )
        ranges.append((start, end))
    return ranges


def _restore_collection(original, cells):
    ordered = sorted(cells)
    if isinstance(original, frozenset):
        return frozenset(cells)
    if isinstance(original, set):
        return set(cells)
    if isinstance(original, tuple):
        return tuple(ordered)
    if isinstance(original, list):
        return ordered
    try:
        return type(original)(ordered)
    except (TypeError, ValueError):
        return set(cells)


def _move_range_zone_in_out(move_range, area_before, area_after):
    row_before, col_before = area_before
    row_after, col_after = area_after
    multiple_row = row_after / row_before
    multiple_col = col_after / col_before
    zone_middle_row = (move_range[0][0] + move_range[0][1]) / 2
    zone_middle_col = (move_range[1][0] + move_range[1][1]) / 2
    zone_edge_row = (move_range[0][1] - move_range[0][0]) / 2
    zone_edge_col = (move_range[1][1] - move_range[1][0]) / 2
    return [
        (
            _half_up((zone_middle_row - zone_edge_row) * multiple_row),
            _half_up((zone_middle_row + zone_edge_row) * multiple_row),
        ),
        (
            _half_up((zone_middle_col - zone_edge_col) * multiple_col),
            _half_up((zone_middle_col + zone_edge_col) * multiple_col),
        ),
    ]


def _edge(cells, axis, source_size):
    values = {cell[axis] for cell in cells}
    if 0 in values:
        return 0
    last = source_size - 1
    if last in values:
        return last
    return -1


def _unscaled_bounds(cell_value, center_before, center_after, edge, before, after):
    if edge == 0:
        return cell_value, cell_value + 1
    if edge > 0:
        start = after - (before - cell_value)
        return start, start + 1
    start = cell_value - center_before + center_after
    return start, start + 1


def _rounded_bounds(start, end, limit):
    start = _half_up(round(start, 2))
    end = _half_up(round(end, 2))
    start = max(0, min(start, limit))
    end = max(0, min(end, limit))
    if start == end:
        if start < limit:
            end = start + 1
        else:
            start = end - 1
    return start, end


def _zone_in_out(coors_before, coors_after, cells, side):
    if not cells:
        return set()

    row_before, col_before = coors_before
    row_after, col_after = coors_after
    multiple_row = row_after / row_before
    multiple_col = col_after / col_before
    min_row = min(cell[0] for cell in cells)
    max_row = max(cell[0] for cell in cells)
    min_col = min(cell[1] for cell in cells)
    max_col = max(cell[1] for cell in cells)
    center_row = (min_row + max_row) / 2
    center_col = (min_col + max_col) / 2
    center_row_after = center_row * multiple_row
    center_col_after = center_col * multiple_col
    row_edge = _edge(cells, 0, row_before)
    col_edge = _edge(cells, 1, col_before)
    result = set()

    for row, col in cells:
        if side in ("both", "row"):
            row_min = row * multiple_row
            row_max = (row + 1) * multiple_row
        else:
            row_min, row_max = _unscaled_bounds(
                row, center_row, center_row_after, row_edge, row_before, row_after
            )

        if side in ("both", "col"):
            col_min = col * multiple_col
            col_max = (col + 1) * multiple_col
        else:
            col_min, col_max = _unscaled_bounds(
                col, center_col, center_col_after, col_edge, col_before, col_after
            )

        row_min, row_max = _rounded_bounds(row_min, row_max, row_after)
        col_min, col_max = _rounded_bounds(col_min, col_max, col_after)
        for new_row in range(row_min, row_max):
            for new_col in range(col_min, col_max):
                result.add((new_row, new_col))

    return result


def scale_level_to_platform(
    game_obj,
    dict_group,
    platform_rows,
    platform_cols,
    floor_layout_coors_no_use=(),
):
    """Scale one loaded Hoops level in place to a floor platform.

    The loaded source object may only be scaled once. The function returns the
    same ``(game_obj, dict_group)`` objects for convenient call-site chaining.
    """

    if getattr(game_obj, _SCALED_MARKER, False):
        raise LevelScalingError("level object is already scaled to a platform")

    source_rows = _positive_dimension(getattr(game_obj, "row", None), "game row")
    source_cols = _positive_dimension(getattr(game_obj, "col", None), "game col")
    target_rows = _positive_dimension(platform_rows, "platform_rows")
    target_cols = _positive_dimension(platform_cols, "platform_cols")

    if getattr(game_obj, "corner_line_start", 0) != 0:
        raise LevelScalingError("corner/wall layouts are not supported by Hoops scaling")
    if getattr(game_obj, "wall_light", False) or getattr(game_obj, "screen", False):
        raise LevelScalingError("wall and screen layouts are not supported")
    if not hasattr(dict_group, "items"):
        raise LevelScalingError("dict_group must be a mapping of level groups")

    no_use = {
        _coordinate(cell, target_rows, target_cols, "no-use coordinate")
        for cell in floor_layout_coors_no_use
    }
    prepared = []
    for key, group in dict_group.items():
        if getattr(group, _SCALED_MARKER, False):
            raise LevelScalingError(f"group {key!r} is already scaled to a platform")
        if getattr(group, "type", None) != FLOOR_LIGHT:
            raise LevelScalingError(
                f"group {key!r} has unsupported type {getattr(group, 'type', None)!r}"
            )
        scale = getattr(group, "scale", None)
        if not isinstance(scale, str) or scale not in SUPPORTED_SCALES:
            raise LevelScalingError(f"group {key!r} has unsupported scale {scale!r}")
        members = getattr(group, "start_member", None)
        if members is None or isinstance(members, (str, bytes)):
            raise LevelScalingError(f"group {key!r} start_member must be a collection")
        try:
            source_cells = {
                _coordinate(cell, source_rows, source_cols, f"group {key!r} coordinate")
                for cell in members
            }
        except TypeError as exc:
            raise LevelScalingError(
                f"group {key!r} start_member must be an iterable collection"
            ) from exc
        area = _activity_area(
            getattr(group, "activity_area", None),
            source_rows,
            source_cols,
            f"group {key!r} activity_area",
        )
        scaled_cells = _zone_in_out(
            (source_rows, source_cols),
            (target_rows, target_cols),
            source_cells,
            "none2edge" if scale == "none" else scale,
        )
        if getattr(group, "speed", None) == 0:
            scaled_cells.difference_update(no_use)
        prepared.append(
            (
                group,
                _restore_collection(members, scaled_cells),
                _move_range_zone_in_out(
                    area,
                    (source_rows, source_cols),
                    (target_rows, target_cols),
                ),
            )
        )

    zone_names = (
        "zone_row_from",
        "zone_row_to",
        "zone_col_from",
        "zone_col_to",
    )
    zone_limits = (source_rows, source_rows, source_cols, source_cols)
    zone_values = []
    for name, limit in zip(zone_names, zone_limits):
        value = getattr(game_obj, name, None)
        if not _is_int(value) or not 0 <= value <= limit:
            raise LevelScalingError(f"{name} must be an integer in 0..{limit}")
        zone_values.append(int(value))
    if zone_values[0] > zone_values[1]:
        raise LevelScalingError("zone row range is reversed")
    if zone_values[2] > zone_values[3]:
        raise LevelScalingError("zone column range is reversed")

    for group, members, activity_area in prepared:
        group.start_member = members
        group.activity_area = activity_area
        setattr(group, _SCALED_MARKER, (target_rows, target_cols))

    row_resize = target_rows / source_rows
    col_resize = target_cols / source_cols
    game_obj.zone_row_from = round(zone_values[0] * row_resize)
    game_obj.zone_row_to = round(zone_values[1] * row_resize)
    game_obj.zone_col_from = round(zone_values[2] * col_resize)
    game_obj.zone_col_to = round(zone_values[3] * col_resize)
    setattr(game_obj, _SCALED_MARKER, (target_rows, target_cols))
    return game_obj, dict_group

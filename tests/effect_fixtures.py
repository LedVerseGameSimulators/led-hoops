"""Build tiny .led ZIP fixtures for fast effects/session-loop tests."""
from __future__ import annotations

import dbm.dumb
import os
import shelve
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
EFFECTS_DIR = FIXTURES_DIR / "effects"
LEVELS_DIR = FIXTURES_DIR / "levels"

GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 254)


def _floor_group(cells, color, start, end):
    if isinstance(cells, set):
        members = cells
    else:
        members = set(cells)
    return SimpleNamespace(
        start_member=members,
        type="floor_light",
        speed=0,
        color=[[color[0], color[1], color[2]]] * 3,
        start_time_sec=start,
        end_time_sec=end,
        direct="right",
        edge_run_into="back",
        move_distance=0.0,
        start_area=1,
        activity_area=[(0, 1), (0, 6)],
        scale="both",
        breath_color_float=[],
        breath_color=[],
        breath_switch=[True, True, True],
        trigger_span_tm=0,
    )


def _game_obj(*, play_order=True):
    return SimpleNamespace(
        play_order=play_order,
        zone_row_from=0,
        zone_row_to=1,
        zone_col_from=0,
        zone_col_to=6,
        row=1,
        col=6,
        cover_action=False,
    )


def _write_led_zip(path: Path, groups, game_obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        sub = os.path.join(tmp, "board")
        os.makedirs(sub)
        gf = os.path.join(sub, "game_file")
        with shelve.Shelf(dbm.dumb.open(gf, "c")) as db:
            db["para_key_game"] = game_obj
            db["dict_group"] = groups
        with zipfile.ZipFile(path, "w") as zf:
            for root, _, files in os.walk(sub):
                for name in files:
                    fp = os.path.join(root, name)
                    zf.write(fp, os.path.relpath(fp, tmp))


def build_countdown_led(path: Path | None = None, *, step: float = 0.05) -> Path:
    path = path or EFFECTS_DIR / "countdown.led"
    groups = {
        "step3": _floor_group([(0, 2), (0, 3)], GREEN, 0.0, step),
        "step2": _floor_group([(0, c) for c in range(1, 5)], GREEN, step, 2 * step),
        "step1": _floor_group([(0, c) for c in range(6)], GREEN, 2 * step, 3 * step),
        "go": _floor_group([(0, c) for c in range(6)], GREEN, 3 * step, 3 * step + step * 0.4),
    }
    _write_led_zip(path, groups, _game_obj(play_order=True))
    return path


def build_level_clear_led(path: Path | None = None, *, duration: float = 0.08) -> Path:
    path = path or EFFECTS_DIR / "level_clear.led"
    groups = {
        "all_green": _floor_group([(0, c) for c in range(6)], GREEN, 0.0, duration),
    }
    _write_led_zip(path, groups, _game_obj(play_order=True))
    return path


def build_level_fail_led(path: Path | None = None, *, duration: float = 0.08) -> Path:
    path = path or EFFECTS_DIR / "level_fail.led"
    groups = {
        "all_red": _floor_group([(0, c) for c in range(6)], RED, 0.0, duration),
    }
    _write_led_zip(path, groups, _game_obj(play_order=True))
    return path


def build_tiny_gameplay_led(
    path: Path | None = None,
    *,
    board_time: float = 30.0,
    include_red: bool = True,
    include_goal: bool = True,
) -> Path:
    """Minimal 1×6 gameplay board for API session-loop tests."""
    path = path or LEVELS_DIR / "tiny.led"
    groups = {}
    if include_goal:
        groups["goal"] = _floor_group([(0, 4)], BLUE, 0.0, board_time)
    if include_red:
        groups["red"] = _floor_group([(0, 0)], RED, 0.0, board_time)
    _write_led_zip(path, groups, _game_obj(play_order=False))
    return path


def ensure_all_fixtures() -> dict[str, Path]:
    """Create/update all fixture archives; return path map."""
    build_countdown_led()
    build_level_clear_led()
    build_level_fail_led()
    build_tiny_gameplay_led()
    build_tiny_gameplay_led(LEVELS_DIR / "tiny_b.led")
    return {
        "countdown": EFFECTS_DIR / "countdown.led",
        "level_clear": EFFECTS_DIR / "level_clear.led",
        "level_fail": EFFECTS_DIR / "level_fail.led",
        "tiny": LEVELS_DIR / "tiny.led",
        "tiny_b": LEVELS_DIR / "tiny_b.led",
    }


if __name__ == "__main__":
    paths = ensure_all_fixtures()
    for name, p in paths.items():
        print(f"{name}: {p}")

"""Scoreable Hoops LEDs must render at authored main_color brightness."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import api.game_manager as game_manager


class HoopsScoreableBrightnessTests(unittest.TestCase):
    def test_goal_p1_p2_use_authored_main_color_at_multiple_total_pass(self):
        table = game_manager.HeadlessLedTable(10, 1, 6)
        authored = {
            (0, 0): (0, 0, 254),      # p1 blue
            (0, 1): (254, 128, 0),    # p2 orange
            (0, 2): (254, 254, 0),    # goal yellow
        }
        cell_win = {
            cell: (0, category, color)
            for cell, (category, color) in (
                ((0, 0), ("p1", authored[(0, 0)])),
                ((0, 1), ("p2", authored[(0, 1)])),
                ((0, 2), ("goal", authored[(0, 2)])),
            )
        }

        for total_pass in (0.0, 0.25, 0.5, 1.0, 2.0, 3.75):
            display = game_manager._build_hoops_led_display(
                cell_win, table, total_pass, {}, now=100.0
            )
            for (row, col), expected in authored.items():
                index = row * table.led_col + col
                with self.subTest(total_pass=total_pass, cell=(row, col)):
                    self.assertEqual(
                        display[index],
                        list(expected),
                        msg=(
                            f"scoreable LED at {total_pass=:.2f}s should match "
                            f"authored main_color {expected}"
                        ),
                    )

    def test_hazard_cells_and_penalty_flash_stay_unchanged(self):
        table = game_manager.HeadlessLedTable(10, 1, 6)
        hazard_color = (254, 0, 0)
        cell_win = {(0, 0): (0, "hazard", hazard_color)}
        display = game_manager._build_hoops_led_display(
            cell_win, table, 0.0, {}, now=100.0
        )
        self.assertEqual(display[0], list(hazard_color))

        flash_display = game_manager._build_hoops_led_display(
            cell_win,
            table,
            0.0,
            {(0, 0): 99.9},
            now=100.0,
        )
        self.assertEqual(flash_display[0], [255, 0, 0])


if __name__ == "__main__":
    unittest.main()

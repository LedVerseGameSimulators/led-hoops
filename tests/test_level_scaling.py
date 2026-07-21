import copy
import unittest
from types import SimpleNamespace

from api.level_scaling import LevelScalingError, scale_level_to_platform


def make_game(**overrides):
    values = {
        "row": 1,
        "col": 5,
        "zone_row_from": 0,
        "zone_row_to": 1,
        "zone_col_from": 0,
        "zone_col_to": 5,
        "corner_line_start": 0,
        "game_area_adaption": True,
        "wall_light": False,
        "screen": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_group(member, scale="both", **overrides):
    values = {
        "start_member": member,
        "scale": scale,
        "type": "floor_light",
        "speed": 0,
        "start_area": 1,
        "activity_area": [(0, 1), (0, 5)],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class GoldenMappingTests(unittest.TestCase):
    def test_both_scale_matches_original_single_cell_mapping(self):
        expected = {
            0: {(0, 0)},
            1: {(0, 1)},
            2: {(0, 2), (0, 3)},
            3: {(0, 4)},
            4: {(0, 5)},
        }
        for source_col, target_cells in expected.items():
            with self.subTest(source_col=source_col):
                game = make_game()
                group = make_group({(0, source_col)}, scale="both")
                scale_level_to_platform(game, {"g": group}, 1, 6)
                self.assertEqual(group.start_member, target_cells)

    def test_none_and_none2edge_match_original_fixed_hazard_mapping(self):
        expected_cols = {0: 0, 1: 1, 2: 2, 3: 4, 4: 5}
        for scale in ("none", "none2edge"):
            for source_col, target_col in expected_cols.items():
                with self.subTest(scale=scale, source_col=source_col):
                    game = make_game()
                    group = make_group({(0, source_col)}, scale=scale)
                    scale_level_to_platform(game, {"g": group}, 1, 6)
                    self.assertEqual(group.start_member, {(0, target_col)})

    def test_activity_area_and_all_zone_fields_are_scaled(self):
        game = make_game(
            zone_row_from=0,
            zone_row_to=1,
            zone_col_from=1,
            zone_col_to=5,
        )
        group = make_group({(0, 0)})

        scale_level_to_platform(game, {"g": group}, 1, 6)

        self.assertEqual(group.activity_area, [(0, 1), (0, 6)])
        self.assertEqual(
            (
                game.zone_row_from,
                game.zone_row_to,
                game.zone_col_from,
                game.zone_col_to,
            ),
            (0, 1, 1, 6),
        )

    def test_preserves_list_membership_collection(self):
        game = make_game()
        group = make_group([(0, 2)])

        scale_level_to_platform(game, {"g": group}, 1, 6)

        self.assertIsInstance(group.start_member, list)
        self.assertEqual(set(group.start_member), {(0, 2), (0, 3)})


class FilteringTests(unittest.TestCase):
    def test_no_use_cells_are_removed_from_static_groups_only(self):
        static = make_group({(0, 2)}, scale="both", speed=0)
        moving = make_group({(0, 2)}, scale="both", speed=1)

        scale_level_to_platform(
            make_game(),
            {"static": static, "moving": moving},
            1,
            6,
            floor_layout_coors_no_use={(0, 3)},
        )

        self.assertEqual(static.start_member, {(0, 2)})
        self.assertEqual(moving.start_member, {(0, 2), (0, 3)})


class ValidationTests(unittest.TestCase):
    def test_rejects_invalid_source_or_platform_dimensions(self):
        cases = [
            (make_game(row=0), 1, 6),
            (make_game(col=-1), 1, 6),
            (make_game(), 0, 6),
            (make_game(), 1, -1),
        ]
        for game, rows, cols in cases:
            with self.subTest(game=(game.row, game.col), platform=(rows, cols)):
                with self.assertRaises(LevelScalingError):
                    scale_level_to_platform(game, {}, rows, cols)

    def test_rejects_unsupported_layouts(self):
        cases = [
            (make_game(corner_line_start=1), make_group({(0, 0)})),
            (make_game(wall_light=True), make_group({(0, 0)})),
            (make_game(screen=True), make_group({(0, 0)})),
            (make_game(), make_group({(0, 0)}, type="wall_light")),
        ]
        for game, group in cases:
            with self.subTest(game=vars(game), group=vars(group)):
                with self.assertRaises(LevelScalingError):
                    scale_level_to_platform(game, {"g": group}, 1, 6)

    def test_rejects_unknown_or_non_string_scale(self):
        for scale in ("diagonal", None, 1):
            with self.subTest(scale=scale):
                with self.assertRaises(LevelScalingError):
                    scale_level_to_platform(
                        make_game(), {"g": make_group({(0, 0)}, scale=scale)}, 1, 6
                    )

    def test_rejects_invalid_coordinates(self):
        groups = [
            make_group({(1, 0)}),
            make_group({(0, 5)}),
            make_group({("0", 1)}),
            make_group({(0, 0)}, activity_area=[(0, 2), (0, 5)]),
        ]
        for group in groups:
            with self.subTest(group=vars(group)):
                with self.assertRaises(LevelScalingError):
                    scale_level_to_platform(make_game(), {"g": group}, 1, 6)

    def test_rejects_invalid_no_use_coordinates(self):
        with self.assertRaises(LevelScalingError):
            scale_level_to_platform(
                make_game(),
                {"g": make_group({(0, 0)})},
                1,
                6,
                floor_layout_coors_no_use={(0, 6)},
            )

    def test_rejects_accidental_second_scaling(self):
        game = make_game()
        groups = {"g": make_group({(0, 0)})}
        scale_level_to_platform(game, groups, 1, 6)

        with self.assertRaisesRegex(LevelScalingError, "already scaled"):
            scale_level_to_platform(game, groups, 1, 6)

    def test_rejects_reversed_zone_ranges_without_mutation(self):
        cases = [
            make_game(zone_row_from=1, zone_row_to=0),
            make_game(zone_col_from=4, zone_col_to=2),
        ]
        for game in cases:
            with self.subTest(zone=vars(game)):
                group = make_group({(0, 2)})
                game_before = copy.deepcopy(vars(game))
                group_before = copy.deepcopy(vars(group))

                with self.assertRaisesRegex(LevelScalingError, "zone"):
                    scale_level_to_platform(game, {"g": group}, 1, 6)

                self.assertEqual(vars(game), game_before)
                self.assertEqual(vars(group), group_before)

    def test_rejects_reused_scaled_group_without_mutating_any_input(self):
        reused_group = make_group({(0, 2)})
        scale_level_to_platform(make_game(), {"reused": reused_group}, 1, 6)

        fresh_game = make_game(col=6, zone_col_to=6)
        fresh_group = make_group(
            {(0, 5)},
            activity_area=[(0, 1), (0, 6)],
        )
        groups = {"fresh": fresh_group, "reused": reused_group}
        game_before = copy.deepcopy(vars(fresh_game))
        groups_before = {
            key: copy.deepcopy(vars(group)) for key, group in groups.items()
        }

        with self.assertRaisesRegex(LevelScalingError, "already scaled"):
            scale_level_to_platform(fresh_game, groups, 1, 7)

        self.assertEqual(vars(fresh_game), game_before)
        for key, group in groups.items():
            self.assertEqual(vars(group), groups_before[key])


if __name__ == "__main__":
    unittest.main()

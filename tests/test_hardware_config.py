import unittest

from hardware_config import (
    HardwareConfigError,
    parse_dimension,
    validate_com_info,
    validate_hardware_config,
    validate_platform_config,
)


class DimensionValidationTests(unittest.TestCase):
    def test_accepts_only_finite_positive_integer_valued_dimensions(self):
        for value, expected in ((1, 1), (1.0, 1), ("1", 1), ("6.0", 6)):
            with self.subTest(value=value):
                self.assertEqual(parse_dimension(value, "rows"), expected)

        for value in (
            True,
            False,
            1.5,
            "6.5",
            float("nan"),
            float("inf"),
            0,
            -1,
            "",
            None,
        ):
            with self.subTest(value=value):
                with self.assertRaises(HardwareConfigError):
                    parse_dimension(value, "rows")

    def test_platform_requires_exactly_six_enabled_hoops(self):
        self.assertEqual(
            validate_platform_config("1.0", 6.0, []),
            (1, 6, []),
        )
        for rows, cols, no_use in (
            (2, 6, []),
            (1, 5, []),
            (1, 6, [(0, 0)]),
            (1, 6, [(0, 5)]),
            (1, 6, [(1, 0)]),
            (1, 6, "not-a-coordinate-list"),
        ):
            with self.subTest(rows=rows, cols=cols, no_use=no_use):
                with self.assertRaisesRegex(HardwareConfigError, "Hoops hardware"):
                    validate_platform_config(rows, cols, no_use)


class LayoutValidationTests(unittest.TestCase):
    def test_accepts_only_strict_supported_layout_types(self):
        for layout in range(8):
            with self.subTest(layout=layout):
                validated = validate_hardware_config(1, 6, [], layout)
                self.assertEqual(validated["layout_type"], layout)

        for layout in (True, -1, 8, 1.5, "1.5", float("nan"), None):
            with self.subTest(layout=layout):
                with self.assertRaisesRegex(HardwareConfigError, "layout"):
                    validate_hardware_config(1, 6, [], layout)


class ComValidationTests(unittest.TestCase):
    def test_accepts_ranges_using_driver_inclusive_numbering(self):
        self.assertEqual(
            validate_com_info(
                [
                    ["COM3", "1", 2, "floor"],
                    ["COM4", 3.0, "6.0"],
                ]
            ),
            [
                ["COM3", 1, 2, "floor"],
                ["COM4", 3, 6],
            ],
        )

    def test_rejects_malformed_partial_duplicate_and_out_of_range_coverage(self):
        invalid = (
            [],
            [None],
            [["", 1, 6]],
            [["COM3", 1]],
            [["COM3", True, 6]],
            [["COM3", 1.5, 6]],
            [["COM3", 0, 6]],
            [["COM3", 1, 7]],
            [["COM3", 4, 3]],
            [["COM3", 1, 5]],
            [["COM3", 1, 4], ["COM4", 4, 6]],
            [["COM3", 1, 6], ["COM3", 1, 6]],
        )
        for com_info in invalid:
            with self.subTest(com_info=com_info):
                with self.assertRaises(HardwareConfigError):
                    validate_com_info(com_info)

    def test_full_hardware_validation_normalizes_com_before_io(self):
        validated = validate_hardware_config(
            "1",
            "6.0",
            [],
            "7",
            [["COM3", "1", "6"]],
        )
        self.assertEqual(validated["rows"], 1)
        self.assertEqual(validated["cols"], 6)
        self.assertEqual(validated["layout_type"], 7)
        self.assertEqual(validated["com_info"], [["COM3", 1, 6]])


if __name__ == "__main__":
    unittest.main()

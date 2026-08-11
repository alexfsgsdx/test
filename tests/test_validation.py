"""Tests for product validation."""

from __future__ import annotations

import unittest

from product_validation import nearest_valid_speed, validate_kit_spec, valid_speeds
from ram_part_number import parse_natural_language, spec_from_form


class TestProductValidation(unittest.TestCase):
    def test_ddr5_4000_rejected(self):
        result = validate_kit_spec(
            sticks=2,
            total_gb=32,
            generation=5,
            speed_mts=4000,
            profile="both",
            per_stick_gb=16,
        )
        self.assertFalse(result.ok)
        self.assertTrue(any("4000" in e for e in result.errors))

    def test_ddr5_4800_allowed(self):
        result = validate_kit_spec(
            sticks=2,
            total_gb=32,
            generation=5,
            speed_mts=4800,
            profile="jedec",
            per_stick_gb=16,
        )
        self.assertTrue(result.ok)

    def test_invalid_speed_listed(self):
        speeds = valid_speeds(5)
        self.assertIn(6000, speeds)
        self.assertNotIn(4000, speeds)
        self.assertEqual(nearest_valid_speed(5, 4000), 4800)

    def test_spec_from_form_rejects_bad_speed(self):
        with self.assertRaises(ValueError) as ctx:
            spec_from_form(
                {
                    "sticks": 2,
                    "total_gb": 32,
                    "generation": 5,
                    "speed_mts": 4000,
                    "profile": "both",
                }
            )
        self.assertIn("4000", str(ctx.exception))

    def test_natural_language_ddr5_6000_ok(self):
        spec = parse_natural_language("2 sticks 32 gb total ddr5 speed 6000 both xmp and expo")
        spec.validate()


if __name__ == "__main__":
    unittest.main()

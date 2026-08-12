"""Tests for RAM timing detail generation."""

from __future__ import annotations

import unittest

from ram_timings import build_ram_details


class TestRamTimings(unittest.TestCase):
    def test_ddr5_jedec_table(self):
        details = build_ram_details(
            brand="adata",
            part_number="AD5U48008G-B",
            product_name="DDR5 4800 U-DIMM",
            sticks=1,
            per_stick_gb=8,
            total_gb=8,
            generation=5,
            speed_mts=4800,
            cas_latency=40,
            profiles=["jedec"],
            requested_profile="jedec",
        )
        self.assertEqual(details["primary_timings"]["cl"], 40)
        self.assertEqual(details["primary_timings"]["trcd"], 40)
        self.assertEqual(details["speed_tier"], "jedec")
        self.assertEqual(details["voltages"]["vdd"], 1.10)

    def test_ddr5_xmp_estimated(self):
        details = build_ram_details(
            brand="corsair",
            part_number="CMH32GX5M2B6400C32",
            product_name="VENGEANCE RGB 32GB DDR5 6400 CL32",
            sticks=2,
            per_stick_gb=16,
            total_gb=32,
            generation=5,
            speed_mts=6400,
            cas_latency=32,
            profiles=["xmp"],
            requested_profile="xmp",
            rgb=True,
        )
        self.assertEqual(details["primary_timings"]["cl"], 32)
        self.assertGreaterEqual(details["primary_timings"]["trcd"], 32)
        self.assertEqual(details["speed_tier"], "oc")
        self.assertGreaterEqual(details["voltages"]["vdd"], 1.30)
        self.assertIn("sections", details)
        self.assertGreaterEqual(len(details["sections"]), 5)

    def test_includes_spd_section(self):
        details = build_ram_details(
            brand="corsair",
            part_number="CMH32GX5M2B6400C32",
            product_name="VENGEANCE RGB",
            sticks=2,
            per_stick_gb=16,
            total_gb=32,
            generation=5,
            speed_mts=6400,
            cas_latency=32,
            profiles=["xmp"],
            requested_profile="xmp",
            spd_serials=[
                {
                    "stick_index": 1,
                    "serial_number": "0x00000000",
                    "encoding": "empty",
                    "module_unique_id": "0x029E0101260800000000",
                }
            ],
        )
        titles = [section["title"] for section in details["sections"]]
        self.assertIn("SPD programming", titles)


if __name__ == "__main__":
    unittest.main()

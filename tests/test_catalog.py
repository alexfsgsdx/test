"""Tests for catalog lookup."""

from __future__ import annotations

import unittest

from catalog import catalog_stats, load_catalog, lookup_catalog
from ram_part_number import generate_report, RamSpec


class TestCatalogLookup(unittest.TestCase):
    def test_catalog_loads(self):
        stats = catalog_stats()
        self.assertGreaterEqual(stats["product_count"], 1100)
        self.assertGreaterEqual(stats["brand_count"], 20)
        self.assertGreaterEqual(stats.get("ddr5_count", 0), 1100)

    def test_corsair_6000_xmp_match(self):
        matches = lookup_catalog(
            sticks=2,
            total_gb=32,
            generation=5,
            speed_mts=6000,
            profile="xmp",
            rgb=False,
        )
        self.assertIn("corsair", matches)
        parts = {p.part_number for p in matches["corsair"]}
        self.assertIn("CMK32GX5M2B6000C30", parts)

    def test_no_synthetic_when_not_in_catalog(self):
        matches = lookup_catalog(
            sticks=2,
            total_gb=32,
            generation=5,
            speed_mts=9200,
            profile="xmp",
            rgb=False,
        )
        self.assertEqual(matches, {})

    def test_generate_report_catalog_only(self):
        spec = RamSpec(
            sticks=2,
            total_gb=32,
            generation=5,
            speed_mts=6000,
            profile="xmp",
            rgb=False,
        )
        report = generate_report(spec)
        self.assertEqual(report["catalog"]["mode"], "catalog_only")
        self.assertGreater(report["catalog"]["matched_products"], 0)
        for brand_id, entries in report["brands"].items():
            for entry in entries:
                self.assertTrue(entry["catalog_confirmed"])
                self.assertTrue(entry["source_url"])

    def test_generate_report_rejects_unknown_config(self):
        spec = RamSpec(
            sticks=2,
            total_gb=32,
            generation=5,
            speed_mts=9200,
            profile="xmp",
            rgb=False,
        )
        with self.assertRaises(ValueError) as ctx:
            generate_report(spec)
        self.assertIn("No verified manufacturer catalog", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

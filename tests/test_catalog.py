"""Tests for catalog lookup."""

from __future__ import annotations

import unittest

from catalog import (
    catalog_stats,
    load_catalog,
    lookup_by_part_number,
    lookup_catalog,
    search_catalog,
)
from ram_part_number import generate_lookup_report, generate_report, RamSpec


class TestCatalogLookup(unittest.TestCase):
    def test_catalog_loads(self):
        stats = catalog_stats()
        self.assertGreaterEqual(stats["product_count"], 4000)
        self.assertGreaterEqual(stats["brand_count"], 20)
        self.assertGreaterEqual(stats.get("ddr5_count", 0), 2700)
        self.assertGreaterEqual(stats.get("ddr4_count", 0), 500)

    def test_all_ddr5_brands_represented(self):
        products = load_catalog()
        ddr5_brands = {p.brand for p in products if p.generation == 5}
        expected = {
            "adata", "apacer", "corsair", "crucial", "geil", "gskill", "hynix",
            "kingston", "klevv", "lexar", "micron", "mushkin", "oloy", "patriot",
            "pny", "samsung", "silicon_power", "teamgroup", "timetec", "vcolor", "xpg",
        }
        missing = expected - ddr5_brands
        self.assertFalse(missing, f"missing DDR5 brands: {sorted(missing)}")
        self.assertNotIn("ballistix", ddr5_brands)
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

    def test_ddr4_lookup(self):
        matches = lookup_catalog(
            sticks=2,
            total_gb=32,
            generation=4,
            speed_mts=3200,
            profile="xmp",
            rgb=False,
        )
        self.assertTrue(matches, "expected DDR4 catalog matches for 2x16 3200 XMP")
        combined = {p.part_number for brand in matches.values() for p in brand}
        self.assertTrue(
            any("3200" in pn or "32" in pn for pn in combined),
            f"expected 32GB DDR4-3200 kit in results, got: {sorted(combined)[:5]}",
        )

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
                self.assertIn("ram_details", entry)
                self.assertIn("primary_timings", entry["ram_details"])

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

    def test_lookup_by_part_number_exact(self):
        product = lookup_by_part_number("CMH32GX5M2B6400C32")
        self.assertIsNotNone(product)
        assert product is not None
        self.assertEqual(product.brand, "corsair")
        self.assertEqual(product.generation, 5)
        self.assertEqual(lookup_by_part_number("cmh32gx5m2b6400c32"), product)
        self.assertIsNone(lookup_by_part_number("NOT-A-REAL-SKU-99999"))

    def test_search_catalog_by_product_name(self):
        results = search_catalog("Vengeance RGB 6400", limit=10)
        self.assertTrue(results)
        self.assertTrue(any("6400" in p.part_number or "6400" in p.product_name for p in results))

    def test_search_catalog_by_part_prefix(self):
        results = search_catalog("CMK32GX5M2B", limit=10)
        self.assertTrue(results)
        self.assertTrue(all(p.part_number.upper().startswith("CMK32GX5M2B") for p in results))

    def test_generate_lookup_report_single_sku(self):
        report = generate_lookup_report("CMH32GX5M2B6400C32")
        self.assertEqual(report["catalog"]["mode"], "lookup")
        self.assertEqual(report["catalog"]["lookup_query"], "CMH32GX5M2B6400C32")
        self.assertEqual(report["catalog"]["matched_products"], 1)
        self.assertIn("corsair", report["brands"])
        self.assertEqual(
            report["brands"]["corsair"][0]["part_number"],
            "CMH32GX5M2B6400C32",
        )
        self.assertEqual(
            report["brands"]["corsair"][0]["spd_serials"][0]["serial_number"],
            "0x00000000",
        )
        self.assertIn("ram_details", report["brands"]["corsair"][0])
        self.assertEqual(
            report["brands"]["corsair"][0]["ram_details"]["primary_timings"]["cl"],
            32,
        )

    def test_generate_lookup_report_search(self):
        report = generate_lookup_report("CMH32GX5M2B6400")
        self.assertGreaterEqual(report["catalog"]["matched_products"], 1)
        self.assertEqual(report["catalog"]["lookup_query"], "CMH32GX5M2B6400")

    def test_generate_lookup_report_exact_only(self):
        with self.assertRaises(ValueError):
            generate_lookup_report("CMH32GX5M2B6400", exact_only=True)

    def test_generate_report_null_serial_only_ddr5(self):
        spec = RamSpec(
            sticks=2,
            total_gb=32,
            generation=5,
            speed_mts=6000,
            profile="xmp",
            rgb=False,
        )
        report = generate_report(spec, null_serial_only=True)
        self.assertTrue(report["catalog"]["null_serial_only"])
        brands = set(report["brands"].keys())
        self.assertIn("corsair", brands)
        self.assertNotIn("kingston", brands)
        for entries in report["brands"].values():
            for entry in entries:
                for serial in entry["spd_serials"]:
                    self.assertEqual(serial["serial_number"], "0x00000000")

    def test_generate_report_null_serial_only_excludes_programmed(self):
        spec = RamSpec(
            sticks=2,
            total_gb=32,
            generation=5,
            speed_mts=6000,
            profile="xmp",
            rgb=False,
        )
        full = generate_report(spec)
        self.assertIn("kingston", full["brands"])
        filtered = generate_report(spec, null_serial_only=True)
        self.assertNotIn("kingston", filtered["brands"])


if __name__ == "__main__":
    unittest.main()

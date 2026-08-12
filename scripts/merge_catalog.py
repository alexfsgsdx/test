#!/usr/bin/env python3
"""Merge scraped DDR4 + DDR5 SKU files into data/catalog.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_catalog import VERIFIED, dedupe, norm_ecc, norm_ff, norm_gen, norm_profiles  # noqa: E402

OUT = ROOT / "data" / "catalog.json"
DOCS = ROOT / "docs" / "catalog.json"

DDR4_SOURCE_PRIORITY = [
    "corsair_ddr4.json",
    "gskill_ddr4.json",
    "teamgroup_ddr4.json",
    "kingston_ddr4.json",
    "crucial_ddr4.json",
    "patriot_ddr4.json",
    "xpg_ddr4.json",
    "pny_ddr4.json",
    "ballistix_ddr4.json",
    "oloy_ddr4.json",
    "geil_ddr4.json",
    "mushkin_ddr4.json",
    "silicon_power_ddr4.json",
    "adata_ddr4.json",
    "micron_ddr4.json",
    "misc_ddr4.json",
]

DDR5_SOURCE_PRIORITY = [
    "corsair_ddr5.json",
    "gskill_ddr5.json",
    "teamgroup_ddr5.json",
    "kingston_ddr5.json",
    "crucial_ddr5.json",
    "patriot_ddr5.json",
    "xpg_ddr5.json",
    "pny_ddr5.json",
    "oloy_ddr5.json",
    "geil_ddr5.json",
    "mushkin_ddr5.json",
    "silicon_power_ddr5.json",
    "klevv_ddr5.json",
    "lexar_ddr5.json",
    "apacer_ddr5.json",
    "vcolor_ddr5.json",
    "timetec_ddr5.json",
    "adata_ddr5.json",
    "samsung_ddr5.json",
    "hynix_ddr5.json",
    "micron_ddr5.json",
    "misc_ddr5.json",
    "ddr5_skus.json",
    "kingston_gskill_ddr5_compact.json",
]

BRAND_MAP: dict[str, str] = {
    "crucial": "crucial",
    "micron/crucial": "micron",
    "micron": "micron",
    "teamgroup t-force": "teamgroup",
    "teamgroup": "teamgroup",
    "patriot viper": "patriot",
    "patriot": "patriot",
    "xpg": "xpg",
    "pny": "pny",
    "oloy": "oloy",
    "geil": "geil",
    "mushkin": "mushkin",
    "silicon power": "silicon_power",
    "klevv": "klevv",
    "lexar": "lexar",
    "apacer": "apacer",
    "v-color": "vcolor",
    "vcolor": "vcolor",
    "timetec": "timetec",
    "adata": "adata",
    "samsung": "samsung",
    "sk hynix": "hynix",
    "hynix": "hynix",
    "kingston": "kingston",
    "gskill": "gskill",
    "g.skill": "gskill",
    "corsair": "corsair",
    "ballistix": "ballistix",
}


def norm_brand(raw: str) -> str:
    key = raw.strip().lower().replace(".", "")
    if key in BRAND_MAP:
        return BRAND_MAP[key]
    for alias, brand_id in BRAND_MAP.items():
        if alias in key or key in alias:
            return brand_id
    slug = key.replace(" ", "_").replace("-", "_")
    return slug


def load_json_array(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("products", [])


def raw_to_entry(raw: dict) -> dict | None:
    brand = norm_brand(str(raw.get("brand", "")))
    part = str(raw.get("part_number", "")).strip()
    if not brand or not part:
        return None

    sticks = int(raw.get("sticks", 1))
    per_stick_gb = int(raw.get("per_stick_gb", 0))
    if per_stick_gb <= 0:
        total = int(raw.get("total_gb", 0))
        if total > 0 and sticks > 0:
            per_stick_gb = total // sticks
    if per_stick_gb <= 0:
        return None

    generation = raw.get("generation")
    if generation is None:
        generation = 5 if raw.get("speed_mts", 0) >= 4800 else 4
    speed_mts = int(raw.get("speed_mts", 0))
    cas_latency = int(raw.get("cas_latency", 0))
    if speed_mts <= 0 or cas_latency <= 0:
        return None

    profiles = raw.get("profiles", ["jedec"])
    rgb = bool(raw.get("rgb", False))
    form_factor = norm_ff(str(raw.get("form_factor", "dimm")))
    ecc = norm_ecc(raw.get("ecc", False))
    source_url = str(raw.get("source_url", "")).strip()
    product_name = str(raw.get("product_name", part)).strip()

    return {
        "brand": brand,
        "part_number": part.upper(),
        "product_name": product_name,
        "sticks": sticks,
        "per_stick_gb": per_stick_gb,
        "total_gb": sticks * per_stick_gb,
        "generation": norm_gen(generation),
        "speed_mts": speed_mts,
        "cas_latency": cas_latency,
        "profiles": norm_profiles(profiles),
        "rgb": rgb,
        "form_factor": form_factor,
        "ecc": ecc,
        "source_url": source_url,
        "source": "manufacturer",
        "verified": VERIFIED,
    }


def discover_sources(priority: list[str], glob_suffix: str) -> list[Path]:
    data_dir = ROOT / "data"
    ordered: list[Path] = []
    seen: set[str] = set()
    for name in priority:
        path = data_dir / name
        if path.exists():
            ordered.append(path)
            seen.add(name)
    for path in sorted(data_dir.glob(glob_suffix)):
        if path.name in seen or path.name == "catalog.json":
            continue
        ordered.append(path)
        seen.add(path.name)
    return ordered


def load_generation_from_sources(generation: int, priority: list[str], glob_pat: str) -> list[dict]:
    products: list[dict] = []
    for path in discover_sources(priority, glob_pat):
        raw_items = load_json_array(path)
        converted = 0
        for raw in raw_items:
            item = raw_to_entry(raw)
            if item and item["generation"] == generation:
                products.append(item)
                converted += 1
        print(f"  {path.name}: {converted} DDR{generation} SKUs")
    return products


def main() -> None:
    print("Loading DDR4 from scraped sources...")
    ddr4 = load_generation_from_sources(4, DDR4_SOURCE_PRIORITY, "*ddr4*.json")

    print("Loading DDR5 from scraped sources...")
    ddr5 = load_generation_from_sources(5, DDR5_SOURCE_PRIORITY, "*ddr5*.json")

    products = dedupe([*ddr4, *ddr5])
    ddr4_count = sum(1 for p in products if p["generation"] == 4)
    ddr5_count = sum(1 for p in products if p["generation"] == 5)
    brands = sorted({p["brand"] for p in products})

    by_brand: dict[str, int] = {}
    ddr4_by_brand: dict[str, int] = {}
    ddr5_by_brand: dict[str, int] = {}
    for p in products:
        by_brand[p["brand"]] = by_brand.get(p["brand"], 0) + 1
        if p["generation"] == 4:
            ddr4_by_brand[p["brand"]] = ddr4_by_brand.get(p["brand"], 0) + 1
        else:
            ddr5_by_brand[p["brand"]] = ddr5_by_brand.get(p["brand"], 0) + 1

    payload = {
        "version": 2,
        "updated": VERIFIED,
        "description": "Verified manufacturer catalog SKUs. Only products listed here are returned by the generator.",
        "products": products,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    OUT.write_text(text, encoding="utf-8")
    DOCS.write_text(text, encoding="utf-8")

    print(f"\nWrote {len(products)} total products ({ddr5_count} DDR5 + {ddr4_count} DDR4)")
    print(f"Across {len(brands)} brands")
    for brand in brands:
        print(
            f"  {brand}: {ddr4_by_brand.get(brand, 0)} DDR4 + "
            f"{ddr5_by_brand.get(brand, 0)} DDR5 = {by_brand[brand]} total"
        )


if __name__ == "__main__":
    main()

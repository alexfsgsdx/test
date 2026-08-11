#!/usr/bin/env python3
"""Merge scraped DDR5 SKU files into data/catalog.json, preserving DDR4 entries."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_catalog import VERIFIED, dedupe, entry, norm_ecc, norm_ff, norm_gen, norm_profiles  # noqa: E402

OUT = ROOT / "data" / "catalog.json"
DOCS = ROOT / "docs" / "catalog.json"
CATALOG = ROOT / "data" / "catalog.json"

SOURCES: list[tuple[Path, str]] = [
    (ROOT / "data" / "kingston_gskill_ddr5_compact.json", "array"),
    (ROOT / "data" / "corsair_ddr5.json", "array"),
    (ROOT / "data" / "ddr5_skus.json", "array"),
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

    generation = raw.get("generation", 5)
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


def load_ddr4_products() -> list[dict]:
    if not CATALOG.exists():
        return []
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    return [p for p in payload.get("products", []) if p.get("generation") == 4]


def load_ddr5_from_sources() -> list[dict]:
    products: list[dict] = []
    for path, _kind in SOURCES:
        if not path.exists():
            print(f"  skip missing: {path.name}")
            continue
        raw_items = load_json_array(path)
        converted = 0
        for raw in raw_items:
            item = raw_to_entry(raw)
            if item and item["generation"] == 5:
                products.append(item)
                converted += 1
        print(f"  {path.name}: {converted} DDR5 SKUs")
    return products


def main() -> None:
    print("Loading DDR4 from existing catalog...")
    ddr4 = load_ddr4_products()
    print(f"  kept {len(ddr4)} DDR4 products")

    print("Loading DDR5 from scraped sources...")
    ddr5 = load_ddr5_from_sources()

    products = dedupe([*ddr4, *ddr5])
    ddr5_count = sum(1 for p in products if p["generation"] == 5)
    ddr4_count = sum(1 for p in products if p["generation"] == 4)
    brands = sorted({p["brand"] for p in products})

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
    print(f"Across {len(brands)} brands: {', '.join(brands)}")


if __name__ == "__main__":
    main()

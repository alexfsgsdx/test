#!/usr/bin/env python3
"""Scrape all G.Skill DDR5 SKUs from gskill.com specification sitemap."""

from __future__ import annotations

import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scrape_utils import fetch, parse_gskill_spec, throttle, write_json  # noqa: E402

OUT = ROOT / "data" / "gskill_ddr5.json"
SITEMAP = "https://www.gskill.com/sitemap.xml"


def collect_spec_urls() -> list[str]:
    xml = fetch(SITEMAP, timeout=60)
    urls = re.findall(r"<loc>([^<]+)</loc>", xml)
    return [u for u in urls if "/specification/" in u and "F5-" in u]


def scrape_one(url: str) -> dict | None:
    try:
        html = fetch(url, timeout=25)
        return parse_gskill_spec(html, url)
    except Exception:
        return None


def main() -> None:
    urls = collect_spec_urls()
    print(f"Found {len(urls)} G.Skill F5 specification URLs")

    products: list[dict] = []
    seen: set[str] = set()

    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(scrape_one, u): u for u in urls}
        for i, fut in enumerate(as_completed(futures), 1):
            item = fut.result()
            if not item:
                continue
            key = item["part_number"].upper()
            if key in seen:
                continue
            seen.add(key)
            products.append(item)
            if i % 100 == 0:
                print(f"  processed {i}/{len(urls)}, unique {len(products)}")

    products.sort(key=lambda p: p["part_number"])
    write_json(OUT, products)
    print(f"Wrote {len(products)} G.Skill DDR5 SKUs -> {OUT}")


if __name__ == "__main__":
    main()

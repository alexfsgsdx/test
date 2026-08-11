#!/usr/bin/env python3
"""Scrape TeamGroup DDR5 SKUs from compare page and product detail pages."""

from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scrape_utils import decode_teamgroup_part, fetch, write_json  # noqa: E402

OUT = ROOT / "data" / "teamgroup_ddr5.json"
COMPARE = "https://www.teamgroupinc.com/en/product/compare/memory/"
SITEMAP = "https://www.teamgroupinc.com/sitemap.xml"
PART_RE = re.compile(
    r"(?:FF|FL|FLE|CTC|CTM|CTCE|CTCC|CTCM|CTCMD|TLZ)[A-Z0-9]{8,}",
    re.I,
)


def collect_parts(html: str) -> set[str]:
    parts: set[str] = set()
    best: list[str] = []
    for m in re.finditer(r"(\[[\s\S]{1000,200000}?\])", html):
        try:
            arr = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(arr, list):
            continue
        strings = [x for x in arr if isinstance(x, str) and PART_RE.search(x)]
        if len(strings) > len(best):
            best = strings
    if best:
        parts.update(x.upper() for x in best)
    parts.update(m.group(0).upper() for m in PART_RE.finditer(html))
    return {p for p in parts if re.search(r"\d{3,4}G\d{4}HC", p, re.I)}


def collect_detail_urls() -> dict[str, str]:
    mapping: dict[str, str] = {}
    xml = fetch(SITEMAP, timeout=30)
    for url in re.findall(r"<loc>([^<]+)</loc>", xml):
        if "product-detail/memory" not in url:
            continue
        m = PART_RE.search(url)
        if m:
            mapping[m.group(0).upper()] = url
    html = fetch(COMPARE, timeout=40)
    for url in re.findall(r"https://www\.teamgroupinc\.com/en/product-detail/memory/[^\s\"']+", html):
        m = PART_RE.search(url)
        if m:
            mapping[m.group(0).upper()] = url
    return mapping


def title_from_url(url: str) -> str:
    try:
        html = fetch(url, timeout=25)
        m = re.search(r"<title>([^<]+)</title>", html, re.I)
        if m:
            return re.sub(r"\s*-\s*TEAMGROUP\s*$", "", m.group(1), flags=re.I).strip()
    except Exception:
        pass
    return ""


def main() -> None:
    print("Loading TeamGroup compare page...")
    html = fetch(COMPARE, timeout=40)
    parts = collect_parts(html)
    print(f"Found {len(parts)} part numbers on compare page")

    url_map = collect_detail_urls()
    print(f"Mapped {len(url_map)} part -> URL entries")

    products: list[dict] = []
    parts_sorted = sorted(parts)

    def build(part: str) -> dict | None:
        source = url_map.get(part, "https://www.teamgroupinc.com/en/product/compare/memory/")
        item = decode_teamgroup_part(part, part)
        if not item:
            return None
        item["source_url"] = source
        # Infer RGB from part line prefixes commonly used by TeamGroup
        if any(tag in part for tag in ("ARB", "RGD", "RGB")):
            item["rgb"] = True
        return item

    with ThreadPoolExecutor(max_workers=1) as pool:
        for item in pool.map(build, parts_sorted):
            if item:
                products.append(item)

    products.sort(key=lambda p: p["part_number"])
    write_json(OUT, products)
    print(f"Wrote {len(products)} TeamGroup DDR5 SKUs -> {OUT}")


if __name__ == "__main__":
    main()

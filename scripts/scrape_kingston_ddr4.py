#!/usr/bin/env python3
"""Scrape verified Kingston Fury / desktop DDR4 SKUs from kingston.com datasheets."""

from __future__ import annotations

import io
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pypdf import PdfReader  # noqa: E402

from decode_ddr4_parts import decode_kingston  # noqa: E402
from scrape_utils import fetch, fetch_bytes, write_json  # noqa: E402

OUT = ROOT / "data" / "kingston_ddr4.json"
DATASHEET = "https://www.kingston.com/datasheets/{part}.pdf"
GOBeyond = "https://www.gobeyond.net/products/manufacturers/KINGSTON/DDR4.html?page={page}"
SEED_FILES = (ROOT / "data" / "catalog.json",)

PREFIXES = ("KF4", "KVR2", "KVR3", "KCP4")


def is_ddr4_part(part: str) -> bool:
    up = part.upper()
    if up.startswith("KF4"):
        return True
    if up.startswith("KVR") and len(up) >= 5 and up[3:5].isdigit() and int(up[3:5]) < 48:
        return True
    if up.startswith("KCP4"):
        return True
    return False


def load_seed_catalog() -> dict[str, str]:
    catalog: dict[str, str] = {}
    for path in SEED_FILES:
        if not path.exists():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw.get("products", raw) if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            continue
        for row in items:
            if not isinstance(row, dict) or row.get("brand") != "kingston":
                continue
            if row.get("generation", 5) != 4:
                continue
            part = str(row.get("part_number", "")).upper()
            if is_ddr4_part(part):
                catalog[part] = str(row.get("product_name", ""))
    return catalog


def gobeyond_catalog(max_pages: int = 40) -> dict[str, str]:
    catalog: dict[str, str] = {}
    for page in range(1, max_pages + 1):
        try:
            html = fetch(GOBeyond.format(page=page), timeout=30)
        except Exception:
            break
        cards = re.split(r'<h3 class="text-lg font-semibold', html)
        if len(cards) <= 1:
            break
        page_hits = 0
        for card in cards[1:]:
            title_m = re.search(
                r'<h3 class="text-lg font-semibold[^"]*"[^>]*>\s*<a[^>]*>\s*([^<]+?)\s*</a>',
                card,
                re.S,
            )
            part_m = re.search(
                r"Manufacturer Part Number:</span>\s*<span[^>]*>([A-Z0-9/-]+)</span>",
                card,
                re.I,
            )
            if part_m:
                part = part_m.group(1).upper().replace(" ", "")
                if not is_ddr4_part(part):
                    continue
                name = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""
                catalog[part] = name
                page_hits += 1
        if page_hits == 0:
            break
        time.sleep(0.15)
    return catalog


def parse_pdf(text: str, part: str) -> dict | None:
    if part not in text:
        return None
    speed_m = re.search(rf"{re.escape(part)}[\s\S]{{0,400}}?DDR4-(\d{{4}})", text)
    if not speed_m:
        speed_m = re.search(r"DDR4-(\d{4})", text)
    if not speed_m:
        return None
    speed_mts = int(speed_m.group(1))
    cl_m = re.search(rf"DDR4-{speed_mts}\s+CL(\d{{2,3}})", text)
    if not cl_m:
        cl_m = re.search(r"CL(\d{2,3})", text)
    if not cl_m:
        return None
    item = decode_kingston(part, product_name=f"Kingston DDR4 {speed_mts} CL{cl_m.group(1)}")
    if item:
        item["speed_mts"] = speed_mts
        item["cas_latency"] = int(cl_m.group(1))
    return item


def fetch_pdf_entry(part: str, product_name: str = "") -> dict | None:
    url = DATASHEET.format(part=part.replace("/", "%2F"))
    try:
        raw = fetch_bytes(url, timeout=25, retries=2)
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
        item = parse_pdf(text, part)
        if item:
            if product_name:
                item["product_name"] = product_name[:120]
            item["source_url"] = f"https://www.kingston.com/en/memory/search?partid={part}"
            return item
    except Exception:
        pass
    item = decode_kingston(part, product_name=product_name)
    if item:
        item["source_url"] = f"https://www.kingston.com/en/memory/search?partid={part}"
    return item


def main() -> None:
    catalog = load_seed_catalog()
    print(f"Seed catalog: {len(catalog)} Kingston DDR4 parts")
    gobeyond = gobeyond_catalog()
    print(f"Gobeyond catalog: {len(gobeyond)} parts")
    catalog.update(gobeyond)

    products: list[dict] = []
    seen: set[str] = set()
    parts = sorted(catalog)

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch_pdf_entry, p, catalog[p]): p for p in parts}
        for i, fut in enumerate(as_completed(futures), 1):
            part = futures[fut]
            if i % 25 == 0:
                print(f"  processed {i}/{len(parts)}")
            try:
                item = fut.result()
            except Exception:
                item = None
            if not item:
                item = decode_kingston(part, catalog[part])
            if not item:
                continue
            pn = item["part_number"].upper()
            if pn in seen:
                continue
            seen.add(pn)
            products.append(item)
            time.sleep(0.02)

    products.sort(key=lambda p: p["part_number"])
    write_json(OUT, products)
    print(f"Wrote {len(products)} Kingston DDR4 SKUs -> {OUT}")


if __name__ == "__main__":
    main()

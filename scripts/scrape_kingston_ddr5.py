#!/usr/bin/env python3
"""Scrape verified Kingston Fury / desktop DDR5 SKUs from kingston.com datasheets."""

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

from scrape_utils import (  # noqa: E402
    decode_kingston_part,
    fetch,
    fetch_bytes,
    parse_kingston_pdf,
    write_json,
)

OUT = ROOT / "data" / "kingston_ddr5.json"
DATASHEET = "https://www.kingston.com/datasheets/{part}.pdf"
SEARCH_URL = "https://www.kingston.com/en/memory/search?partid={part}"
GOBeyond = "https://www.gobeyond.net/products/manufacturers/KINGSTON/DDR5.html?page={page}"
SEED_FILES = (
    ROOT / "data" / "kingston_gskill_ddr5_compact.json",
    ROOT / "data" / "catalog.json",
)

PREFIXES = ("KF5", "KVR", "KSM")


def is_ddr5_part(part: str) -> bool:
    up = part.upper()
    if up.startswith("KF5"):
        return True
    if up.startswith("KVR") and len(up) >= 5 and up[3:5].isdigit() and int(up[3:5]) >= 48:
        return True
    if up.startswith("KSM") and up[3:5].isdigit() and int(up[3:5]) >= 48:
        return True
    return False

FEATURE_TOKENS = (
    "BB", "BBA", "BBE", "BBEA", "BBE2A", "BWE", "BWA", "BWEA",
    "R36RB", "RS", "RSA", "RSK", "RW", "RWA", "RH",
)
CAPACITIES = (8, 16, 24, 32, 48, 64, 96, 128, 256)
KITS = ("", "K2", "K4", "K8")


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
            if row.get("generation", 5) != 5:
                continue
            part = str(row.get("part_number", "")).upper()
            if part.startswith(PREFIXES) and is_ddr5_part(part):
                catalog[part] = str(row.get("product_name", ""))
    return catalog


def gobeyond_catalog(max_pages: int = 60) -> dict[str, str]:
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
                r"Manufacturer Part Number:</span>\s*<span[^>]*>([A-Z0-9-]+)</span>",
                card,
                re.I,
            )
            if part_m:
                part = part_m.group(1).upper()
                name = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""
                catalog[part] = name
                page_hits += 1
        if page_hits == 0:
            break
        time.sleep(0.15)
    return catalog


def expand_from_verified(verified: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    stems: set[str] = set()
    for part in verified:
        m = re.match(r"^(KF5\d{2}[A-Z]?C\d{2}[A-Z0-9]+?)(K\d)?-(\d+)$", part, re.I)
        if m:
            stems.add(m.group(1).upper())
    for stem in stems:
        for kit in KITS:
            for cap in CAPACITIES:
                if kit == "K4" and cap < 32:
                    continue
                if kit == "K8" and cap < 64:
                    continue
                if not kit and cap > 64:
                    continue
                out.setdefault(f"{stem}{kit}-{cap}", "")
    return out


def expand_systematic(tokens: set[str], verified: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    speeds: set[int] = set()
    latencies: set[int] = set()
    caps: set[int] = set()
    for part in verified:
        m = re.match(r"KF5(?P<speed>\d{2})[A-Z]?C(?P<cl>\d{2})", part, re.I)
        if m:
            speeds.add(int(m.group("speed")))
            latencies.add(int(m.group("cl")))
        tail = re.search(r"-(\d+)$", part)
        if tail:
            caps.add(int(tail.group(1)))
    if not speeds:
        return out
    for speed in sorted(speeds):
        for cl in sorted(latencies):
            for feat in tokens:
                for kit in ("", "K2", "K4"):
                    for cap in sorted(caps):
                        if kit == "K4" and cap < 32:
                            continue
                        if not kit and cap > 64:
                            continue
                        out[f"KF5{speed}C{cl:02d}{feat}{kit}-{cap}"] = ""
    return out


def feature_tokens_from(parts: dict[str, str]) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        m = re.match(r"KF5\d{2}[A-Z]?C\d{2}([A-Z0-9]+?)(?:K\d)?-\d+", part, re.I)
        if not m:
            continue
        token = m.group(1).upper()
        for known in FEATURE_TOKENS:
            if token == known or token.startswith(known):
                tokens.add(known)
    return tokens


def kingston_rate_limited() -> bool:
    url = DATASHEET.format(part="KF560C30BBK2-32")
    req = __import__("urllib.request").request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with __import__("urllib.request").request.urlopen(req, timeout=15) as resp:
            return not resp.read(5).startswith(b"%PDF")
    except Exception as exc:
        return "429" in str(exc)


def pdf_exists(part: str) -> bool:
    try:
        raw = fetch_bytes(DATASHEET.format(part=part), timeout=20, retries=1)
        return raw.startswith(b"%PDF")
    except Exception as exc:
        if "429" in str(exc):
            raise exc
        return False


def scrape_pdf(part: str) -> dict | None:
    try:
        raw = fetch_bytes(DATASHEET.format(part=part), timeout=30, retries=2)
        if not raw.startswith(b"%PDF"):
            return None
        text = "".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(raw)).pages)
        return parse_kingston_pdf(text, part)
    except Exception:
        return None


def normalize_profiles(profiles: list[str]) -> list[str]:
    has_xmp = "xmp" in profiles
    has_expo = "expo" in profiles
    if has_xmp and has_expo:
        return ["both"]
    if has_expo:
        return ["expo"]
    if has_xmp:
        return ["xmp"]
    return ["jedec"]


def finalize(item: dict, product_name: str = "") -> dict:
    item["part_number"] = item["part_number"].upper()
    item["profiles"] = normalize_profiles(item.get("profiles", ["jedec"]))
    if product_name:
        item["product_name"] = product_name[:120]
    item["source_url"] = SEARCH_URL.format(part=item["part_number"])
    return item


def discover_verified_parts(candidates: dict[str, str], workers: int = 1) -> dict[str, str]:
    parts = sorted(candidates)
    verified: dict[str, str] = {}
    print(f"Probing {len(parts)} candidate PDFs on kingston.com ...")

    def probe(part: str) -> tuple[str, bool]:
        time.sleep(0.8)
        try:
            return part, pdf_exists(part)
        except Exception as exc:
            if "429" in str(exc):
                raise exc
            return part, False

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(probe, p): p for p in parts}
            for i, fut in enumerate(as_completed(futures), 1):
                part, ok = fut.result()
                if ok:
                    verified[part] = candidates.get(part, "")
                if i % 50 == 0:
                    print(f"  probed {i}/{len(parts)}, verified {len(verified)}")
    except Exception as exc:
        if "429" in str(exc):
            print("  rate-limited during probe; keeping partial results")
        else:
            raise
    print(f"Verified {len(verified)} real part numbers via kingston.com datasheets")
    return verified


def main() -> None:
    seed = load_seed_catalog()
    retailer = gobeyond_catalog()
    merged = {**seed, **retailer}
    print(f"Seed catalog: {len(seed)}, gobeyond: {len(retailer)}, merged: {len(merged)}")

    limited = kingston_rate_limited()
    if limited:
        print("Kingston datasheets rate-limited; using distributor/catalog verified MPNs")
        verified = {p: n for p, n in merged.items() if is_ddr5_part(p)}
    else:
        verified = discover_verified_parts(merged, workers=1)
        for extra in (
            expand_from_verified(verified),
            expand_systematic(feature_tokens_from(verified), verified),
        ):
            new = {p: n for p, n in extra.items() if p not in verified}
            if new and not kingston_rate_limited():
                verified.update(discover_verified_parts(new, workers=1))
            elif new:
                break

    products: list[dict] = []
    seen: set[str] = set()
    for part in sorted(verified):
        if not part.startswith(PREFIXES) or not is_ddr5_part(part):
            continue
        name = verified.get(part, "")
        item = scrape_pdf(part) if not limited else None
        if not item:
            item = decode_kingston_part(part, name)
        if not item:
            continue
        item = finalize(item, name)
        key = item["part_number"]
        if key in seen:
            continue
        seen.add(key)
        products.append(item)

    products.sort(key=lambda p: p["part_number"])
    write_json(OUT, products)
    print(f"Wrote {len(products)} Kingston DDR5 SKUs -> {OUT}")


if __name__ == "__main__":
    main()

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

PART_RE = re.compile(r"\b(KF5[A-Z0-9-]{4,}|KVR5[A-Z0-9-]{4,}|KSM5[A-Z0-9-]{4,})\b")
PREFIXES = ("KF5", "KVR5", "KSM5")

# Observed Kingston Fury DDR5 feature / series tokens (from kingston.com + distributor catalogs).
FEATURE_TOKENS = (
    "BB",
    "BBA",
    "BBE",
    "BBEA",
    "BBE2A",
    "BWE",
    "BWA",
    "BWEA",
    "R36RB",
    "RS",
    "RSA",
    "RSK",
    "RW",
    "RWA",
    "RH",
)
SPEEDS = tuple(range(48, 81))  # 4800–8000 MT/s encoded as 48–80
LATENCIES = (28, 30, 32, 34, 36, 38, 40, 42, 46, 48)
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
            gen = row.get("generation", 5)
            if gen != 5:
                continue
            part = str(row.get("part_number", "")).upper()
            if part.startswith(PREFIXES):
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
            title_m = re.search(r'>([^<]+)</h3>', card)
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
    """Generate capacity/kit neighbors from confirmed part-number stems."""
    out = dict(verified)
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


def expand_systematic(known_features: set[str], verified: dict[str, str]) -> dict[str, str]:
    """Sweep datasheet namespace for observed speed/CL/feature combinations."""
    out: dict[str, str] = {}
    tokens = known_features or set(FEATURE_TOKENS)

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
        speeds = {48, 52, 56, 60, 64, 68, 72, 80}
    if not latencies:
        latencies = set(LATENCIES)
    if not caps:
        caps = set(CAPACITIES)

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
    return tokens or set(FEATURE_TOKENS)


def pdf_exists(part: str) -> bool:
    url = DATASHEET.format(part=part)
    try:
        raw = fetch_bytes(url, timeout=20, retries=2)
        return raw.startswith(b"%PDF")
    except Exception:
        return False


def scrape_pdf(part: str) -> dict | None:
    url = DATASHEET.format(part=part)
    try:
        raw = fetch_bytes(url, timeout=30, retries=3)
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
    """Return parts whose kingston.com datasheet PDF exists."""
    parts = sorted(candidates)
    verified: dict[str, str] = {}
    print(f"Probing {len(parts)} candidate PDFs on kingston.com ...")

    def probe(part: str) -> tuple[str, bool]:
        time.sleep(0.8)
        return part, pdf_exists(part)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(probe, p): p for p in parts}
        for i, fut in enumerate(as_completed(futures), 1):
            part, ok = fut.result()
            if ok:
                verified[part] = candidates.get(part, "")
            if i % 50 == 0:
                print(f"  probed {i}/{len(parts)}, verified {len(verified)}")
    print(f"Verified {len(verified)} real part numbers via kingston.com datasheets")
    return verified


def main() -> None:
    seed = load_seed_catalog()
    retailer = gobeyond_catalog()
    merged = {**seed, **retailer}
    print(f"Seed catalog: {len(seed)}, gobeyond: {len(retailer)}, merged: {len(merged)}")

    # Phase 1 — known distributor / catalog part numbers.
    verified = discover_verified_parts(merged, workers=1)

    # Phase 2 — expand capacity/kit variants from confirmed stems.
    round2 = expand_from_verified(verified)
    new2 = {p: n for p, n in round2.items() if p not in verified}
    if new2:
        verified.update(discover_verified_parts(new2, workers=1))

    # Phase 3 — systematic sweep using feature tokens seen in verified parts.
    tokens = feature_tokens_from(verified)
    round3 = expand_systematic(tokens, verified)
    new3 = {p: n for p, n in round3.items() if p not in verified}
    if new3:
        verified.update(discover_verified_parts(new3, workers=1))

    # Phase 4 — ValueRAM DDR5 on kingston.com memory finder.
    valueram: dict[str, str] = {}
    for speed in (48, 52, 56, 60, 64):
        for cap in (8, 16, 32, 64):
            for pat in (
                f"KVR5{speed}U40BS6-{cap}",
                f"KVR5{speed}U42BS6-{cap}",
                f"KVR5{speed}U46BS8-{cap}",
                f"KVR5{speed}U46BD8-{cap}",
                f"KVR5{speed}U46BS6-{cap}",
            ):
                valueram[pat] = ""
    new4 = {p: n for p, n in valueram.items() if p not in verified}
    if new4:
        verified.update(discover_verified_parts(new4, workers=1))

    products: list[dict] = []
    seen: set[str] = set()

    for part in sorted(verified):
        name = verified.get(part, "")
        item = scrape_pdf(part)
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
        time.sleep(0.25)

    products.sort(key=lambda p: (p["part_number"]))
    write_json(OUT, products)
    print(f"Wrote {len(products)} Kingston DDR5 SKUs -> {OUT}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Scrape verified Corsair DDR5 desktop memory SKUs from corsair.com."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "corsair_ddr5.json"
GRAPHQL = "https://www.corsair.com/graphql"
SITEMAP = "https://www.corsair.com/us-sitemap-products-1.xml"
BASE_URL = "https://www.corsair.com/us/en/p/memory"

HEADERS = {
    "Content-Type": "application/json",
    "x-pylot-backend": "corsair",
    "Store": "default",
    "sid": "corsair-ddr5-scraper",
    "locale": "en",
    "region": "US",
}

PRODUCTS_QUERY = """
query products($searchCriteria: [SearchCriteriaInput!]!, $pageSize: Int = 100, $currentPage: Int = 1, $sort: ProductAttributeSortInput = {}) {
  products(searchCriteria: $searchCriteria, pageSize: $pageSize, currentPage: $currentPage, sort: $sort) {
    total_count
    page_info { current_page total_pages }
    items { sku name url_key tech_specs { code value } }
  }
}
"""

PART_RE = re.compile(
    r"^CM[A-Z0-9]*GX5M(?P<sticks>\d)[A-Z](?P<speed>\d{4,5})(?P<profile>[BCZ])(?P<cl>\d{2})",
    re.I,
)
MEMORY_SIZE_RE = re.compile(
    r"(?P<total>\d+)\s*GB\s*\(\s*(?P<sticks>\d+)\s*x\s*(?P<per>\d+)\s*GB\s*\)",
    re.I,
)
SINGLE_SIZE_RE = re.compile(r"(?P<total>\d+)\s*GB(?!\s*\()", re.I)


def gql(query: str, variables: dict, query_name: str = "products") -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        GRAPHQL,
        data=body,
        headers={**HEADERS, "x-pylot-query": query_name},
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.load(resp)
            if payload.get("errors"):
                raise RuntimeError(str(payload["errors"]))
            return payload
        except (urllib.error.URLError, TimeoutError, RuntimeError):
            if attempt == 3:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("unreachable")


def spec_map(item: dict) -> dict[str, str]:
    return {s["code"]: s["value"] for s in item.get("tech_specs", [])}


def parse_profiles(raw: str | None, sku: str) -> list[str]:
    if not raw:
        m = PART_RE.match(sku.upper())
        if m and m.group("profile").upper() == "Z":
            return ["both"]
        if m and m.group("profile").upper() == "C":
            return ["xmp"]
        return ["jedec"]
    text = raw.lower()
    has_xmp = "xmp" in text
    has_expo = "expo" in text
    if has_xmp and has_expo:
        return ["both"]
    if has_expo:
        return ["expo"]
    if has_xmp:
        return ["xmp"]
    return ["jedec"]


def parse_memory_size(raw: str | None, sku: str) -> tuple[int, int] | None:
    if raw:
        m = MEMORY_SIZE_RE.search(raw)
        if m:
            return int(m.group("sticks")), int(m.group("per"))
        m = SINGLE_SIZE_RE.search(raw)
        if m:
            total = int(m.group("total"))
            return 1, total
    m = PART_RE.match(sku.upper())
    if not m:
        return None
    sticks = int(m.group("sticks"))
    # CMK32GX5 -> 32G is total kit capacity in Corsair numbering
    cap_match = re.search(r"CM[A-Z](\d+)GX5", sku.upper())
    if not cap_match:
        return None
    total = int(cap_match.group(1))
    if total % sticks != 0:
        return None
    return sticks, total // sticks


def parse_rgb(specs: dict[str, str], name: str, sku: str) -> bool:
    led = specs.get("LED Lighting", "").upper()
    if led == "RGB":
        return True
    if "rgb" in name.lower():
        return True
    series = sku[2:3].upper() if len(sku) > 2 else ""
    return series in {"H", "P"}  # Vengeance RGB, Dominator RGB lines


def clean_name(name: str) -> str:
    text = name.replace("\u00ae", "").replace("\u2122", "").strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*—.*$", "", text)
    text = re.sub(r"\s*-\s*(Black|White|Grey|Gray|Silver).*$", "", text, flags=re.I)
    return text.strip()


def parse_cas_latency(specs: dict[str, str], sku: str) -> int | None:
    raw = specs.get("Tested Latency")
    if raw:
        first = raw.split("-")[0].strip()
        if first.isdigit():
            return int(first)
    m = PART_RE.match(sku.upper())
    return int(m.group("cl")) if m else None


def parse_speed(specs: dict[str, str], sku: str) -> int | None:
    raw = specs.get("Tested Speed (Up To)") or specs.get("Tested Speed")
    if raw and str(raw).strip().isdigit():
        return int(str(raw).strip())
    m = PART_RE.match(sku.upper())
    return int(m.group("speed")) if m else None


def is_desktop_ddr5(item: dict) -> bool:
    sku = item.get("sku", "")
    if not PART_RE.match(sku.upper()):
        return False
    specs = spec_map(item)
    mem_type = specs.get("Memory Type", "DDR5").upper()
    if "DDR5" not in mem_type:
        return False
    fmt = specs.get("Package Memory Format", "UDIMM").upper()
    return fmt == "UDIMM"


def item_to_entry(item: dict) -> dict | None:
    sku = item.get("sku", "").upper()
    if not PART_RE.match(sku):
        return None
    specs = spec_map(item)
    if specs.get("Package Memory Format", "UDIMM").upper() != "UDIMM":
        return None
    if "DDR5" not in specs.get("Memory Type", "DDR5").upper():
        return None

    size = parse_memory_size(specs.get("Memory Size"), sku)
    if not size:
        return None
    sticks, per_stick = size
    speed = parse_speed(specs, sku)
    cl = parse_cas_latency(specs, sku)
    if speed is None or cl is None:
        return None

    url_key = item.get("url_key", "")
    slug = f"{sku.lower()}/{url_key}" if url_key else sku.lower()
    name = clean_name(item.get("name", sku))

    return {
        "brand": "corsair",
        "part_number": sku,
        "product_name": name,
        "sticks": sticks,
        "per_stick_gb": per_stick,
        "speed_mts": speed,
        "cas_latency": cl,
        "profiles": parse_profiles(specs.get("Performance Profile"), sku),
        "rgb": parse_rgb(specs, item.get("name", ""), sku),
        "form_factor": "dimm",
        "source_url": f"{BASE_URL}/{slug}",
    }


def fetch_category_items() -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        data = gql(
            PRODUCTS_QUERY,
            {
                "searchCriteria": [
                    {
                        "attribute_code": "category_url_key",
                        "filter_action": "EQ",
                        "filter_value": "ddr5-ram",
                    }
                ],
                "pageSize": 100,
                "currentPage": page,
                "sort": {"featured": "ASC"},
            },
        )
        products = data["data"]["products"]
        items.extend(products["items"])
        total_pages = products["page_info"]["total_pages"]
        print(f"Category page {page}/{total_pages}: {len(products['items'])} items")
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.15)
    return items


def sitemap_skus() -> dict[str, str]:
    xml = urllib.request.urlopen(SITEMAP, timeout=60).read()
    root = ET.fromstring(xml)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    out: dict[str, str] = {}
    for loc in root.findall(".//sm:loc", ns):
        url = (loc.text or "").strip()
        if "/us/en/p/memory/" not in url:
            continue
        slug = url.lower()
        if "ddr4" in slug or "gx4" in slug or "sodimm" in slug:
            continue
        m = re.search(r"/p/memory/([a-z0-9]+)/", slug)
        if not m:
            continue
        sku = m.group(1).upper()
        if "GX5" not in sku or not sku.startswith("CM"):
            continue
        out[sku] = url.rstrip("/")
    return out


def fetch_sku(sku: str) -> dict | None:
    data = gql(
        PRODUCTS_QUERY,
        {
            "searchCriteria": [
                {"attribute_code": "sku", "filter_action": "EQ", "filter_value": sku}
            ],
            "pageSize": 1,
            "currentPage": 1,
        },
    )
    items = data["data"]["products"]["items"]
    return items[0] if items else None


def main() -> None:
    category_items = fetch_category_items()
    by_sku: dict[str, dict] = {}
    for item in category_items:
        sku = item.get("sku", "").upper()
        if sku:
            by_sku[sku] = item

    sitemap = sitemap_skus()
    missing = [sku for sku in sitemap if sku not in by_sku]
    print(f"Category SKUs: {len(by_sku)}, sitemap SKUs: {len(sitemap)}, missing: {len(missing)}")

    if missing:
        print(f"Fetching {len(missing)} sitemap-only SKUs...")
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(fetch_sku, sku): sku for sku in missing}
            done = 0
            for fut in as_completed(futures):
                sku = futures[fut]
                done += 1
                if done % 50 == 0:
                    print(f"  fetched {done}/{len(missing)}")
                try:
                    item = fut.result()
                    if item:
                        by_sku[sku.upper()] = item
                except Exception as exc:
                    print(f"  warn: failed {sku}: {exc}")
                time.sleep(0.05)

    entries: list[dict] = []
    skipped: list[str] = []
    for sku, item in sorted(by_sku.items()):
        if not is_desktop_ddr5(item):
            skipped.append(sku)
            continue
        entry = item_to_entry(item)
        if entry:
            if sku in sitemap:
                entry["source_url"] = sitemap[sku]
            entries.append(entry)
        else:
            skipped.append(sku)

    # dedupe by part_number
    seen: set[str] = set()
    unique: list[dict] = []
    for e in entries:
        if e["part_number"] in seen:
            continue
        seen.add(e["part_number"])
        unique.append(e)

    unique.sort(key=lambda e: (e["speed_mts"], e["sticks"] * e["per_stick_gb"], e["part_number"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(unique, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(unique)} SKUs to {OUT}")
    if skipped:
        print(f"Skipped {len(skipped)} non-desktop/invalid items")


if __name__ == "__main__":
    main()

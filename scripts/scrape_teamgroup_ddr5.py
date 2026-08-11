#!/usr/bin/env python3
"""Scrape verified TeamGroup T-FORCE / T-CREATE DDR5 desktop memory SKUs."""

from __future__ import annotations

import base64
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "teamgroup_ddr5.json"
API = "https://www.teamgroupinc.com/en/product/act/"
BASE = "https://www.teamgroupinc.com"

FILTERS = {
    "T-FORCE": "filter-209=2410&filter-219=2412&filter-210=2415",
    "T-CREATE": "filter-209=2409&filter-219=2412&filter-210=2415",
}

PART_RE = re.compile(r"^[A-Z0-9]{8,}(?:-CU\d+)?$")
CAPACITY_RE = re.compile(
    r"(?P<total>\d+)\s*GB\s*\(\s*(?P<sticks>\d+)\s*x\s*(?P<per>\d+)\s*GB\s*\)",
    re.I,
)
SINGLE_CAPACITY_RE = re.compile(r"(?P<total>\d+)\s*GB(?!\s*\()", re.I)
SPEED_RE = re.compile(r"(\d+)\s*(?:MT/s|MHz)", re.I)
CL_RE = re.compile(r"CL(\d+)", re.I)


def b64url_encode(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("unreachable")


def parse_capacity(raw: str) -> tuple[int, int] | None:
    m = CAPACITY_RE.search(raw)
    if m:
        return int(m.group("sticks")), int(m.group("per"))
    m = SINGLE_CAPACITY_RE.search(raw)
    if m:
        total = int(m.group("total"))
        return 1, total
    return None


def parse_speed(raw: str) -> int | None:
    m = SPEED_RE.search(raw)
    return int(m.group(1)) if m else None


def parse_cl(raw: str) -> int | None:
    m = CL_RE.search(raw)
    return int(m.group(1)) if m else None


def parse_profiles(compat: str, speed_mts: int) -> list[str]:
    compat_l = compat.lower()
    has_intel = "intel" in compat_l
    has_amd = "amd" in compat_l
    if has_intel and has_amd:
        return ["both"]
    if has_intel:
        return ["xmp"]
    if has_amd:
        return ["expo"]
    if speed_mts <= 5600:
        return ["jedec"]
    return ["xmp"]


def infer_rgb(product_name: str) -> bool:
    upper = product_name.upper()
    return "RGB" in upper or "ARGB" in upper


def build_source_url(base_url: str, part_number: str) -> str:
    return re.sub(r"-[A-Z0-9-]+/$", f"-{part_number}/", base_url)


def build_product_name(series: str, capacity: str, freq: str, latency: str) -> str:
    return f"{series} {capacity} {freq} {latency}".strip()


def parse_compare_page(html: str) -> list[dict]:
    rows_out: list[dict] = []
    for sec in re.split(r'<section class="compareBox', html)[1:]:
        title_m = re.search(
            r'class="productTitle[^"]*"><a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>',
            sec,
        )
        if not title_m:
            continue
        base_url, series_name = title_m.group(1), title_m.group(2).strip()
        if "/TEAMGROUP/" in base_url:
            continue

        for row in re.findall(
            r'<tr class="specTableRow specTableRowContent">(.*?)</tr>', sec, re.S
        ):
            cols = re.findall(r'<td class="specTableColumn">([^<]*)</td>', row)
            if len(cols) < 7:
                continue
            _module, capacity, freq, latency, _volt, compat, part = cols[:7]
            part = part.strip()
            if not PART_RE.match(part):
                continue

            cap = parse_capacity(capacity)
            speed = parse_speed(freq)
            cl = parse_cl(latency)
            if not cap or speed is None or cl is None:
                continue

            sticks, per_stick_gb = cap
            product_name = build_product_name(series_name, capacity, freq, latency)
            rows_out.append(
                {
                    "brand": "teamgroup",
                    "part_number": part,
                    "product_name": product_name,
                    "sticks": sticks,
                    "per_stick_gb": per_stick_gb,
                    "speed_mts": speed,
                    "cas_latency": cl,
                    "profiles": parse_profiles(compat, speed),
                    "rgb": infer_rgb(series_name),
                    "form_factor": "dimm",
                    "source_url": build_source_url(base_url, part),
                }
            )
    return rows_out


def fetch_brand_skus(brand_key: str, filter_str: str) -> list[dict]:
    encoded = b64url_encode(filter_str)
    collected: list[dict] = []
    for page in range(1, 50):
        url = (
            f"{API}?act=101&filter={encoded}&page={page}"
            f"&index_m1_blink=memory&index_m2_blink="
        )
        html = fetch_html(url)
        page_rows = parse_compare_page(html)
        if not page_rows:
            break
        collected.extend(page_rows)
        print(f"  {brand_key} page {page}: +{len(page_rows)} rows")
        time.sleep(0.2)
    return collected


def main() -> None:
    by_part: dict[str, dict] = {}
    for brand_key, filter_str in FILTERS.items():
        print(f"Fetching {brand_key}...")
        for entry in fetch_brand_skus(brand_key, filter_str):
            by_part[entry["part_number"]] = entry

    entries = sorted(
        by_part.values(),
        key=lambda e: (e["product_name"], e["speed_mts"], e["part_number"]),
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} SKUs to {OUT}")


if __name__ == "__main__":
    main()

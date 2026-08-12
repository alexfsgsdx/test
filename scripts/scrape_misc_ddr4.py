#!/usr/bin/env python3
"""Scrape DDR4 desktop UDIMM SKUs for misc memory brands."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decode_ddr4_parts import decode_part  # noqa: E402
from scrape_utils import fetch, write_json  # noqa: E402

DATA = ROOT / "data"

BRANDS = [
    "crucial", "patriot", "xpg", "pny", "oloy", "geil", "mushkin", "silicon_power",
    "ballistix", "adata", "micron",
]

PART_PATTERNS: dict[str, re.Pattern[str]] = {
    "crucial": re.compile(r"\b(CT(?:2K|4K|8K)?\d+G4[A-Z0-9]+|BL(?:2K|4K)?\d+G\d{2,3}C\d{2}U4)\b", re.I),
    "patriot": re.compile(r"\b(PSP4\d{2}G\d{4}K?H?\d?|PV4\d{2}G\d{2,4}C\d{2}K?|PSD4\d{2}G\d{4}K?)\b", re.I),
    "xpg": re.compile(r"\bAX4U\d{4}C\d{2}\d{1,3}G[-A-Z0-9]+\b", re.I),
    "pny": re.compile(r"\bMD\d{2}G(K\d)?D4\d{7}[A-Z]*\b", re.I),
    "oloy": re.compile(r"\b[MN]D4U16\d{6}[A-Z]+(?:DE|DA)\b", re.I),
    "geil": re.compile(r"\bGA[A-Z0-9]*4\d{2}GB\d{4}C\d{2}[A-Z0-9]+\b", re.I),
    "mushkin": re.compile(r"\bMR4U\d{4}C\d{2}\d{2}G(?:X\d)?\b", re.I),
    "silicon_power": re.compile(r"\bSP\d{3}GLHU\d{4}B\d{2}A4(?:X\d)?\b", re.I),
    "ballistix": re.compile(r"\bBLT(?:2K|4K)\d+G4D\d{2,4}AET4K\b", re.I),
    "adata": re.compile(r"\bAD4U\d{4}C\d{2}\d{1,3}G[-A-Z0-9]+\b", re.I),
    "micron": re.compile(r"\bMTA\d+ASF\d{2}C\d{2}(?:K\d)?\b", re.I),
}

CURATED: dict[str, list[str]] = {
    "crucial": [
        "CT2K16G4DFRA32A", "CT2K8G4DFRA32A", "CT2K16G4DFRD2666", "CT2K8G4DFRD2666",
        "CT16G4DFD832A", "CT8G4DFRA266", "CT16G4DFRA266", "CT2K16G4DFRA266",
        "CT2K32G4DFD832A", "CT2K16G4SFD8266", "CT2K16G4DFRA32", "CT2K8G4DFRA32",
        "BL2K8G32C16U4B", "BL2K16G32C16U4B", "BL2K8G36C16U4B", "BL2K16G36C16U4B",
        "BL2K8G30C15U4B", "BL2K16G30C15U4B",
    ],
    "patriot": [
        "PSP432G3200KH1", "PSP416G3200KH1", "PSP464G3200KH1", "PSP432G3600KH1",
        "PSP416G3600KH1", "PSP464G3600KH1", "PSD432G3200K", "PSD416G3200K",
        "PV432G320C16K", "PV416G320C16K", "PV432G360C18K", "PV416G360C18K",
    ],
    "xpg": [
        "AX4U320032G16A-DTBKD35G", "AX4U320016G16A-SBKD35G", "AX4U360016G18A-SBKD35G",
        "AX4U360032G18A-DTBKD35G", "AX4U32008G16A-BBKD35G", "AX4U320016G16A-WBKD35G",
        "AX4U320032G16A-WBKD35G", "AX4U360032G18A-WTBKD35G",
    ],
    "pny": [
        "MD32GK4D4320036XR", "MD16GK4D4320036XR", "MD32GK4D4360038XR",
        "MD16GK4D4360038XR", "MD32GK4D4320036XRGB", "MD16GK4D4320036XRGB",
    ],
    "ballistix": [
        "BLT2K8G4D32AET4K", "BLT4K8G4D32AET4K", "BLT2K8G4D30AET4K",
    ],
}


def add_part(bucket: dict[str, dict], brand: str, part: str, **kwargs) -> None:
    part = part.upper().strip()
    if not part or part in bucket:
        return
    entry = decode_part(brand, part, **kwargs)
    if not entry:
        return
    if entry["speed_mts"] <= 0 or entry["cas_latency"] <= 0 or entry["per_stick_gb"] <= 0:
        return
    bucket[part] = entry


def scrape_html(brand: str, url: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    try:
        html = fetch(url, timeout=20)
    except Exception:
        return out
    pat = PART_PATTERNS[brand]
    for match in pat.findall(html):
        add_part(out, brand, match, source_url=url)
    return out


def scrape_brand(brand: str) -> list[dict]:
    parts: dict[str, dict] = {}
    for part in CURATED.get(brand, []):
        add_part(parts, brand, part)
    urls = {
        "crucial": "https://www.crucial.com/memory/ddr4",
        "patriot": "https://www.patriotmemory.com/en/products/signature-line-premium-ddr4",
        "xpg": "https://www.xpg.com/us/xpg/dram-modules-spectrix-d35g-ddr4",
        "pny": "https://www.pny.com/ddr4-memory",
    }
    if brand in urls:
        parts.update(scrape_html(brand, urls[brand]))
    return sorted(parts.values(), key=lambda e: e["part_number"])


def main() -> None:
    all_misc: list[dict] = []
    for brand in BRANDS:
        items = scrape_brand(brand)
        out_path = DATA / f"{brand}_ddr4.json"
        write_json(out_path, items)
        print(f"  {brand}: {len(items)} DDR4 SKUs -> {out_path.name}")
        all_misc.extend(items)
    write_json(DATA / "misc_ddr4.json", all_misc)
    print(f"Combined misc DDR4: {len(all_misc)} SKUs")


if __name__ == "__main__":
    main()

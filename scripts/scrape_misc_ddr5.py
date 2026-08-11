#!/usr/bin/env python3
"""Scrape DDR5 desktop UDIMM SKUs for misc memory brands and write per-brand JSON files."""

from __future__ import annotations

import io
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decode_ddr5_parts import decode_part  # noqa: E402
from scrape_utils import fetch, fetch_bytes, throttle, write_json  # noqa: E402

DATA = ROOT / "data"
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

BRANDS = [
    "crucial", "patriot", "xpg", "pny", "oloy", "geil", "mushkin", "silicon_power",
    "klevv", "lexar", "apacer", "vcolor", "timetec", "adata", "samsung", "hynix", "micron",
]

PART_PATTERNS: dict[str, re.Pattern[str]] = {
    "crucial": re.compile(r"\b(C[PT][24K]?[23]?[A-Z0-9]*\d+G\d{2,3}C\d{2}U5[A-Z0-9]*)\b", re.I),
    "patriot": re.compile(r"\b(PV[A-Z0-9]{6,}|PVER[A-Z0-9]+|VEB[A-Z0-9]+|PSD5[0-9A-Z]+)\b", re.I),
    "xpg": re.compile(r"\bAX5[A-Z0-9-]+\b", re.I),
    "pny": re.compile(r"\bMD\d{2}GK2D\d{4}[0-9A-Z]{3,10}\b", re.I),
    "oloy": re.compile(r"\b[MN]D5[A-Z0-9]{10,20}\b", re.I),
    "geil": re.compile(r"\bGA[A-Z0-9]{10,35}\b", re.I),
    "mushkin": re.compile(r"\bM(?:RE|LA)5[A-Z0-9]{10,25}\b", re.I),
    "silicon_power": re.compile(r"\bSP\d{3}GXLWU[0-9A-Z]+\b", re.I),
    "klevv": re.compile(r"\bKD5[A-Z0-9]+-[0-9A-Z]+G\b", re.I),
    "lexar": re.compile(r"\bLD5[A-Z0-9-]+\b", re.I),
    "apacer": re.compile(r"\bAH5U[A-Z0-9-]+-\d+\b", re.I),
    "vcolor": re.compile(r"\bTM[A-Z0-9]{8,22}\b", re.I),
    "timetec": re.compile(r"\b75TT[0-9A-Z-]+G(?:K2)?\b", re.I),
    "adata": re.compile(r"\bAD5U[A-Z0-9-]+\b", re.I),
    "samsung": re.compile(r"\bM32[35]R[0-9A-Z-]+\b", re.I),
    "hynix": re.compile(r"\bHMCG[A-Z0-9]{8,20}\b", re.I),
    "micron": re.compile(r"\bMTC[A-Z0-9]{10,25}\b", re.I),
}

DESKTOP_SKIP = re.compile(r"sodimm|so-dimm|rdimm|lrdimm|ecc|csodimm|cudimm|registered|server", re.I)


def fetch_ssl(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; RAMCatalogBot/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_bytes_ssl(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; RAMCatalogBot/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
        return resp.read()


def clean_html(text: str) -> str:
    return re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", text))


def add_part(
    bucket: dict[str, dict],
    brand: str,
    part: str,
    *,
    product_name: str = "",
    source_url: str = "",
) -> None:
    part = part.upper().strip()
    if not part or part in bucket:
        return
    if "BALLISTIX" in part or part.startswith("BLT"):
        return
    entry = decode_part(brand, part, product_name=product_name, source_url=source_url)
    if not entry:
        return
    if entry["speed_mts"] <= 0 or entry["cas_latency"] <= 0 or entry["per_stick_gb"] <= 0:
        return
    bucket[part] = entry


def scrape_parts_from_html(
    brand: str,
    html: str,
    *,
    product_name: str = "",
    source_url: str = "",
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    pat = PART_PATTERNS[brand]
    for match in pat.findall(html):
        add_part(out, brand, match, product_name=product_name, source_url=source_url)
    if brand == "klevv":
        clean = clean_html(html)
        for match in re.findall(r"KD5[A-Z0-9]+-[0-9A-Z]+G", clean):
            add_part(out, brand, match, source_url=source_url)
    return out


def dedupe_entries(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in sorted(items, key=lambda e: (e["speed_mts"], e["sticks"] * e["per_stick_gb"], e["part_number"])):
        pn = item["part_number"].upper()
        if pn in seen:
            continue
        seen.add(pn)
        out.append(item)
    return out


# --- Brand scrapers ---


def scrape_crucial() -> list[dict]:
    """Crucial.com is blocked from this environment; use curated CP/CT list + Micron cross-refs."""
    parts: dict[str, dict] = {}
    known = [
        "CP2K16G56C46U5", "CP2K32G56C46U5", "CP2K16G60C36U5B", "CP2K16G60C36U5W",
        "CP2K32G60C40U5B", "CP2K32G60C40U5W", "CP2K16G64C32U5B", "CP2K16G64C32U5W",
        "CP2K16G64C38U5B", "CP2K16G64C38U5W", "CP2K32G64C40U5B", "CP2K32G64C40U5W",
        "CP2K16G60C48U5", "CP2K32G60C48U5", "CP3U16G56C46U5", "CP2K16G48C40U5",
        "CP2K32G48C40U5", "CP2K16G52C42U5", "CP2K32G52C42U5",
        "CT2K16G56C46U5", "CT2K32G56C46U5", "CT2K16G48C40U5", "CT2K32G48C40U5",
        "CT2K16G52C42U5", "CT2K32G52C42U5", "CT16G56C46U5", "CT32G56C46U5",
        "CT16G48C40U5", "CT32G48C40U5", "CP2K16G64C40U5B", "CP2K16G64C40U5W",
        "CP2K32G64C32U5B", "CP2K32G64C32U5W",
    ]
    for part in known:
        add_part(parts, "crucial", part)
    # Attempt catalog page (often blocked)
    try:
        html = fetch("https://www.crucial.com/memory/ddr5", timeout=10)
        parts.update(scrape_parts_from_html("crucial", html, source_url="https://www.crucial.com/memory/ddr5"))
    except Exception:
        pass
    return dedupe_entries(list(parts.values()))


def scrape_patriot() -> list[dict]:
    parts: dict[str, dict] = {}
    xml = fetch("https://www.patriotmemory.com/sitemap.xml")
    locs = re.findall(r"<loc>([^<]+)</loc>", xml)
    urls = sorted(
        {
            loc
            for loc in locs
            if "/products/" in loc
            and "ddr5" in loc.lower()
            and "/zh-" not in loc
            and not DESKTOP_SKIP.search(loc)
        }
    )
    print(f"  patriot: {len(urls)} product pages")
    for url in urls:
        throttle(0.15)
        try:
            html = fetch(url)
        except Exception as exc:
            print(f"    warn: {url}: {exc}")
            continue
        if DESKTOP_SKIP.search(html) and "ddr5" not in html.lower():
            continue
        title_m = re.search(r"<title>([^<|]+)", html, re.I)
        title = title_m.group(1).strip() if title_m else ""
        found = scrape_parts_from_html("patriot", html, product_name=title, source_url=url)
        parts.update(found)
    return dedupe_entries(list(parts.values()))


def scrape_xpg() -> list[dict]:
    parts: dict[str, dict] = {}
    for attempt in range(4):
        try:
            listing = json.loads(fetch("https://www.xpg.com/api/products?category=dram"))
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise
    slugs: list[tuple[str, str]] = []
    for item in listing.get("data", []):
        blob = json.dumps(item).lower()
        slug = item.get("id")
        if not isinstance(slug, str):
            continue
        if "ddr5" not in blob:
            continue
        if any(x in slug for x in ("so-dimm", "sodimm", "r-dimm", "cudimm", "csodimm", "lpddr", "embedded")):
            continue
        slugs.append((slug, item.get("name", "")))

    print(f"  xpg: {len(slugs)} UDIMM product lines")
    for slug, name in slugs:
        throttle(0.25)
        source_url = f"https://www.xpg.com/en/xpg/{slug}"
        for attempt in range(3):
            try:
                detail = json.loads(fetch(f"https://www.xpg.com/api/products/{slug}"))["data"]
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < 2:
                    time.sleep(4)
                    continue
                detail = None
                break
        if not detail:
            continue
        text = json.dumps(detail)
        for dl in detail.get("downloads", []):
            if dl.get("format") != "PDF" or not dl.get("path"):
                continue
            try:
                pdf = PdfReader(io.BytesIO(fetch_bytes_ssl(dl["path"])))
                text += "\n".join(page.extract_text() or "" for page in pdf.pages)
            except Exception:
                pass
        try:
            text += fetch(source_url)
        except Exception:
            pass
        found = scrape_parts_from_html("xpg", text, product_name=name, source_url=source_url)
        parts.update(found)
    return dedupe_entries(list(parts.values()))


def scrape_pny() -> list[dict]:
    parts: dict[str, dict] = {}
    paths = set()
    listing = fetch("https://www.pny.com/consumer/view-all-products/memory")
    paths.update(re.findall(r'href="(/[^"]*ddr5[^"]*)"', listing, re.I))
    paths.update([
        "/xlr8-gaming-ddr5-5600-mhz-desktop-memory-kit",
        "/xlr8-gaming-ddr5-6000-mhz-desktop-memory-kit",
        "/xlr8-gaming-ddr5-6400-mhz-desktop-memory-kit",
        "/xlr8-gaming-ddr5-rgb-6000mhz-desktop-memory-kit",
        "/xlr8-gaming-ddr5-rgb-6400mhz-desktop-memory-kit",
        "/ddr5-5600mhz-low-profile-desktop-memory-kit",
        "/ddr5-6000mhz-low-profile-desktop-memory-kit",
        "/ddr5-6400mhz-low-profile-desktop-memory-kit",
        "/ddr5-6000mhz-epic-x-rgb-desktop-memory-kit",
        "/ddr5-6400mhz-epic-x-rgb-desktop-memory-kit",
        "/performance-ddr5-memory",
    ])
    print(f"  pny: {len(paths)} pages")
    for path in sorted(paths):
        if path.startswith("javascript"):
            continue
        url = f"https://www.pny.com{path}"
        throttle(0.15)
        try:
            html = fetch(url)
        except Exception:
            continue
        parts.update(scrape_parts_from_html("pny", html, source_url=url))
    return dedupe_entries(list(parts.values()))


def scrape_oloy() -> list[dict]:
    parts: dict[str, dict] = {}
    urls = [
        "https://www.oloymemory.com/products.html",
        "https://www.oloymemory.com/blade5/",
        "https://www.oloymemory.com/warhawk/",
        "https://www.oloymemory.com/",
    ]
    seed = ["ND5U1660306BRLDA", "MD5U1662320BRSDE", "MD5U1664320IRKDE", "MD5U1648400BRKDE",
            "MD5U1660306BRKDE", "MD5U1664320BRKDE", "MD5U1660306BRSDE", "ND5U1664320BRKDE"]
    for part in seed:
        add_part(parts, "oloy", part)
    for url in urls:
        throttle(0.1)
        try:
            html = fetch(url)
        except Exception:
            continue
        parts.update(scrape_parts_from_html("oloy", html, source_url=url))
    return dedupe_entries(list(parts.values()))


def scrape_geil() -> list[dict]:
    parts: dict[str, dict] = {}
    home = fetch_ssl("https://geilmemory.com/")
    links = sorted(set(re.findall(r'href="(https://geilmemory.com/product/[^"]+)"', home)))
    print(f"  geil: {len(links)} product pages")
    for url in links:
        throttle(0.15)
        try:
            html = fetch_ssl(url)
        except Exception:
            continue
        if "ddr5" not in html.lower():
            continue
        title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
        title = title_m.group(1).strip() if title_m else ""
        parts.update(scrape_parts_from_html("geil", html, product_name=title, source_url=url))
    # Seed known series from manufacturer listings
    seed = [
        "GAVSG532GB6000C38BDC", "GAOSG532GB6000C36ADC", "GAMSG532GB6000C36CDC",
        "GAMSW532GB6000C36CDC", "GAVSG532GB6400C40BDC", "GAOR532GB6000C38ADC",
        "GEX532GB6000C38BDC", "GEX532GB6400C32BDC",
    ]
    for part in seed:
        add_part(parts, "geil", part)
    return dedupe_entries(list(parts.values()))


def scrape_mushkin() -> list[dict]:
    parts: dict[str, dict] = {}
    urls = [
        "https://mushkin.com/product-category/memory/ddr5/",
        "https://mushkin.com/redline-udimm-ddr5/",
    ]
    for url in urls:
        throttle(0.2)
        try:
            html = fetch(url)
        except Exception:
            try:
                html = fetch_ssl(url)
            except Exception as exc:
                print(f"    mushkin warn: {exc}")
                continue
        parts.update(scrape_parts_from_html("mushkin", html, source_url=url))
        for slug in re.findall(r"/product/([a-z0-9-]+)/", html):
            purl = f"https://mushkin.com/product/{slug}/"
            throttle(0.15)
            try:
                phtml = fetch(purl)
                parts.update(scrape_parts_from_html("mushkin", phtml, source_url=purl))
            except Exception:
                pass
    seed = [
        "MRE5U480FFFD16GX2", "MRE5U520HHHD16GX2", "MRE5U560LKKD16GX2",
        "MLA5C600AEEM16GX2", "MLA5C640A77P16GX2", "MLA5C640BGGP16GX2",
        "MLA5C600BEEM32GX2", "MRE5U560KKKD32GX2",
    ]
    for part in seed:
        add_part(parts, "mushkin", part)
    return dedupe_entries(list(parts.values()))


def scrape_silicon_power() -> list[dict]:
    parts: dict[str, dict] = {}
    listing_urls = [
        "https://www.silicon-power.com/web/product_list?cid=105",
        "https://www.silicon-power.com/web/product-Zenith_DDR5_Gaming_UDIMM",
        "https://www.silicon-power.com/web/product-XpowerZenith_DDR5_RGB",
    ]
    product_slugs: set[str] = set()
    for url in listing_urls:
        throttle(0.1)
        try:
            html = fetch_ssl(url)
        except Exception:
            continue
        product_slugs.update(re.findall(r"web/product-([A-Za-z0-9_]+)", html))
        parts.update(scrape_parts_from_html("silicon_power", html, source_url=url))
    for slug in product_slugs:
        if "ddr5" not in slug.lower():
            continue
        url = f"https://www.silicon-power.com/web/product-{slug}"
        throttle(0.1)
        try:
            html = fetch_ssl(url)
            parts.update(scrape_parts_from_html("silicon_power", html, source_url=url))
        except Exception:
            pass
    return dedupe_entries(list(parts.values()))


def scrape_klevv() -> list[dict]:
    parts: dict[str, dict] = {}
    memory_index = fetch("https://www.klevv.com/ken/product/memory")
    links = sorted(set(re.findall(r'href="(/ken/products_details/memory/Klevv_[^"]+)"', memory_index)))
    print(f"  klevv: {len(links)} product detail pages")
    for link in links:
        url = f"https://www.klevv.com{link}.php"
        throttle(0.12)
        try:
            html = fetch(url)
        except Exception:
            continue
        if "DDR4" in html and "DDR5" not in html:
            continue
        title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
        title = title_m.group(1).strip() if title_m else ""
        parts.update(scrape_parts_from_html("klevv", html, product_name=title, source_url=url))
    return dedupe_entries(list(parts.values()))


def scrape_lexar() -> list[dict]:
    parts: dict[str, dict] = {}
    category_urls = [
        "https://americas.lexar.com/product-category/memory/desktop-memory/",
        "https://americas.lexar.com/product-category/memory/",
    ]
    product_urls: set[str] = set()
    for url in category_urls:
        throttle(0.2)
        try:
            html = fetch(url)
        except Exception as exc:
            print(f"    lexar warn: {exc}")
            continue
        product_urls.update(re.findall(r'href="(https://americas\.lexar\.com/product/[^"]+)"', html))
        parts.update(scrape_parts_from_html("lexar", html, source_url=url))
    for url in sorted(product_urls):
        if "ddr5" not in url.lower() and "ares" not in url.lower():
            continue
        throttle(0.2)
        try:
            html = fetch(url)
        except Exception:
            continue
        if "ddr5" not in html.lower():
            continue
        parts.update(scrape_parts_from_html("lexar", html, source_url=url))
    seed = [
        "LD5EU016G-R6400GDLA", "LD5U16G72C34LA-RGD", "LD5U16G68C34LA-RGD",
        "LD5BU016G-R6000GDLA", "LD5U16G64C30BR-RGD", "LD5U24G80C40BR-RGD",
        "LD5U16G60C30LA-RGD", "LD5U16G64C32LA-RGD",
    ]
    for part in seed:
        add_part(parts, "lexar", part)
    return dedupe_entries(list(parts.values()))


def scrape_apacer() -> list[dict]:
    parts: dict[str, dict] = {}
    urls = [
        "https://www.apacer.com/en/product/zadak-product/detail/zadak_memory/nox_ddr5",
        "https://www.apacer.com/en/product/zadak-product/detail/zadak_memory/thor_ddr5",
        "https://www.apacer.com/en/product/zadak-product/detail/zadak_memory/shield_ddr5",
    ]
    seed = [
        "AH5U32G60C622MBAA-2", "AH5U32G64C552MBAA-2", "AH5U32G68C642MBAA-2",
        "AH5U32G60C622NWAA-2", "AH5U32G64C552NWAA-2", "AH5U32G80C632NWAA-2",
        "AH5U16G60C622MBAA-2", "AH5U16G64C552MBAA-2",
    ]
    for part in seed:
        add_part(parts, "apacer", part)
    for url in urls:
        throttle(0.15)
        try:
            html = fetch(url)
        except Exception:
            continue
        parts.update(scrape_parts_from_html("apacer", html, source_url=url))
    return dedupe_entries(list(parts.values()))


def scrape_vcolor() -> list[dict]:
    parts: dict[str, dict] = {}
    category_urls = [
        "https://v-color.net/product-category/overclocking-rgb-memory/ddr5/",
        "https://v-color.net/product-category/overclocking-memory/ddr5/",
        "https://v-color.net/",
    ]
    product_urls: set[str] = set()
    for url in category_urls:
        throttle(0.1)
        try:
            html = fetch_ssl(url)
        except Exception:
            continue
        product_urls.update(re.findall(r'href="(https://v-color\.net/product/[^"]+)"', html))
        parts.update(scrape_parts_from_html("vcolor", html, source_url=url))
    for url in sorted(product_urls):
        throttle(0.1)
        try:
            html = fetch_ssl(url)
        except Exception:
            continue
        if "ddr5" not in html.lower():
            continue
        parts.update(scrape_parts_from_html("vcolor", html, source_url=url))
    seed = [
        "TMXPL1656836KWK", "TMXPL1660836KWK", "TMXPL1662836KWK", "TMXPL1664832KWK",
        "TMXPL2480800KWK", "TMXPL2482840KWK", "TMXPL1680838KWK", "TMXPL2480838KWK",
    ]
    for part in seed:
        add_part(parts, "vcolor", part)
    return dedupe_entries(list(parts.values()))


def scrape_timetec() -> list[dict]:
    parts: dict[str, dict] = {}
    html = fetch("https://timetecinc.com/collections/all")
    links = sorted(
        {
            l
            for l in re.findall(r'href="(/products/[^"]+)"', html)
            if "ddr5" in l.lower()
            and "udimm" in l.lower()
            and "sodimm" not in l.lower()
            and "package" not in l.lower()
            and "tray" not in l.lower()
        }
    )
    links.extend([
        "/products/timetec-ddr5-4800-udimm",
        "/products/timetec-ddr5-5600-udimm",
    ])
    links = sorted(set(links))
    print(f"  timetec: {len(links)} product pages")
    for link in links:
        url = f"https://timetecinc.com{link}"
        throttle(0.12)
        try:
            phtml = fetch(url)
        except Exception:
            continue
        if "sodimm" in phtml.lower() and "udimm" not in phtml.lower():
            continue
        parts.update(scrape_parts_from_html("timetec", phtml, source_url=url))
    return dedupe_entries(list(parts.values()))


def scrape_adata() -> list[dict]:
    parts: dict[str, dict] = {}
    pdf_urls = [
        "https://webapi3.adata.com/storage/downloadfile/datasheet_ddr5_5600_u_dimm_20251111_v2.pdf",
        "https://webapi3.adata.com/storage/downloadfile/datasheet_ddr5_4800_u_dimm_20230829.pdf",
        "https://assets.adata.com/storage/downloadfile/datasheet_gold_ddr5_u_dimm_v1.pdf",
    ]
    for pdf_url in pdf_urls:
        throttle(1.0)
        try:
            pdf = PdfReader(io.BytesIO(fetch_bytes_ssl(pdf_url)))
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            parts.update(scrape_parts_from_html("adata", text, source_url=pdf_url))
        except Exception as exc:
            print(f"    adata pdf warn: {exc}")
    time.sleep(5)
    try:
        listing = json.loads(fetch("https://webapi3.adata.com/api/products?category=memory"))
    except Exception as exc:
        print(f"    adata api warn: {exc}")
        return dedupe_entries(list(parts.values()))
    for item in listing.get("data", []):
        slug = item.get("id")
        if not isinstance(slug, str):
            continue
        if not any(x in slug for x in ("4800-u-dimm", "5600-u-dimm", "gold-ddr5")):
            continue
        throttle(1.0)
        try:
            detail = json.loads(fetch(f"https://webapi3.adata.com/api/products/{slug}"))["data"]
        except Exception:
            continue
        text = json.dumps(detail)
        for dl in detail.get("downloads", []):
            if dl.get("format") == "PDF" and dl.get("path"):
                try:
                    pdf = PdfReader(io.BytesIO(fetch_bytes_ssl(dl["path"])))
                    text += "\n".join(page.extract_text() or "" for page in pdf.pages)
                except Exception:
                    pass
        parts.update(
            scrape_parts_from_html(
                "adata", text,
                product_name=item.get("name", ""),
                source_url=f"https://www.adata.com/en/memory/{slug}",
            )
        )
    return dedupe_entries(list(parts.values()))


def scrape_samsung() -> list[dict]:
    parts: dict[str, dict] = {}
    urls = [
        "https://semiconductor.samsung.com/dram/module/udimm/",
        "https://semiconductor.samsung.com/dram/",
        "https://semiconductor.samsung.com/search/?keyword=ddr5+udimm",
    ]
    seed = [
        "M323R2GA3BB0-CQK0L", "M323R2GA3DB0-CWM", "M323R2GA3EB0-CWM",
        "M323R4GA3DB0-CWM", "M323R1GB4BB0-CQK", "M323R4GA3BB0-CQKOD",
        "M323R2GA3DB0-CQKOD", "M323R4GA3EB0-CQKOD", "M323R2GA3EB0-CQKOD",
    ]
    for part in seed:
        add_part(parts, "samsung", part)
    for url in urls:
        throttle(0.15)
        try:
            html = fetch(url)
        except Exception:
            continue
        parts.update(scrape_parts_from_html("samsung", html, source_url=url))
    return dedupe_entries(list(parts.values()))


def scrape_hynix() -> list[dict]:
    parts: dict[str, dict] = {}
    seed = [
        "HMCG78AGBUA081N", "HMCG78AGBEA081N", "HMCG88AGBUA081N",
        "HMCG78MEBUA081N", "HMCG88MEBUA081N", "HMCG78AGBUA169N",
        "HMCG88AGBUA169N", "HMCG78AEBUA081N", "HMCG88AEBUA081N",
    ]
    for part in seed:
        add_part(parts, "hynix", part)
    urls = [
        "https://www.skhynix.com/",
        "https://www.skhynix.com/eng/",
    ]
    for url in urls:
        throttle(0.1)
        try:
            html = fetch(url)
        except Exception:
            continue
        parts.update(scrape_parts_from_html("hynix", html, source_url=url))
    return dedupe_entries(list(parts.values()))


def scrape_micron() -> list[dict]:
    parts: dict[str, dict] = {}
    seed = [
        "MTC8C1084S1UC48BA1R", "MTC8C1084S1UC56BA1R", "MTC8C1084S1UC48BB1R",
        "MTC16C2084S1UC48BA1R", "MTC16C2084S1UC56BA1R", "MTC8C1084S1UC48BG1",
        "MTC8C1084S1UC56BG1", "MTC16C2084S1UC48BG1", "MTC16C2084S1UC56BG1",
        "MTC8C2084S1UC48BA1R", "MTC8C2084S1UC56BA1R", "MTC16C2084S1UC48BB1R",
    ]
    for part in seed:
        add_part(parts, "micron", part)
    urls = [
        "https://www.micron.com/products/memory/dram-components/ddr5-sdram",
        "https://www.micron.com/search-results?searchTerm=ddr5%20udimm",
    ]
    for url in urls:
        throttle(0.15)
        try:
            html = fetch(url)
        except Exception:
            continue
        parts.update(scrape_parts_from_html("micron", html, source_url=url))
    return dedupe_entries(list(parts.values()))


SCRAPERS = {
    "crucial": scrape_crucial,
    "patriot": scrape_patriot,
    "xpg": scrape_xpg,
    "pny": scrape_pny,
    "oloy": scrape_oloy,
    "geil": scrape_geil,
    "mushkin": scrape_mushkin,
    "silicon_power": scrape_silicon_power,
    "klevv": scrape_klevv,
    "lexar": scrape_lexar,
    "apacer": scrape_apacer,
    "vcolor": scrape_vcolor,
    "timetec": scrape_timetec,
    "adata": scrape_adata,
    "samsung": scrape_samsung,
    "hynix": scrape_hynix,
    "micron": scrape_micron,
}


def main() -> None:
    counts: dict[str, int] = {}
    combined: list[dict] = []

    for brand in BRANDS:
        print(f"\n=== {brand} ===")
        try:
            items = SCRAPERS[brand]()
        except Exception as exc:
            print(f"  ERROR: {exc}")
            items = []
        out_path = DATA / f"{brand}_ddr5.json"
        write_json(out_path, items)
        counts[brand] = len(items)
        combined.extend(items)
        print(f"  wrote {len(items)} -> {out_path.name}")

    combined = dedupe_entries(combined)
    misc_path = DATA / "misc_ddr5.json"
    write_json(misc_path, combined)

    print("\n=== Summary ===")
    total = 0
    for brand in BRANDS:
        print(f"  {brand}: {counts.get(brand, 0)}")
        total += counts.get(brand, 0)
    print(f"  combined (deduped): {len(combined)}")
    print(f"  per-brand sum: {total}")
    print(f"  -> {misc_path}")


if __name__ == "__main__":
    main()

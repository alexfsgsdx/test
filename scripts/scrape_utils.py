#!/usr/bin/env python3
"""Shared helpers for DDR5 manufacturer scrapers."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (compatible; RAMCatalogBot/1.0)"}
ROOT = Path(__file__).resolve().parents[1]


def fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_bytes(url: str, timeout: int = 30, retries: int = 4) -> bytes:
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            last_err = exc
            time.sleep(0.75 * (attempt + 1))
    raise last_err  # type: ignore[misc]


def head_ok(url: str, timeout: int = 15) -> bool:
    req = urllib.request.Request(url, method="HEAD", headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except urllib.error.HTTPError as exc:
        return exc.code == 405 and head_ok_get(url, timeout)
    except Exception:
        return False


def head_ok_get(url: str, timeout: int = 15) -> bool:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def write_json(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_gskill_spec(html: str, url: str) -> dict | None:
    part_m = re.search(r"<h1[^>]*>(F5-[A-Z0-9-]+)</h1>", html)
    if not part_m:
        part_m = re.search(r"(F5-[A-Z0-9-]+)-Specification", url)
    if not part_m:
        return None
    part = part_m.group(1)

    def field(label: str) -> str | None:
        pat = rf'list-block list-tit">\s*{re.escape(label)}\s*</div>\s*<div class="list-block">\s*([^<]+)'
        m = re.search(pat, html, re.I | re.S)
        return m.group(1).strip() if m else None

    capacity = field("Capacity") or ""
    speed_raw = field("Tested Speed (Up To) (XMP/EXPO)") or field("SPD Speed (Default)") or ""
    latency_raw = field("Tested Latency (XMP/EXPO)") or field("SPD Latency (Default)") or ""
    profile_raw = field("OC Profile Support") or field("Features") or ""
    module = field("Module Type") or "288-Pin DIMM (UDIMM)"

    cap_m = re.search(r"(\d+)GB\s*\((\d+)GBx(\d+)\)", capacity, re.I)
    if cap_m:
        total, per, sticks = map(int, cap_m.groups())
        per_stick_gb = per
        stick_count = sticks
    else:
        cap_m2 = re.search(r"(\d+)GB", capacity)
        if not cap_m2:
            return None
        total = int(cap_m2.group(1))
        stick_count = 1
        per_stick_gb = total

    speed_m = re.search(r"(\d{4,5})", speed_raw.replace("*", ""))
    if not speed_m:
        og = re.search(r'og:description" content="[^"]*DDR5-(\d{4,5})', html, re.I)
        if not og:
            return None
        speed_mts = int(og.group(1))
    else:
        speed_mts = int(speed_m.group(1))

    cl_m = re.search(r"(\d{2,3})", latency_raw)
    if not cl_m:
        og = re.search(r"CL(\d{2,3})", html)
        if not og:
            return None
        cas = int(og.group(1))
    else:
        cas = int(cl_m.group(1))

    profiles: list[str] = []
    blob = (profile_raw + " " + html).lower()
    if "expo" in blob:
        profiles.append("expo")
    if "xmp" in blob:
        profiles.append("xmp")
    if not profiles:
        profiles = ["jedec"]

    rgb = bool(re.search(r"\brgb\b", html, re.I)) and "non-rgb" not in html.lower()
    form_factor = "sodimm" if "so-dimm" in module.lower() or "sodimm" in module.lower() else "dimm"

    title_m = re.search(r'og:description" content="([^"]+)"', html)
    product_name = title_m.group(1).split(" Up to")[0] if title_m else part

    return {
        "brand": "gskill",
        "part_number": part,
        "product_name": product_name[:120],
        "sticks": stick_count,
        "per_stick_gb": per_stick_gb,
        "speed_mts": speed_mts,
        "cas_latency": cas,
        "profiles": profiles,
        "rgb": rgb,
        "form_factor": form_factor,
        "source_url": url,
    }


def decode_teamgroup_part(part: str, product_name: str = "") -> dict | None:
    m = re.search(r"(\d{3,4})G(\d{4})HC(\d{2,3})", part, re.I)
    if not m:
        return None
    cap_code, speed_mts, cas = m.groups()
    speed_mts = int(speed_mts)
    cas = int(cas[:2])

    cap_code = cap_code.upper()
    if not cap_code.startswith("5"):
        return None

    body = cap_code[1:]
    if len(body) == 2:
        total_gb = int(body)
        sticks = 1
    elif len(body) == 3:
        total_gb = int(body[:2])
        stick_digit = int(body[2])
        sticks = stick_digit if stick_digit in (1, 2, 4) else 1
    elif len(body) == 4:
        total_gb = int(body[:3])
        stick_digit = int(body[3])
        sticks = stick_digit if stick_digit in (1, 2, 4) else 2
    else:
        return None

    if sticks <= 0 or total_gb % sticks != 0:
        sticks = 2 if total_gb >= 32 and "K2" in part.upper() else 1
    per_stick_gb = total_gb // sticks

    name_lower = product_name.lower()
    rgb = any(k in name_lower for k in ("rgb", "argb")) or any(
        tag in part.upper() for tag in ("ARB", "RGD", "RGB")
    )
    form_factor = "sodimm" if "so-dimm" in name_lower or "sodimm" in name_lower else "dimm"

    profiles = ["both"]
    if "classic" in name_lower:
        profiles = ["jedec"]

    product_label = product_name if product_name != part else f"TeamGroup DDR5 {total_gb}GB {speed_mts} CL{cas}"

    return {
        "brand": "teamgroup",
        "part_number": part.upper(),
        "product_name": product_label[:120],
        "sticks": sticks,
        "per_stick_gb": per_stick_gb,
        "speed_mts": speed_mts,
        "cas_latency": cas,
        "profiles": profiles,
        "rgb": rgb,
        "form_factor": form_factor,
    }


def _kingston_profiles(series: str, product_name: str) -> list[str]:
    blob = f"{series} {product_name}".lower()
    has_xmp = "xmp" in blob or "BB" in series
    has_expo = "expo" in blob or "BBE" in series
    if has_xmp and has_expo:
        return ["both"]
    if has_expo:
        return ["expo"]
    if has_xmp:
        return ["xmp"]
    return ["jedec"]


def _kingston_line(part: str, series: str, product_name: str) -> str:
    blob = product_name.lower()
    if part.startswith("KVR5"):
        return "ValueRAM"
    if part.startswith("KSM5"):
        return "Server Premier"
    if "impact" in blob or re.search(r"KF5\d{2}S", part, re.I):
        return "FURY Impact"
    if "renegade" in blob or "RW" in part or "RS" in part or series.startswith("RB") or "R36" in part:
        return "FURY Renegade"
    if "beast" in blob or "BB" in series:
        return "FURY Beast"
    return "FURY"


def _parse_sticks_from_name(product_name: str) -> int | None:
    m = re.search(r"\(\s*(\d+)\s*x\s*(\d+)\s*GB\s*\)", product_name, re.I)
    if m:
        return int(m.group(1))
    return None


def decode_kingston_part(part: str, product_name: str = "") -> dict | None:
    up = part.upper()
    m = re.match(
        r"KF5(?P<speed>\d{2})(?P<mod>[A-Z]?)(?P<cl>\d{2})(?P<series>[A-Z0-9]+?)(?P<kit>K\d)?-(?P<total>\d+)$",
        up,
    )
    if m and m.group("mod").upper() in {"", "C", "S", "R"}:
        speed_mts = int(m.group("speed")) * 100
        cas = int(m.group("cl"))
        total = int(m.group("total"))
        kit = (m.group("kit") or "").upper()
        sticks = {"K2": 2, "K4": 4, "K8": 8}.get(kit, 1)
        named = _parse_sticks_from_name(product_name)
        if named:
            sticks = named
        if total % sticks:
            sticks = 1
        per_stick_gb = total // sticks
        series = m.group("series").upper()
        mod = m.group("mod").upper()
        rgb = any(x in up for x in ("BBA", "BBE", "BBE2A", "RWA", "RSA", "RW", "WB", "BWA", "BWEA"))
        profiles = _kingston_profiles(series, product_name)
        line = _kingston_line(up, series, product_name)
        form_factor = "sodimm" if mod == "S" or "so-dimm" in product_name.lower() or "impact" in product_name.lower() else "dimm"
        if product_name:
            label = product_name
        elif sticks == 1:
            label = f"{line} {total}GB (1x{per_stick_gb}GB) DDR5 {speed_mts} CL{cas}"
        else:
            label = f"{line} {total}GB ({sticks}x{per_stick_gb}GB) DDR5 {speed_mts} CL{cas}"
        return {
            "brand": "kingston",
            "part_number": up,
            "product_name": label[:120],
            "sticks": sticks,
            "per_stick_gb": per_stick_gb,
            "speed_mts": speed_mts,
            "cas_latency": cas,
            "profiles": profiles,
            "rgb": rgb,
            "form_factor": form_factor,
            "source_url": f"https://www.kingston.com/en/memory/search?partid={up}",
        }

    m2 = re.match(
        r"KVR(?P<speed>\d{2})U(?P<cl>\d{2})(?P<series>[A-Z0-9]+)-(?P<total>\d+)$",
        up,
    )
    if m2:
        speed_mts = int(m2.group("speed")) * 100
        cas = int(m2.group("cl"))
        total = int(m2.group("total"))
        series = m2.group("series").upper()
        kit_m = re.search(r"(K[248])$", series)
        kit = kit_m.group(1) if kit_m else ""
        series = series[: kit_m.start()] if kit_m else series
        sticks = {"K2": 2, "K4": 4, "K8": 8}.get(kit, 1)
        if total % sticks:
            sticks = 1
        per_stick_gb = total // sticks
        label = product_name or f"ValueRAM {total}GB DDR5 {speed_mts} CL{cas}"
        form_factor = "sodimm" if series.startswith("BS") else "dimm"
        return {
            "brand": "kingston",
            "part_number": up,
            "product_name": label[:120],
            "sticks": sticks,
            "per_stick_gb": per_stick_gb,
            "speed_mts": speed_mts,
            "cas_latency": cas,
            "profiles": ["jedec"],
            "rgb": False,
            "form_factor": form_factor,
            "source_url": f"https://www.kingston.com/en/memory/search?partid={up}",
        }

    m3 = re.match(r"KSM(?P<speed>\d{2})[A-Z0-9]+-(?P<total>\d+)[A-Z]*$", up)
    if m3:
        speed_mts = int(m3.group("speed")) * 100
        total = int(m3.group("total"))
        sticks = 2 if "K2" in up or total <= 32 else 1
        if total % sticks:
            sticks = 1
        per_stick_gb = total // sticks
        label = product_name or f"Server Premier {total}GB DDR5 {speed_mts}"
        form_factor = "sodimm" if "BS" in up else "dimm"
        return {
            "brand": "kingston",
            "part_number": up,
            "product_name": label[:120],
            "sticks": sticks,
            "per_stick_gb": per_stick_gb,
            "speed_mts": speed_mts,
            "cas_latency": 40,
            "profiles": ["jedec"],
            "rgb": False,
            "form_factor": form_factor,
            "source_url": f"https://www.kingston.com/en/memory/search?partid={up}",
        }

    return None


def parse_kingston_pdf(text: str, part: str) -> dict | None:
    if part not in text:
        return None

    speed_m = re.search(rf"{re.escape(part)}[\s\S]{{0,400}}?DDR5-(\d{{4,5}})", text)
    if not speed_m:
        speed_m = re.search(r"DDR5-(\d{4,5})", text)
    if not speed_m:
        return None
    speed_mts = int(speed_m.group(1))

    cl_m = re.search(rf"DDR5-{speed_mts}\s+CL(\d{{2,3}})", text)
    if not cl_m:
        cl_m = re.search(r"CL(\d{2,3})", text)
    if not cl_m:
        return None
    cas = int(cl_m.group(1))

    kit_m = re.search(r"kit of (two|three|four|eight|\d+)", text, re.I)
    cap_m = re.search(r"Total kit capacity is (\d+)GB", text, re.I)
    pair_m = re.search(r"(\d+)GB\s*\((\d+)GB[^)]*x\s*(\d+)\s*pcs", text, re.I)
    single_paren_m = re.search(r"is a \d+G x 64-bit\s*\((\d+)GB\)", text, re.I)
    header_single_m = re.search(r"(?<!\()\b(\d+)GB\s+\d+G x 64-Bit\b(?!\s*x)", text, re.I)

    sticks = 1
    per_stick_gb = 0
    if pair_m:
        per = int(pair_m.group(2))
        sticks = int(pair_m.group(3))
        per_stick_gb = per
    elif cap_m and kit_m:
        total = int(cap_m.group(1))
        word = kit_m.group(1).lower()
        sticks = {"two": 2, "three": 3, "four": 4, "eight": 8}.get(
            word, int(word) if word.isdigit() else 2
        )
        per_stick_gb = total // sticks
    elif single_paren_m:
        per_stick_gb = int(single_paren_m.group(1))
        sticks = 1
    elif header_single_m:
        per_stick_gb = int(header_single_m.group(1))
        sticks = 1
    else:
        tail_m = re.search(r"-(\d+)\b", part)
        if tail_m:
            total = int(tail_m.group(1))
            up = part.upper()
            if "K8" in up:
                sticks, per_stick_gb = 8, total // 8
            elif "K4" in up:
                sticks, per_stick_gb = 4, total // 4
            elif "K2" in up:
                sticks, per_stick_gb = 2, total // 2
            else:
                sticks, per_stick_gb = 1, total
        else:
            return None

    blob = text.lower()
    profiles: list[str] = []
    if "expo" in blob:
        profiles.append("expo")
    if "xmp" in blob:
        profiles.append("xmp")
    if not profiles:
        profiles = ["jedec"]

    rgb = any(x in part.upper() for x in ("BBA", "BBE", "BBE2A", "RWA", "RSA", "RW", "WB", "BWA", "BWEA"))
    form_factor = "sodimm" if "so-dimm" in blob or re.search(r"\bSODIMM\b", text, re.I) else "dimm"
    if "rdimm" in blob or "registered" in blob:
        form_factor = "dimm"

    if part.startswith("KVR5"):
        series = "ValueRAM"
    elif part.startswith("KSM5"):
        series = "Server Premier"
    elif "Impact" in text:
        series = "FURY Impact"
    elif "Renegade" in text:
        series = "FURY Renegade"
    elif "Beast" in text:
        series = "FURY Beast"
    else:
        series = "FURY"

    if sticks == 1:
        cap_label = f"{per_stick_gb}GB (1x{per_stick_gb}GB)"
    else:
        cap_label = f"{sticks * per_stick_gb}GB ({sticks}x{per_stick_gb}GB)"
    product_name = f"{series} {cap_label} DDR5 {speed_mts} CL{cas}"

    return {
        "brand": "kingston",
        "part_number": part,
        "product_name": product_name,
        "sticks": sticks,
        "per_stick_gb": per_stick_gb,
        "speed_mts": speed_mts,
        "cas_latency": cas,
        "profiles": profiles,
        "rgb": rgb,
        "form_factor": form_factor,
        "source_url": f"https://www.kingston.com/en/memory/search?partid={part}",
    }


def throttle(seconds: float = 0.05) -> None:
    time.sleep(seconds)

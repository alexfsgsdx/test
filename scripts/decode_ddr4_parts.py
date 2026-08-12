#!/usr/bin/env python3
"""Decode manufacturer DDR4 desktop UDIMM part numbers into catalog fields."""

from __future__ import annotations

import re

JEDEC_CL = {2133: 15, 2400: 17, 2666: 19, 2933: 21, 3200: 22}


def norm_profiles(raw: list[str] | str | None, default: list[str] | None = None) -> list[str]:
    if isinstance(raw, str):
        blob = raw.lower()
        out: list[str] = []
        if "expo" in blob:
            out.append("expo")
        if "xmp" in blob:
            out.append("xmp")
        if not out:
            out = ["jedec"]
        return out
    if raw:
        return [p.lower() for p in raw]
    return default or ["jedec"]


def finalize(
    brand: str,
    part: str,
    *,
    product_name: str = "",
    sticks: int,
    per_stick_gb: int,
    speed_mts: int,
    cas_latency: int,
    profiles: list[str] | None = None,
    rgb: bool = False,
    form_factor: str = "dimm",
    source_url: str = "",
) -> dict:
    return {
        "brand": brand,
        "part_number": part.upper(),
        "product_name": product_name or part.upper(),
        "sticks": sticks,
        "per_stick_gb": per_stick_gb,
        "generation": 4,
        "speed_mts": speed_mts,
        "cas_latency": cas_latency,
        "profiles": norm_profiles(profiles),
        "rgb": rgb,
        "form_factor": form_factor,
        "source_url": source_url,
    }


def decode_corsair(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(
        r"^CM[A-Z0-9]*GX4M(?P<sticks>\d)[A-Z](?P<speed>\d{4})(?P<profile>[A-Z])(?P<cl>\d{2})$",
        p,
    )
    if not m:
        return None
    sticks = int(m.group("sticks"))
    speed = int(m.group("speed"))
    cl = int(m.group("cl"))
    cap_m = re.search(r"CM[A-Z](\d+)GX4", p)
    if not cap_m:
        return None
    total = int(cap_m.group(1))
    if total % sticks:
        return None
    per = total // sticks
    profile = m.group("profile").upper()
    profiles = ["both"] if profile == "Z" else ["xmp"] if profile in {"C", "D"} else ["jedec"]
    rgb = p[2:3] in {"H", "W", "P"} or "RGB" in product_name.upper()
    return finalize(
        "corsair", p,
        product_name=product_name or f"Corsair DDR4 {total}GB {speed} CL{cl}",
        sticks=sticks, per_stick_gb=per, speed_mts=speed, cas_latency=cl,
        profiles=profiles, rgb=rgb,
        source_url=source_url or f"https://www.corsair.com/us/en/p/memory/{p.lower()}",
    )


def decode_gskill(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^F4-(\d{4})C(\d{2,3})([A-Z])-(\d+)([A-Z0-9-]+)$", p)
    if not m:
        return None
    speed_mts, cl, _variant, cap_code, series = m.groups()
    speed_mts = int(speed_mts)
    cas = int(cl)
    cap = int(cap_code)
    sticks = 2 if cap >= 32 and cap % 16 == 0 else 1
    if cap >= 64:
        sticks = 4 if cap == 64 and "4X" in series.upper() else 2
    per = cap // sticks if cap % sticks == 0 else cap
    if sticks == 1 and cap in {8, 16, 32}:
        per = cap
    rgb = any(x in series.upper() for x in ("TZ", "TR", "RG", "RGB"))
    profiles = ["xmp"] if speed_mts >= 3000 else ["jedec"]
    return finalize(
        "gskill", p,
        product_name=product_name or f"G.Skill DDR4 {cap}GB {speed_mts} CL{cas}",
        sticks=sticks, per_stick_gb=per, speed_mts=speed_mts, cas_latency=cas,
        profiles=profiles, rgb=rgb, source_url=source_url,
    )


def decode_kingston(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper().replace(" ", "")
    m = re.match(
        r"KF4(?P<speed>\d{2})(?P<mod>[A-Z]?)(?P<cl>\d{2})(?P<series>[A-Z0-9]+?)(?P<kit>K[248])?[-/](?P<total>\d+)$",
        p,
    )
    if m and m.group("mod").upper() in {"", "C", "S", "R"}:
        speed_mts = int(m.group("speed")) * 100
        cas = int(m.group("cl"))
        total = int(m.group("total"))
        kit = (m.group("kit") or "").upper()
        sticks = {"K2": 2, "K4": 4, "K8": 8}.get(kit, 1)
        kit_m = re.search(r"\(\s*(\d+)\s*x\s*(\d+)\s*GB\s*\)", product_name, re.I)
        if kit_m:
            sticks = int(kit_m.group(1))
        if total % sticks:
            sticks = 1
        per = total // sticks
        rgb = any(x in p for x in ("BBA", "BBE", "RWA", "RSA", "RW"))
        profiles = ["xmp"] if "BB" in m.group("series") or "xmp" in product_name.lower() else ["jedec"]
        return finalize(
            "kingston", p,
            product_name=product_name or f"Kingston FURY DDR4 {total}GB {speed_mts} CL{cas}",
            sticks=sticks, per_stick_gb=per, speed_mts=speed_mts, cas_latency=cas,
            profiles=profiles, rgb=rgb, source_url=source_url or f"https://www.kingston.com/en/memory/search?partid={p}",
        )

    m2 = re.match(r"KVR(?P<speed>\d{2})(?P<ecc>[A-Z]?)(?P<cl>\d{2})(?P<series>[A-Z0-9]+)[-/](?P<total>\d+)$", p)
    if m2:
        speed_mts = int(m2.group("speed")) * 100
        cas = int(m2.group("cl"))
        total = int(m2.group("total"))
        series = m2.group("series").upper()
        kit_m = re.search(r"(K[248])$", series)
        kit = kit_m.group(1) if kit_m else ""
        sticks = {"K2": 2, "K4": 4, "K8": 8}.get(kit, 1)
        if total % sticks:
            sticks = 1
        per = total // sticks
        return finalize(
            "kingston", p,
            product_name=product_name or f"Kingston ValueRAM DDR4 {total}GB {speed_mts}",
            sticks=sticks, per_stick_gb=per, speed_mts=speed_mts, cas_latency=cas,
            profiles=["jedec"], source_url=source_url or f"https://www.kingston.com/en/memory/search?partid={p}",
        )
    return None


def decode_crucial(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^CT(2K|4K|8K)(\d+)G4([A-Z0-9]+)$", p)
    if m:
        kit, per, _tail = m.groups()
        sticks = {"2K": 2, "4K": 4, "8K": 8}[kit]
        per_stick = int(per)
        speed_mts, cas = 3200, 22
        if "266" in _tail or "A26" in _tail:
            speed_mts, cas = 2666, 19
        if "240" in _tail:
            speed_mts, cas = 2400, 17
        return finalize(
            "crucial", p,
            product_name=product_name or f"Crucial DDR4 {sticks * per_stick}GB Kit",
            sticks=sticks, per_stick_gb=per_stick, speed_mts=speed_mts, cas_latency=cas,
            profiles=["xmp"], source_url=source_url or f"https://www.crucial.com/memory/ddr4/{p.lower()}",
        )
    m = re.match(r"^CT(\d+)G4([A-Z0-9]+)$", p)
    if m:
        per, _tail = m.groups()
        per_stick = int(per)
        speed_mts, cas = 3200, 22
        if "266" in _tail:
            speed_mts, cas = 2666, 19
        return finalize(
            "crucial", p,
            product_name=product_name or f"Crucial DDR4 {per_stick}GB {speed_mts}",
            sticks=1, per_stick_gb=per_stick, speed_mts=speed_mts, cas_latency=cas,
            profiles=["jedec"], source_url=source_url or f"https://www.crucial.com/memory/ddr4/{p.lower()}",
        )
    m = re.match(r"^BL(2K|4K)?(\d+)G(\d{2,3})C(\d{2})U4$", p)
    if m:
        kit, per, speed, cl = m.groups()
        sticks = {"2K": 2, "4K": 4}.get(kit or "", 1)
        per_stick = int(per)
        return finalize(
            "ballistix", p,
            product_name=product_name or f"Ballistix DDR4 {sticks * per_stick}GB",
            sticks=sticks, per_stick_gb=per_stick, speed_mts=int(speed) * 100, cas_latency=int(cl),
            profiles=["xmp"], source_url=source_url,
        )
    return None


def decode_teamgroup(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    m = re.search(r"(\d{3,4})G(\d{4})HC(\d{2,3})", part, re.I)
    if not m:
        return None
    cap_code, speed_mts, cas = m.groups()
    speed_mts = int(speed_mts)
    if speed_mts >= 4800:
        return None
    cas = int(cas[:2])
    cap_code = cap_code.upper()
    if not cap_code.startswith("4"):
        return None
    body = cap_code[1:]
    if len(body) == 2:
        total_gb, sticks = int(body), 1
    elif len(body) == 3:
        total_gb = int(body[:2])
        stick_digit = int(body[2])
        sticks = stick_digit if stick_digit in (1, 2, 4) else 2
    else:
        total_gb = int(body[:3]) if len(body) >= 3 else int(body)
        sticks = 2 if total_gb >= 32 else 1
    if total_gb % sticks:
        sticks = 2 if "DC" in part.upper() or total_gb >= 32 else 1
    per = total_gb // sticks
    rgb = any(tag in part.upper() for tag in ("ARB", "RGD", "RGB")) or "rgb" in product_name.lower()
    profiles = ["xmp"] if speed_mts >= 3000 else ["jedec"]
    return finalize(
        "teamgroup", part.upper(),
        product_name=product_name or f"TeamGroup DDR4 {total_gb}GB {speed_mts} CL{cas}",
        sticks=sticks, per_stick_gb=per, speed_mts=speed_mts, cas_latency=cas,
        profiles=profiles, rgb=rgb, source_url=source_url,
    )


def decode_patriot(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^(PSP|PSD|PV)(4)?(\d{2})G(\d{4})(K?H?\d?)$", p)
    if m:
        _, _, total, speed_code, kit = m.groups()
        total_gb = int(total)
        speed_mts = int(speed_code)
        sticks = 2 if kit else 1
        per = total_gb // sticks
        return finalize(
            "patriot", p,
            product_name=product_name or f"Patriot DDR4 {total_gb}GB {speed_mts}",
            sticks=sticks, per_stick_gb=per, speed_mts=speed_mts,
            cas_latency=JEDEC_CL.get(speed_mts, 22), profiles=["jedec"], source_url=source_url,
        )
    m = re.match(r"^PV4(\d{2})G(\d{2,4})C(\d{2})(K?)$", p)
    if m:
        total, speed_code, cl, kit = m.groups()
        speed_raw = int(speed_code)
        speed_mts = speed_raw * 100 if speed_raw < 1000 else speed_raw
        sticks = 2 if kit else 1
        per = int(total) // sticks
        return finalize(
            "patriot", p,
            product_name=product_name or f"Patriot Viper DDR4 {int(total)}GB {speed_mts}",
            sticks=sticks, per_stick_gb=per, speed_mts=speed_mts, cas_latency=int(cl),
            profiles=["xmp"], rgb="RGB" in p, source_url=source_url,
        )
    return None


def decode_xpg(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^AX4U(\d{4})C(\d{2})(\d{1,3})G(-[A-Z0-9-]+)?$", p)
    if not m:
        m = re.match(r"^AX4U(\d{4})(\d{2})G(\d{1,3})G?([A-Z-]*)(-[A-Z0-9-]+)?$", p)
        if not m:
            return None
        speed_mts, cl, per, mid, suffix = m.groups()
        suffix = (suffix or "") + (mid or "")
    else:
        speed_mts, cl, per, suffix = m.groups()
        suffix = suffix or ""
    per_stick = int(per)
    sticks = 2 if suffix.startswith("-DC") or "DCL" in suffix or "DTBK" in suffix else 1
    rgb = "AR" in suffix or "RGB" in suffix or "D35" in suffix or "WBK" in suffix
    return finalize(
        "xpg", p,
        product_name=product_name or f"XPG DDR4 {per_stick}GB {speed_mts}",
        sticks=sticks, per_stick_gb=per_stick, speed_mts=int(speed_mts), cas_latency=int(cl),
        profiles=["xmp"] if int(speed_mts) >= 3000 else ["jedec"], rgb=rgb, source_url=source_url,
    )


def decode_pny(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^MD(\d{2})G(K\d)D4(\d{4})(\d{2})(X?R?)(RGB?)?$", p)
    if not m:
        m = re.match(r"^MD(\d{2})G(K\d)?D4(\d{4})(\d{3})(X?R?)(RGB?)?$", p)
        if not m:
            return None
        total, kit, speed_mts, cl, _, rgb_suffix = m.groups()
        total_gb = int(total)
        sticks = int(kit[1]) if kit else 1
        per = total_gb // sticks
        rgb = bool(rgb_suffix)
        return finalize(
            "pny", p,
            product_name=product_name or f"PNY DDR4 {total_gb}GB {speed_mts}",
            sticks=sticks, per_stick_gb=per, speed_mts=int(speed_mts), cas_latency=int(cl[:2]),
            profiles=["xmp"], rgb=rgb, source_url=source_url,
        )
    total, kit, speed_mts, cl, _, rgb_suffix = m.groups()
    total_gb = int(total)
    sticks = int(kit[1])
    per = total_gb // sticks if total_gb % sticks == 0 else total_gb // 2
    rgb = bool(rgb_suffix)
    return finalize(
        "pny", p,
        product_name=product_name or f"PNY DDR4 {total_gb}GB {speed_mts}",
        sticks=sticks, per_stick_gb=per, speed_mts=int(speed_mts), cas_latency=int(cl),
        profiles=["xmp"], rgb=rgb, source_url=source_url,
    )


def decode_ballistix(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    if p.startswith("BLT"):
        m = re.match(r"^BLT(2K|4K)(\d+)G4D(\d{2,4})AET4K$", p)
        if m:
            kit, per, speed_code = m.groups()
            sticks = {"2K": 2, "4K": 4}[kit]
            per_stick = int(per)
            speed_raw = int(speed_code)
            speed_mts = speed_raw * 100 if speed_raw < 1000 else speed_raw
            return finalize(
                "ballistix", p,
                product_name=product_name or f"Ballistix Tactical Tracer RGB DDR4",
                sticks=sticks, per_stick_gb=per_stick, speed_mts=speed_mts, cas_latency=16,
                profiles=["xmp"], rgb=True, source_url=source_url,
            )
    return decode_crucial(part, product_name, source_url) if p.startswith("BL") else None


def decode_adata(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    return decode_xpg(part.replace("AD4", "AX4"), product_name, source_url) if "4U" in part.upper() else None


def decode_geil(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^GA[A-Z0-9]*4(\d{2})GB(\d{4})C(\d{2})", p)
    if not m:
        return None
    total, speed_mts, cl = m.groups()
    total_gb = int(total)
    sticks = 2 if total_gb >= 16 else 1
    per = total_gb // sticks
    return finalize(
        "geil", p,
        product_name=product_name or f"GeIL DDR4 {total_gb}GB {speed_mts}",
        sticks=sticks, per_stick_gb=per, speed_mts=int(speed_mts), cas_latency=int(cl),
        profiles=["xmp"], rgb="RGB" in p, source_url=source_url,
    )


def decode_mushkin(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^MR4U(\d{4})C(\d{2})(\d{2})G(X\d)?$", p)
    if not m:
        return None
    speed_mts, cl, total, kit = m.groups()
    total_gb = int(total)
    sticks = int(kit[1]) if kit else 1
    per = total_gb // sticks
    return finalize(
        "mushkin", p,
        product_name=product_name or f"Mushkin DDR4 {total_gb}GB {speed_mts}",
        sticks=sticks, per_stick_gb=per, speed_mts=int(speed_mts), cas_latency=int(cl),
        profiles=["xmp"], source_url=source_url,
    )


def decode_silicon_power(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^SP(\d{3})GLHU(\d{4})B(\d{2})A4(X\d)?$", p)
    if not m:
        return None
    per_code, speed_mts, cl, kit = m.groups()
    per = int(per_code)
    sticks = int(kit[1]) if kit else 1
    return finalize(
        "silicon_power", p,
        product_name=product_name or f"Silicon Power DDR4 {per * sticks}GB {speed_mts}",
        sticks=sticks, per_stick_gb=per, speed_mts=int(speed_mts), cas_latency=int(cl),
        profiles=["jedec"], source_url=source_url,
    )


def decode_oloy(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^(MD|ND)4U16(\d{2})(\d{2})\d([A-Z]+)(DE|DA)$", p)
    if not m:
        return None
    _, speed_hi, cl, rgb_code, _ = m.groups()
    speed_mts = int(speed_hi) * 100
    return finalize(
        "oloy", p,
        product_name=product_name or f"OLOy DDR4 32GB {speed_mts}",
        sticks=2, per_stick_gb=16, speed_mts=speed_mts, cas_latency=int(cl),
        profiles=["xmp"], rgb="R" in rgb_code, source_url=source_url,
    )


def decode_micron(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^MTA(\d+)ASF(\d{2})C(\d{2})(K\d)?$", p)
    if not m:
        return None
    per, speed_hi, cl, kit = m.groups()
    speed_mts = int(speed_hi) * 100
    sticks = int(kit[1]) if kit else 1
    per_stick = int(per)
    return finalize(
        "micron", p,
        product_name=product_name or f"Micron DDR4 {per_stick * sticks}GB {speed_mts}",
        sticks=sticks, per_stick_gb=per_stick, speed_mts=speed_mts, cas_latency=int(cl),
        profiles=["jedec"], source_url=source_url,
    )


DECODERS = {
    "corsair": decode_corsair,
    "gskill": decode_gskill,
    "kingston": decode_kingston,
    "crucial": decode_crucial,
    "ballistix": decode_ballistix,
    "teamgroup": decode_teamgroup,
    "patriot": decode_patriot,
    "xpg": decode_xpg,
    "pny": decode_pny,
    "adata": decode_adata,
    "geil": decode_geil,
    "mushkin": decode_mushkin,
    "silicon_power": decode_silicon_power,
    "oloy": decode_oloy,
    "micron": decode_micron,
}


def decode_part(brand: str, part: str, **kwargs) -> dict | None:
    fn = DECODERS.get(brand)
    if not fn:
        return None
    return fn(part, **kwargs)

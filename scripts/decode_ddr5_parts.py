#!/usr/bin/env python3
"""Decode manufacturer DDR5 desktop UDIMM part numbers into catalog fields."""

from __future__ import annotations

import re

JEDEC_CL = {4800: 40, 5200: 42, 5600: 46, 6000: 48, 6400: 52}


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
        "speed_mts": speed_mts,
        "cas_latency": cas_latency,
        "profiles": norm_profiles(profiles),
        "rgb": rgb,
        "form_factor": form_factor,
        "source_url": source_url,
    }


def decode_crucial(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^(CP|CT)(2K|4K)(\d+)G(\d{2,3})C(\d{2})U5([BW])?$", p)
    if m:
        _, kit, per, speed, cl, color = m.groups()
        sticks = {"2K": 2, "4K": 4}[kit]
        per_stick = int(per)
        speed_mts = int(speed) * 100
        cas = int(cl)
        profiles = ["both"] if speed_mts >= 6000 or "pro" in product_name.lower() else ["jedec"]
        if speed_mts == 5600 and cas == 46:
            profiles = ["both"]
        name = product_name or f"Crucial {'Pro ' if p.startswith('CP') else ''}DDR5-{speed_mts} {sticks * per_stick}GB Kit ({per_stick}GBx{sticks})"
        return finalize(
            "crucial", p, product_name=name, sticks=sticks, per_stick_gb=per_stick,
            speed_mts=speed_mts, cas_latency=cas, profiles=profiles, rgb=False,
            source_url=source_url or f"https://www.crucial.com/memory/ddr5/{p.lower()}",
        )
    m = re.match(r"^CP3U(\d+)G(\d{2,3})C(\d{2})U5$", p)
    if m:
        per, speed, cl = m.groups()
        per_stick = int(per)
        if per_stick == 16:
            per_stick = 32
        speed_mts = int(speed) * 100
        return finalize(
            "crucial", p,
            product_name=product_name or f"Crucial Pro DDR5-{speed_mts} {per_stick}GB UDIMM",
            sticks=1, per_stick_gb=per_stick, speed_mts=speed_mts, cas_latency=int(cl),
            profiles=["both"], source_url=source_url or f"https://www.crucial.com/memory/ddr5/{p.lower()}",
        )
    m = re.match(r"^CT(\d+)G(\d{2,3})C(\d{2})U5$", p)
    if m:
        per, speed, cl = m.groups()
        speed_mts = int(speed) * 100
        return finalize(
            "crucial", p,
            product_name=product_name or f"Crucial DDR5-{speed_mts} {int(per)}GB UDIMM",
            sticks=1, per_stick_gb=int(per), speed_mts=speed_mts, cas_latency=int(cl),
            profiles=["jedec"], source_url=source_url or f"https://www.crucial.com/memory/ddr5/{p.lower()}",
        )
    return None


def decode_patriot(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    rgb = bool(re.search(r"PVVR|PVXR|PVER|RGB", p))
    m = re.match(r"^(PVER|VEB)5?(\d{2})G(\d{2,4})C(\d{2})(K?W?)$", p)
    if m:
        total, speed_code, cl, kit = m.group(2), m.group(3), m.group(4), m.group(5)
    else:
        m = re.match(r"^PV[A-Z0-9]*?5?(\d{2})G(\d{2,4})C(\d{2})(K?W?)$", p)
        if not m:
            m = re.match(r"^(PSD)5(\d{2})G(\d{4})(K?)$", p)
            if m:
                _, total, speed_code, kit = m.groups()
                total_gb = int(total)
                speed_mts = int(speed_code)
                sticks = 2 if kit else 1
                per = total_gb // sticks
                return finalize(
                    "patriot", p,
                    product_name=product_name or f"Patriot Signature Line DDR5 {total_gb}GB {speed_mts}MT/s",
                    sticks=sticks, per_stick_gb=per, speed_mts=speed_mts,
                    cas_latency=JEDEC_CL.get(speed_mts, 40), profiles=["jedec"], rgb=False,
                    source_url=source_url,
                )
            return None
        total, speed_code, cl, kit = m.groups()
    total_gb = int(total)
    speed_raw = int(speed_code)
    speed_mts = speed_raw * 100 if speed_raw < 1000 else speed_raw
    sticks = 2 if kit else 1
    if sticks == 1 and total_gb in {16, 32, 48, 64}:
        sticks = 2
    per = total_gb // sticks
    profiles = ["both"] if speed_mts >= 6000 else ["xmp"]
    if "VENOM" in product_name.upper() or "ELITE" in product_name.upper():
        profiles = ["both"]
    return finalize(
        "patriot", p,
        product_name=product_name or f"Patriot Viper DDR5 {sticks * per}GB {speed_mts}MT/s CL{cl}",
        sticks=sticks, per_stick_gb=per, speed_mts=speed_mts, cas_latency=int(cl),
        profiles=profiles, rgb=rgb, source_url=source_url,
    )


def decode_xpg(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^AX5U(\d{4})C(\d{2})(\d{1,3})G(-[A-Z0-9-]+)?$", p)
    if not m:
        return None
    speed_mts, cl, per, suffix = m.groups()
    per_stick = int(per)
    if per_stick not in {8, 16, 24, 32, 48, 64}:
        return None
    suffix = suffix or ""
    sticks = 2 if suffix.startswith("-DC") or "DCL" in suffix else 1
    rgb = "AR" in suffix or "RGB" in suffix or "RBK" in suffix
    profiles = ["both"] if int(speed_mts) >= 6000 else ["jedec"]
    return finalize(
        "xpg", p,
        product_name=product_name or f"XPG DDR5 {per_stick}GB {speed_mts}MT/s CL{cl}",
        sticks=sticks, per_stick_gb=per_stick, speed_mts=int(speed_mts), cas_latency=int(cl),
        profiles=profiles, rgb=rgb, source_url=source_url,
    )


def decode_pny(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^MD(\d{2})G(K\d)?D(\d{4})(\d{3})(M?)(X?)(RGB?|XR)?$", p)
    if not m:
        return None
    total, kit, speed_mts, cl, _, _, rgb_suffix = m.groups()
    total_gb = int(total)
    sticks = int(kit[1]) if kit else 1
    per = total_gb // sticks
    rgb = bool(rgb_suffix and "RGB" in rgb_suffix)
    profiles = ["both"] if "M" in (m.group(5) or "") else ["xmp"]
    if int(speed_mts) == 5600:
        profiles = ["jedec"]
    return finalize(
        "pny", p,
        product_name=product_name or f"PNY XLR8 DDR5 {total_gb}GB {speed_mts}MT/s",
        sticks=sticks, per_stick_gb=per, speed_mts=int(speed_mts), cas_latency=int(cl[:2]),
        profiles=profiles, rgb=rgb, source_url=source_url,
    )


def decode_oloy(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^(MD|ND)5U16(\d{2})(\d{2})\d([A-Z]+)(DE|DA)$", p)
    if not m:
        return None
    _, speed_hi, cl, rgb_code, _ = m.groups()
    speed_mts = int(speed_hi) * 100
    cas = int(cl)
    rgb = "R" in rgb_code or "I" in rgb_code
    sticks = 2
    per = 16
    profiles = ["jedec"] if speed_mts <= 4800 else ["xmp"]
    return finalize(
        "oloy", p,
        product_name=product_name or f"OLOy Blade DDR5 32GB {speed_mts}MT/s",
        sticks=sticks, per_stick_gb=per, speed_mts=speed_mts, cas_latency=cas,
        profiles=profiles, rgb=rgb,
        source_url=source_url or "https://www.oloymemory.com/products.html",
    )


def decode_geil(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^GA([A-Z]{3})(\d{3})GB(\d{4})C(\d{2})([A-Z]+)$", p)
    if not m:
        return None
    _, total_code, speed_mts, cl, suffix = m.groups()
    total = int(total_code[1:]) if total_code[0] == "5" else int(total_code)
    sticks = 2
    per = total // sticks
    rgb = "R" in suffix or "S" in suffix[:2]
    return finalize(
        "geil", p,
        product_name=product_name or f"GeIL DDR5 {total}GB {speed_mts}MT/s CL{cl}",
        sticks=sticks, per_stick_gb=per, speed_mts=int(speed_mts), cas_latency=int(cl),
        profiles=["both"], rgb=rgb, source_url=source_url or "https://geilmemory.com/",
    )


def decode_mushkin(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^(MRE5U|MLA5C)(\d{3,4})([A-Z0-9]+)(\d{2})G(X2)?$", p)
    if not m:
        return None
    series, speed_raw, _mid, per_raw, kit = m.groups()
    speed_mts = int(speed_raw)
    if speed_mts < 1000:
        speed_mts *= 100
    sticks = 2 if kit else 1
    per = int(per_raw)
    rgb = series.startswith("MLA")
    profiles = ["xmp"] if rgb or speed_mts >= 6000 else ["jedec"]
    return finalize(
        "mushkin", p,
        product_name=product_name or f"Mushkin Redline DDR5 {sticks * per}GB {speed_mts}MT/s",
        sticks=sticks, per_stick_gb=per, speed_mts=speed_mts,
        cas_latency=30 if rgb else JEDEC_CL.get(speed_mts, 40),
        profiles=profiles, rgb=rgb,
        source_url=source_url or "https://mushkin.com/product-category/memory/ddr5/",
    )


def decode_silicon_power(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^SP(\d{3})GXLWU(\d{2,4})([AF])([A-Z]{3,4})$", p)
    if not m:
        return None
    total, speed_raw, tier, suffix = m.groups()
    total_gb = int(total)
    speed_mts = int(speed_raw)
    if speed_mts < 1000:
        speed_mts *= 100
    sticks = 2
    per = total_gb // sticks
    rgb = suffix.endswith("F") or "FDF" in p
    cl = 30 if tier == "A" and speed_mts >= 6000 else 40
    if "64A" in p:
        cl = 32
    return finalize(
        "silicon_power", p,
        product_name=product_name or f"Silicon Power XPOWER Zenith DDR5 {total_gb}GB {speed_mts}MT/s",
        sticks=sticks, per_stick_gb=per, speed_mts=speed_mts, cas_latency=cl,
        profiles=["xmp"], rgb=rgb,
        source_url=source_url or "https://www.silicon-power.com/web/product-Zenith_DDR5_Gaming_UDIMM",
    )


def decode_klevv(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^(KD5[A-Z0-9]+)-(\d{2})([A-Z])(\d{3})([A-Z?])?(\d*)G?$", p)
    if not m:
        return None
    prefix, speed_hi, profile_code, cl_raw, variant, _ = m.groups()
    speed_mts = int(speed_hi) * 100
    cas = int(cl_raw[0:2]) if cl_raw else 30
    rgb = "A" in prefix or "U" in prefix
    sticks = 2
    per = 24 if "KG" in prefix or "320S" in p else 16
    if "48" in product_name or "XR5" in product_name.upper():
        per = 24
    profiles = ["both"] if profile_code in {"A", "B"} else ["xmp"]
    return finalize(
        "klevv", p,
        product_name=product_name or f"KLEVV CRAS DDR5 {sticks * per}GB {speed_mts}MT/s",
        sticks=sticks, per_stick_gb=per, speed_mts=speed_mts, cas_latency=cas,
        profiles=profiles, rgb=rgb,
        source_url=source_url or "https://www.klevv.com/ken/product/memory",
    )


def decode_lexar(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^LD5([A-Z]*)(\d+)G(\d{2})C(\d{2})([A-Z-]*-)?(RGD|BK)?$", p)
    if not m:
        m = re.match(r"^LD5EU(\d+)G-R(\d{4})GDLA$", p)
        if m:
            per, speed_mts = m.groups()
            return finalize(
                "lexar", p,
                product_name=product_name or f"Lexar ARES RGB DDR5 32GB {speed_mts}MT/s",
                sticks=2, per_stick_gb=int(per), speed_mts=int(speed_mts), cas_latency=32,
                profiles=["both"], rgb=True,
                source_url=source_url or "https://americas.lexar.com/product-category/memory/desktop-memory/",
            )
        return None
    _, per, speed_hi, cl, _, _ = m.groups()
    speed_mts = int(speed_hi) * 100
    per_stick = int(per)
    sticks = 2
    return finalize(
        "lexar", p,
        product_name=product_name or f"Lexar ARES RGB DDR5 {sticks * per_stick}GB {speed_mts}MT/s",
        sticks=sticks, per_stick_gb=per_stick, speed_mts=speed_mts, cas_latency=int(cl),
        profiles=["both"], rgb=True, source_url=source_url,
    )


def decode_apacer(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^AH5U(\d+)G(\d{2,4})C(\d{2,3})([A-Z]{4})-(\d+)$", p)
    if not m:
        return None
    per, speed_raw, cl, suffix, sticks = m.groups()
    rgb = "NW" in suffix
    speed_mts = int(speed_raw)
    if speed_mts < 1000:
        speed_mts *= 100
    cas = int(cl[:2])
    if cas > 52:
        cas = {6000: 38, 6400: 32, 6800: 34, 8000: 38}.get(speed_mts, 36)
    return finalize(
        "apacer", p,
        product_name=product_name or f"Apacer NOX {'RGB ' if rgb else ''}DDR5 {int(sticks)*int(per)}GB {speed_mts}MT/s",
        sticks=int(sticks), per_stick_gb=int(per), speed_mts=int(speed_mts), cas_latency=cas,
        profiles=["both"], rgb=rgb,
        source_url=source_url or "https://www.apacer.com/en/product/zadak-product/detail/zadak_memory/nox_ddr5",
    )


def decode_vcolor(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^TMXPL(\d{2})(\d{2})(\d{3})KWK$", p)
    if m:
        per, speed_hi, cl_raw = m.groups()
        per_stick = int(per)
        speed_mts = int(speed_hi) * 100
        cas = int(cl_raw[-2:]) if int(cl_raw[-2:]) >= 20 else int(cl_raw[0] + cl_raw[-1])
    else:
        m = re.match(r"^TMXPL(\d{3})(\d{4})KWK$", p)
        if not m:
            return None
        cap, speed_raw = m.groups()
        per_stick = int(cap)
        speed_mts = int(speed_raw)
        cas = {8000: 38, 8200: 40}.get(speed_mts, 38)
    sticks = 2
    return finalize(
        "vcolor", p,
        product_name=product_name or f"v-color Manta XPrism RGB DDR5 {sticks * per_stick}GB {speed_mts}MT/s",
        sticks=sticks, per_stick_gb=per_stick, speed_mts=speed_mts, cas_latency=cas,
        profiles=["xmp"], rgb=True, source_url=source_url or "https://v-color.net/",
    )


def decode_timetec(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^75TT(\d{2})NU\dR8-(\d+)GK2$", p)
    if m:
        speed_hi, cap = m.groups()
        speed_mts = int(speed_hi) * 100
        return finalize(
            "timetec", p,
            product_name=product_name or f"Timetec Premium DDR5 {int(cap) * 2}GB Kit {speed_mts}MT/s",
            sticks=2, per_stick_gb=int(cap), speed_mts=speed_mts,
            cas_latency=JEDEC_CL.get(speed_mts, 40), profiles=["jedec"], rgb=False,
            source_url=source_url or "https://timetecinc.com/collections/all",
        )
    m = re.match(r"^75TT(\d{2})NU\dR8-(\d+)G$", p)
    if not m:
        return None
    speed_hi, cap = m.groups()
    speed_mts = int(speed_hi) * 100
    return finalize(
        "timetec", p,
        product_name=product_name or f"Timetec Premium DDR5 {int(cap)}GB {speed_mts}MT/s",
        sticks=1, per_stick_gb=int(cap), speed_mts=speed_mts,
        cas_latency=JEDEC_CL.get(speed_mts, 40), profiles=["jedec"], rgb=False,
        source_url=source_url or "https://timetecinc.com/collections/all",
    )


def decode_adata(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^AD5U5600(\d+)G-([A-Z]+)$", p)
    speed_mts = 5600
    if not m:
        m = re.match(r"^AD5U4800(\d+)G-([A-Z]+)$", p)
        speed_mts = 4800
    if not m:
        return None
    cap_token, _variant = m.groups()
    cap_map = {"08": 8, "016": 16, "024": 24, "032": 32, "048": 48, "064": 64}
    per = cap_map.get(cap_token, int(cap_token.replace("G", "")))
    return finalize(
        "adata", p,
        product_name=product_name or f"ADATA DDR5-{speed_mts} {per}GB UDIMM",
        sticks=1, per_stick_gb=per, speed_mts=speed_mts,
        cas_latency=JEDEC_CL.get(speed_mts, 46), profiles=["jedec"], rgb=False,
        source_url=source_url,
    )


def decode_samsung(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    m = re.match(r"^M32(\d)R(\d)GA(\d)BB0-C([A-Z0-9]+)$", p)
    if not m:
        return None
    gen, rank, density, tail = m.groups()
    density_map = {"1": 8, "2": 16, "4": 16, "6": 32, "8": 64}
    per = density_map.get(density, 16)
    sticks = 2 if "K" in tail else 1
    if rank == "1" and sticks == 2:
        per = 8
    speed_mts = 4800 if "48" in tail or "CQ" in tail else 5600
    return finalize(
        "samsung", p,
        product_name=product_name or f"Samsung DDR5 {sticks * per}GB {speed_mts}MT/s UDIMM",
        sticks=sticks, per_stick_gb=per, speed_mts=speed_mts,
        cas_latency=JEDEC_CL.get(speed_mts, 40), profiles=["jedec"], rgb=False,
        source_url=source_url or "https://semiconductor.samsung.com/dram/module/udimm/",
    )


def decode_hynix(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    if not p.startswith("HMCG") or len(p) < 12:
        return None
    per = 32 if "88" in p[4:6] else 16
    speed_mts = 5600 if "A" in p[6:10] else 4800
    return finalize(
        "hynix", p,
        product_name=product_name or f"SK hynix DDR5 {per}GB {speed_mts}MT/s UDIMM",
        sticks=1, per_stick_gb=per, speed_mts=speed_mts,
        cas_latency=JEDEC_CL.get(speed_mts, 40), profiles=["jedec"], rgb=False,
        source_url=source_url or "https://www.skhynix.com/",
    )


def decode_micron(part: str, product_name: str = "", source_url: str = "") -> dict | None:
    p = part.upper()
    if not p.startswith("MTC"):
        return None
    per = 32 if "832" in p or "864" in p else 16
    speed_mts = 5600 if "56" in p else 4800
    return finalize(
        "micron", p,
        product_name=product_name or f"Micron DDR5 {per}GB {speed_mts}MT/s UDIMM",
        sticks=1, per_stick_gb=per, speed_mts=speed_mts,
        cas_latency=JEDEC_CL.get(speed_mts, 40), profiles=["jedec"], rgb=False,
        source_url=source_url or "https://www.micron.com/products/memory/dram-components/ddr5-sdram",
    )


DECODERS = {
    "crucial": decode_crucial,
    "patriot": decode_patriot,
    "xpg": decode_xpg,
    "pny": decode_pny,
    "oloy": decode_oloy,
    "geil": decode_geil,
    "mushkin": decode_mushkin,
    "silicon_power": decode_silicon_power,
    "klevv": decode_klevv,
    "lexar": decode_lexar,
    "apacer": decode_apacer,
    "vcolor": decode_vcolor,
    "timetec": decode_timetec,
    "adata": decode_adata,
    "samsung": decode_samsung,
    "hynix": decode_hynix,
    "micron": decode_micron,
}


def decode_part(brand: str, part: str, **kwargs) -> dict | None:
    fn = DECODERS.get(brand)
    if not fn:
        return None
    return fn(part, **kwargs)

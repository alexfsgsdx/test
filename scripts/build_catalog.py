#!/usr/bin/env python3
"""Build data/catalog.json from normalized product records."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "catalog.json"
DOCS = ROOT / "docs" / "catalog.json"
VERIFIED = "2026-08-12"


def norm_profiles(raw) -> list[str]:
    if isinstance(raw, str):
        raw = [raw]
    out: set[str] = set()
    for p in raw:
        key = p.lower().replace(" ", "").replace(".", "")
        if "xmp" in key:
            out.add("xmp")
        elif "expo" in key:
            out.add("expo")
        elif key in {"both", "dual"}:
            out.update({"xmp", "expo"})
        elif "jedec" in key:
            out.add("jedec")
    if "xmp" in out and "expo" in out:
        out.discard("xmp")
        out.discard("expo")
        out.add("both")
    return sorted(out) or ["jedec"]


def norm_gen(g) -> int:
    if isinstance(g, int):
        return g
    return 5 if "5" in str(g) else 4


def norm_ff(ff: str) -> str:
    return "sodimm" if "so" in ff.lower() else "dimm"


def norm_ecc(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).lower() in {"ecc", "true", "yes", "1"}


def entry(
    brand: str,
    part_number: str,
    product_name: str,
    sticks: int,
    per_stick_gb: int,
    generation,
    speed_mts: int,
    cas_latency: int,
    profiles,
    rgb: bool = False,
    form_factor: str = "dimm",
    ecc=False,
    source_url: str = "",
) -> dict:
    return {
        "brand": brand,
        "part_number": part_number,
        "product_name": product_name,
        "sticks": sticks,
        "per_stick_gb": per_stick_gb,
        "total_gb": sticks * per_stick_gb,
        "generation": norm_gen(generation),
        "speed_mts": speed_mts,
        "cas_latency": cas_latency,
        "profiles": norm_profiles(profiles),
        "rgb": rgb,
        "form_factor": norm_ff(form_factor),
        "ecc": norm_ecc(ecc),
        "source_url": source_url,
        "source": "manufacturer",
        "verified": VERIFIED,
    }


def corsair(url_slug: str, **kw) -> dict:
    pn = url_slug.split("/")[0].upper()
    base = f"https://www.corsair.com/us/en/p/memory/{url_slug.lower()}"
    return entry("corsair", pn, source_url=base, **kw)


def kingston(part: str, **kw) -> dict:
    return entry(
        "kingston",
        part,
        source_url=f"https://www.kingston.com/en/memory/search?partid={part.replace('/', '%2F')}",
        **kw,
    )


def gskill(part: str, spec_path: str, **kw) -> dict:
    return entry(
        "gskill",
        part,
        source_url=f"https://www.gskill.com/specification/{spec_path}",
        **kw,
    )


def crucial(slug: str, **kw) -> dict:
    pn = slug.upper()
    return entry("crucial", pn, source_url=f"https://www.crucial.com/memory/ddr5/{slug.lower()}", **kw)


def teamgroup(path: str, **kw) -> dict:
    pn = path.split("-")[-1].upper()
    return entry(
        "teamgroup",
        pn,
        source_url=f"https://www.teamgroupinc.com/en/product-detail/memory/{path}/",
        **kw,
    )


PRODUCTS: list[dict] = []

# ── Corsair ──────────────────────────────────────────────────────────────────
C = PRODUCTS.extend
C([
    corsair(
        "cmk32gx5m2b6000c30/vengeance-32gb-2x16gb-ddr5-dram-6000mt-s-c30-memory-kit-black-cmk32gx5m2b6000c30",
        product_name="VENGEANCE 32GB (2x16GB) DDR5 6000 CL30",
        sticks=2, per_stick_gb=16, generation=5, speed_mts=6000, cas_latency=30, profiles=["xmp"],
    ),
    corsair(
        "cmk32gx5m2b6000z30/vengeance-32gb-2x16gb-ddr5-dram-6000mt-s-cl30-amd-expo-memory-black-cmk32gx5m2b6000z30",
        product_name="VENGEANCE 32GB (2x16GB) DDR5 6000 CL30 XMP/EXPO",
        sticks=2, per_stick_gb=16, generation=5, speed_mts=6000, cas_latency=30, profiles=["both"],
    ),
    corsair(
        "cmh32gx5m2b6000c30/vengeance-rgb-32gb-2x16gb-ddr5-dram-6000mt-s-c30-memory-kit-black-cmh32gx5m2b6000c30",
        product_name="VENGEANCE RGB 32GB (2x16GB) DDR5 6000 CL30",
        sticks=2, per_stick_gb=16, generation=5, speed_mts=6000, cas_latency=30, profiles=["xmp"], rgb=True,
    ),
    corsair(
        "cmk32gx5m2b6400c32/vengeance-32gb-2x16gb-ddr5-dram-6400mhz-c32-memory-kit-black-cmk32gx5m2b6400c32",
        product_name="VENGEANCE 32GB (2x16GB) DDR5 6400 CL32",
        sticks=2, per_stick_gb=16, generation=5, speed_mts=6400, cas_latency=32, profiles=["xmp"],
    ),
    corsair(
        "cmk32gx5m2b6400z36/vengeance-32gb-2x16gb-ddr5-dram-6400mt-s-cl36-memory-kit-cmk32gx5m2b6400z36",
        product_name="VENGEANCE 32GB (2x16GB) DDR5 6400 CL36 XMP/EXPO",
        sticks=2, per_stick_gb=16, generation=5, speed_mts=6400, cas_latency=36, profiles=["both"],
    ),
    corsair(
        "cmk32gx5m2b5600c36/vengeance-32gb-2x16gb-ddr5-dram-5600mt-s-c36-memory-kit-black-cmk32gx5m2b5600c36",
        product_name="VENGEANCE 32GB (2x16GB) DDR5 5600 CL36",
        sticks=2, per_stick_gb=16, generation=5, speed_mts=5600, cas_latency=36, profiles=["xmp"],
    ),
    corsair(
        "cmk16gx5m2b5600c36/vengeance-16gb-2x8gb-ddr5-dram-5600mt-s-c36-memory-kit-black-cmk16gx5m2b5600c36",
        product_name="VENGEANCE 16GB (2x8GB) DDR5 5600 CL36",
        sticks=2, per_stick_gb=8, generation=5, speed_mts=5600, cas_latency=36, profiles=["xmp"],
    ),
    corsair(
        "cmk16gx5m2b5200z40/vengeance-16gb-2x8gb-ddr5-dram-5200mt-s-cl40-memory-kit-cmk16gx5m2b5200z40",
        product_name="VENGEANCE 16GB (2x8GB) DDR5 5200 CL40",
        sticks=2, per_stick_gb=8, generation=5, speed_mts=5200, cas_latency=40, profiles=["both"],
    ),
    corsair(
        "cmk32gx5m2a4800c40/vengeancea-32gb-2x16gb-ddr5-dram-4800mhz-c40-memory-kit-a-black-cmk32gx5m2a4800c40",
        product_name="VENGEANCE 32GB (2x16GB) DDR5 4800 CL40",
        sticks=2, per_stick_gb=16, generation=5, speed_mts=4800, cas_latency=40, profiles=["xmp"],
    ),
    corsair(
        "cmk32gx5m2x7200c34/vengeance-32gb-2x16gb-ddr5-dram-7200mhz-c34-memory-kit-black-cmk32gx5m2x7200c34",
        product_name="VENGEANCE 32GB (2x16GB) DDR5 7200 CL34",
        sticks=2, per_stick_gb=16, generation=5, speed_mts=7200, cas_latency=34, profiles=["xmp"],
    ),
    corsair(
        "cmk64gx5m2b6000z30/vengeance-64gb-2x32gb-ddr5-dram-6000mt-s-cl30-amd-expo-memory-kit-cmk64gx5m2b6000z30",
        product_name="VENGEANCE 64GB (2x32GB) DDR5 6000 CL30",
        sticks=2, per_stick_gb=32, generation=5, speed_mts=6000, cas_latency=30, profiles=["both"],
    ),
    corsair(
        "cmk64gx5m2b5200z40/vengeance-64gb-2x32gb-ddr5-dram-5200mt-s-cl40-amd-expo-memory-kit-cmk64gx5m2b5200z40",
        product_name="VENGEANCE 64GB (2x32GB) DDR5 5200 CL40",
        sticks=2, per_stick_gb=32, generation=5, speed_mts=5200, cas_latency=40, profiles=["both"],
    ),
    corsair(
        "cmk32gx4m2d3600c18/vengeance-lpx-32gb-2x16gb-ddr4-dram-3600mhz-c18-memory-kit-cmk32gx4m2d3600c18",
        product_name="VENGEANCE LPX 32GB (2x16GB) DDR4 3600 CL18",
        sticks=2, per_stick_gb=16, generation=4, speed_mts=3600, cas_latency=18, profiles=["xmp"],
    ),
    corsair(
        "cmk16gx4m2b3200c16/vengeance-lpx-16gb-2-x-8gb-ddr4-dram-3200mhz-c16-memory-kit-black-cmk16gx4m2b3200c16",
        product_name="VENGEANCE LPX 16GB (2x8GB) DDR4 3200 CL16",
        sticks=2, per_stick_gb=8, generation=4, speed_mts=3200, cas_latency=16, profiles=["xmp"],
    ),
])

# ── Kingston ─────────────────────────────────────────────────────────────────
PRODUCTS.extend([
    kingston("KF560C30BBK2-32", product_name="FURY Beast 32GB (2x16GB) DDR5 6000 CL30", sticks=2, per_stick_gb=16, generation=5, speed_mts=6000, cas_latency=30, profiles=["xmp"]),
    kingston("KF560C30BBAK2-32", product_name="FURY Beast RGB 32GB (2x16GB) DDR5 6000 CL30", sticks=2, per_stick_gb=16, generation=5, speed_mts=6000, cas_latency=30, profiles=["both"], rgb=True),
    kingston("KF560C36BBEAK2-32", product_name="FURY Beast RGB 32GB (2x16GB) DDR5 6000 CL36", sticks=2, per_stick_gb=16, generation=5, speed_mts=6000, cas_latency=36, profiles=["both"], rgb=True),
    kingston("KF564C32BBEK2-32", product_name="FURY Beast 32GB (2x16GB) DDR5 6400 CL32", sticks=2, per_stick_gb=16, generation=5, speed_mts=6400, cas_latency=32, profiles=["both"]),
    kingston("KF556C40BBK2-32", product_name="FURY Beast 32GB (2x16GB) DDR5 5600 CL40", sticks=2, per_stick_gb=16, generation=5, speed_mts=5600, cas_latency=40, profiles=["xmp"]),
    kingston("KF556C36BBEK2-32", product_name="FURY Beast 32GB (2x16GB) DDR5 5600 CL36", sticks=2, per_stick_gb=16, generation=5, speed_mts=5600, cas_latency=36, profiles=["both"]),
    kingston("KF548C38BBK2-32", product_name="FURY Beast 32GB (2x16GB) DDR5 4800 CL38", sticks=2, per_stick_gb=16, generation=5, speed_mts=4800, cas_latency=38, profiles=["jedec"]),
    kingston("KF560C30BBK2-64", product_name="FURY Beast 64GB (2x32GB) DDR5 6000 CL30", sticks=2, per_stick_gb=32, generation=5, speed_mts=6000, cas_latency=30, profiles=["xmp"]),
    kingston("KF564C32BBEK2-64", product_name="FURY Beast 64GB (2x32GB) DDR5 6400 CL32", sticks=2, per_stick_gb=32, generation=5, speed_mts=6400, cas_latency=32, profiles=["both"]),
    kingston("KF432C16BBK2/32", product_name="FURY Beast 32GB (2x16GB) DDR4 3200 CL16", sticks=2, per_stick_gb=16, generation=4, speed_mts=3200, cas_latency=16, profiles=["xmp"]),
    kingston("KF432C16BBK2/16", product_name="FURY Beast 16GB (2x8GB) DDR4 3200 CL16", sticks=2, per_stick_gb=8, generation=4, speed_mts=3200, cas_latency=16, profiles=["xmp"]),
    kingston("KF436C18BBK2/32", product_name="FURY Beast 32GB (2x16GB) DDR4 3600 CL18", sticks=2, per_stick_gb=16, generation=4, speed_mts=3600, cas_latency=18, profiles=["xmp"]),
    kingston("KF432C16BBK2/64", product_name="FURY Beast 64GB (2x32GB) DDR4 3200 CL16", sticks=2, per_stick_gb=32, generation=4, speed_mts=3200, cas_latency=16, profiles=["xmp"]),
])

# ── G.Skill ──────────────────────────────────────────────────────────────────
PRODUCTS.extend([
    gskill("F5-6000J3040F16GX2-TZ5RK", "165/390/1662622003/F5-6000J3040F16GX2-TZ5RK-Specification", product_name="Trident Z5 RGB 32GB (2x16GB) DDR5 6000 CL30", sticks=2, per_stick_gb=16, generation=5, speed_mts=6000, cas_latency=30, profiles=["xmp"], rgb=True),
    gskill("F5-6000J3238F16GX2-TZ5N", "165/393/1662622365/F5-6000J3238F16GX2-TZ5N-Specification", product_name="Trident Z5 Neo 32GB (2x16GB) DDR5 6000 CL32", sticks=2, per_stick_gb=16, generation=5, speed_mts=6000, cas_latency=32, profiles=["both"]),
    gskill("F5-6000J3238F16GX2-TZ5NR", "165/390/1662622003/F5-6000J3040F16GX2-TZ5RK-Specification", product_name="Trident Z5 Neo RGB 32GB (2x16GB) DDR5 6000 CL32", sticks=2, per_stick_gb=16, generation=5, speed_mts=6000, cas_latency=32, profiles=["both"], rgb=True),
    gskill("F5-6400J3239G16GX2-TZ5RS", "165/374/1642064772/F5-6400J3239G16GX2-TZ5RS-F5-6400J3239G16GA2-TZ5RS-Specification", product_name="Trident Z5 RGB 32GB (2x16GB) DDR5 6400 CL32", sticks=2, per_stick_gb=16, generation=5, speed_mts=6400, cas_latency=32, profiles=["xmp"], rgb=True),
    gskill("F5-6400J3239G16GX2-FX5", "165/396/1722406390/F5-6400J3239G16GX2-FX5-Specification", product_name="Flare X5 32GB (2x16GB) DDR5 6400 CL32", sticks=2, per_stick_gb=16, generation=5, speed_mts=6400, cas_latency=32, profiles=["expo"]),
    gskill("F5-7200J3445G16GX2-TZ5RS", "165/374/1665644713/F5-7200J3445G16GX2-TZ5RS-Specification", product_name="Trident Z5 RGB 32GB (2x16GB) DDR5 7200 CL34", sticks=2, per_stick_gb=16, generation=5, speed_mts=7200, cas_latency=34, profiles=["xmp"], rgb=True),
    gskill("F5-5600J3636C16GX2-TZ5K", "165/371/1640228924/F5-5600J3636C16GX2-TZ5K-F5-5600J3636C16GA2-TZ5K-Specification", product_name="Trident Z5 32GB (2x16GB) DDR5 5600 CL36", sticks=2, per_stick_gb=16, generation=5, speed_mts=5600, cas_latency=36, profiles=["xmp"]),
    gskill("F5-5600J3636D32GX2-RS5K", "165/377/1648538953/F5-5600J3636D32GX2-RS5K-F5-5600J3636D32GA2-RS5K-Specification", product_name="Ripjaws S5 64GB (2x32GB) DDR5 5600 CL36", sticks=2, per_stick_gb=32, generation=5, speed_mts=5600, cas_latency=36, profiles=["xmp"]),
    gskill("F4-3200C16D-32GVK", "165/184/1536110922/F4-3200C16D-32GVK-Specification", product_name="Ripjaws V 32GB (2x16GB) DDR4 3200 CL16", sticks=2, per_stick_gb=16, generation=4, speed_mts=3200, cas_latency=16, profiles=["xmp"]),
    gskill("F4-3600C16D-32GVKC", "165/184/1562831784/F4-3600C16D-32GVKC-Specification", product_name="Ripjaws V 32GB (2x16GB) DDR4 3600 CL16", sticks=2, per_stick_gb=16, generation=4, speed_mts=3600, cas_latency=16, profiles=["xmp"]),
    gskill("F4-3600C16D-32GTZNC", "165/326/1562840211/F4-3600C16D-32GTZNC-Specification", product_name="Trident Z Neo 32GB (2x16GB) DDR4 3600 CL16", sticks=2, per_stick_gb=16, generation=4, speed_mts=3600, cas_latency=16, profiles=["xmp"], rgb=True),
])

# ── Crucial ──────────────────────────────────────────────────────────────────
PRODUCTS.extend([
    entry("crucial", "CP2K16G60C36U5B", "Crucial Pro 32GB (2x16GB) DDR5 6000 CL36", 2, 16, 5, 6000, 36, ["both"], source_url="https://www.crucial.com/memory/ddr5/cp2k16g60c36u5b"),
    entry("crucial", "CP2K16G64C32U5W", "Crucial Pro 32GB (2x16GB) DDR5 6400 CL32 White", 2, 16, 5, 6400, 32, ["both"], source_url="https://www.crucial.com/memory/ddr5/cp2k16g64c32u5w"),
    entry("crucial", "CP2K16G56C46U5", "Crucial Pro 32GB (2x16GB) DDR5 5600 CL46", 2, 16, 5, 5600, 46, ["both"], source_url="https://www.crucial.com/memory/ddr5/cp2k16g56c46u5"),
    entry("crucial", "CP2K32G64C40U5B", "Crucial Pro 64GB (2x32GB) DDR5 6400 CL40", 2, 32, 5, 6400, 40, ["both"], source_url="https://www.crucial.com/memory/ddr5/cp2k32g64c40u5b"),
    entry("crucial", "CP2K32G60C40U5B", "Crucial Pro 64GB (2x32GB) DDR5 6000 CL40", 2, 32, 5, 6000, 40, ["both"], source_url="https://www.crucial.com/memory/ddr5/cp2k32g60c40u5b"),
    entry("crucial", "CT2K16G56C46U5", "Crucial 32GB (2x16GB) DDR5 5600 CL46", 2, 16, 5, 5600, 46, ["both"], source_url="https://www.crucial.com/memory/ddr5/ct2k16g56c46u5"),
    entry("crucial", "CT2K16G48C40U5", "Crucial 32GB (2x16GB) DDR5 4800 CL40", 2, 16, 5, 4800, 40, ["jedec"], source_url="https://www.crucial.com/memory/ddr5/ct2k16g48c40u5"),
    entry("crucial", "CT2K32G52C42U5", "Crucial 64GB (2x32GB) DDR5 5200 CL42", 2, 32, 5, 5200, 42, ["jedec"], source_url="https://www.crucial.com/memory/ddr5/ct2k32g52c42u5"),
    entry("crucial", "CT2K16G4DFRA32A", "Crucial 32GB (2x16GB) DDR4 3200 CL22", 2, 16, 4, 3200, 22, ["xmp"], source_url="https://www.crucial.com/memory/ddr4/ct2k16g4dfra32a"),
    entry("crucial", "CT2K8G4DFRA32A", "Crucial 16GB (2x8GB) DDR4 3200 CL22", 2, 8, 4, 3200, 22, ["xmp"], source_url="https://www.crucial.com/memory/ddr4/ct2k8g4dfra32a"),
])

# ── TeamGroup ────────────────────────────────────────────────────────────────
PRODUCTS.extend([
    teamgroup("T-FORCE/delta-rgb-ddr5-black/delta-rgb-ddr5-black-FF3D532G6000HC34ADC01", product_name="T-FORCE Delta RGB 32GB (2x16GB) DDR5 6000 CL34", sticks=2, per_stick_gb=16, generation=5, speed_mts=6000, cas_latency=34, profiles=["both"], rgb=True),
    teamgroup("T-FORCE/delta-rgb-ddr5-black/delta-rgb-ddr5-black-FF3D532G6400HC38GDC01", product_name="T-FORCE Delta RGB 32GB (2x16GB) DDR5 6400 CL38", sticks=2, per_stick_gb=16, generation=5, speed_mts=6400, cas_latency=38, profiles=["both"], rgb=True),
    teamgroup("T-FORCE/vulcan-ddr5-black/vulcan-ddr5-black-FLBD532G6000HC38ADC01", product_name="T-FORCE Vulcan 32GB (2x16GB) DDR5 6000 CL38", sticks=2, per_stick_gb=16, generation=5, speed_mts=6000, cas_latency=38, profiles=["both"]),
    teamgroup("T-FORCE/vulcan-ddr5-black/vulcan-ddr5-black-FLBD532G6400HC32ADC01", product_name="T-FORCE Vulcan 32GB (2x16GB) DDR5 6400 CL32", sticks=2, per_stick_gb=16, generation=5, speed_mts=6400, cas_latency=32, profiles=["both"]),
    teamgroup("T-FORCE/vulcan-ddr5-black/vulcan-ddr5-black-FLBD532G6000HC30DC01", product_name="T-FORCE Vulcan 32GB (2x16GB) DDR5 6000 CL30", sticks=2, per_stick_gb=16, generation=5, speed_mts=6000, cas_latency=30, profiles=["both"]),
    teamgroup("T-FORCE/vulcan-ddr5-black/vulcan-ddr5-black-FLBD564G6000HC34BDC01", product_name="T-FORCE Vulcan 64GB (2x32GB) DDR5 6000 CL34", sticks=2, per_stick_gb=32, generation=5, speed_mts=6000, cas_latency=34, profiles=["both"]),
    teamgroup("T-FORCE/xtreem-ddr5-black/xtreem-ddr5-black-FFXD532G6000HC38ADC01", product_name="T-FORCE XTREEM 32GB (2x16GB) DDR5 6000 CL38", sticks=2, per_stick_gb=16, generation=5, speed_mts=6000, cas_latency=38, profiles=["both"]),
    teamgroup("T-FORCE/vulcan-z-black/vulcan-z-black-TLZBD432G3200HC16FDC01", product_name="T-FORCE Vulcan Z 32GB (2x16GB) DDR4 3200 CL16", sticks=2, per_stick_gb=16, generation=4, speed_mts=3200, cas_latency=16, profiles=["xmp"]),
    teamgroup("T-FORCE/vulcan-z-black/vulcan-z-black-TLZBD416G3600HC18JDC01", product_name="T-FORCE Vulcan Z 16GB (2x8GB) DDR4 3600 CL18", sticks=2, per_stick_gb=8, generation=4, speed_mts=3600, cas_latency=18, profiles=["xmp"]),
])

# ── Patriot ──────────────────────────────────────────────────────────────────
PRODUCTS.extend([
    entry("patriot", "PVV532G600C30K", "Viper Venom 32GB (2x16GB) DDR5 6000 CL30", 2, 16, 5, 6000, 30, ["both"], source_url="https://viper.patriotmemory.com/products/viper-venom-ddr5-performance-ram"),
    entry("patriot", "PVV532G640C32K", "Viper Venom 32GB (2x16GB) DDR5 6400 CL32", 2, 16, 5, 6400, 32, ["both"], source_url="https://viper.patriotmemory.com/products/viper-venom-ddr5-performance-ram"),
    entry("patriot", "PVVR532G640C32K", "Viper Venom RGB 32GB (2x16GB) DDR5 6400 CL32", 2, 16, 5, 6400, 32, ["both"], rgb=True, source_url="https://viper.patriotmemory.com/products/viper-venom-ddr5-performance-ram"),
    entry("patriot", "PVER532G60C30KW", "Viper Elite 5 RGB 32GB (2x16GB) DDR5 6000 CL30", 2, 16, 5, 6000, 30, ["both"], rgb=True, source_url="https://viper.patriotmemory.com/products/elite5-ddr5-performance-ram"),
    entry("patriot", "PSD532G5600K", "Signature Line 32GB (2x16GB) DDR5 5600", 2, 16, 5, 5600, 46, ["jedec"], source_url="https://www.patriotmemory.com/en/products/signature-line-ddr5"),
    entry("patriot", "PSD532G4800K", "Signature Line 32GB (2x16GB) DDR5 4800", 2, 16, 5, 4800, 40, ["jedec"], source_url="https://www.patriotmemory.com/en/products/signature-line-ddr5"),
    entry("patriot", "PSP432G3200KH1", "Signature Premium 32GB (2x16GB) DDR4 3200", 2, 16, 4, 3200, 22, ["jedec"], source_url="https://www.patriotmemory.com/en/products/signature-line-premium-ddr4"),
])

# ── XPG / ADATA ──────────────────────────────────────────────────────────────
PRODUCTS.extend([
    entry("xpg", "AX5U6000C3016G-DCLABK", "LANCER 32GB (2x16GB) DDR5 6000 CL30", 2, 16, 5, 6000, 30, ["both"], source_url="https://www.xpg.com/us/xpg/dram-modules-lancer-ddr5"),
    entry("xpg", "AX5U6400C3232G-DCLABK", "LANCER 32GB (2x16GB) DDR5 6400 CL32", 2, 16, 5, 6400, 32, ["both"], source_url="https://www.xpg.com/us/xpg/dram-modules-lancer-ddr5"),
    entry("xpg", "AX5U6000C3016G-DCLARBK", "LANCER RGB 32GB (2x16GB) DDR5 6000 CL30", 2, 16, 5, 6000, 30, ["both"], rgb=True, source_url="https://www.xpg.com/us/xpg/dram-modules-lancer-rgb-ddr5"),
    entry("xpg", "AX5U6400C3232G-DCLARBK", "LANCER RGB 32GB (2x16GB) DDR5 6400 CL32", 2, 16, 5, 6400, 32, ["both"], rgb=True, source_url="https://www.xpg.com/us/xpg/dram-modules-lancer-rgb-ddr5"),
    entry("xpg", "AX5U7200C3416G-DCLARBK", "LANCER RGB 16GB (2x8GB) DDR5 7200 CL34", 2, 8, 5, 7200, 34, ["both"], rgb=True, source_url="https://www.xpg.com/us/xpg/dram-modules-lancer-rgb-ddr5"),
    entry("xpg", "AX5U320032G16A-DTBKD35G", "SPECTRIX D35G RGB 32GB (2x16GB) DDR4 3200 CL16", 2, 16, 4, 3200, 16, ["xmp"], rgb=True, source_url="https://www.xpg.com/us/xpg/dram-modules-spectrix-d35g-ddr4"),
    entry("adata", "AX5U6000C3016G-CLARBK", "XPG LANCER RGB 16GB DDR5 6000 CL30", 1, 16, 5, 6000, 30, ["both"], rgb=True, source_url="https://www.adata.com/us/xpg/5939"),
    entry("adata", "AX5U6400C3216G-CLARBK", "XPG LANCER RGB 16GB DDR5 6400 CL32", 1, 16, 5, 6400, 32, ["both"], rgb=True, source_url="https://www.adata.com/us/xpg/5939"),
    entry("adata", "AD5U6000C4016G-D", "ADATA XPG LANCER 32GB (2x16GB) DDR5 6000 CL40", 2, 16, 5, 6000, 40, ["both"], source_url="https://www.adata.com/us/xpg/5939"),
])

# ── PNY, OLOy, GeIL, Mushkin ─────────────────────────────────────────────────
PRODUCTS.extend([
    entry("pny", "MD32GK2D5640036XR", "XLR8 Gaming 32GB (2x16GB) DDR5 6400 CL36", 2, 16, 5, 6400, 36, ["both"], source_url="https://www.pny.com/xlr8-gaming-ddr5-6400-mhz-desktop-memory-kit"),
    entry("pny", "MD32GK2D5640036XRGB", "XLR8 EPIC-X RGB 32GB (2x16GB) DDR5 6400 CL36", 2, 16, 5, 6400, 36, ["both"], rgb=True, source_url="https://www.pny.com/en-eu/xlr8-gaming-ddr5-rgb-6400mhz-desktop-memory-kit"),
    entry("pny", "MD32GK2D5560046XR", "XLR8 Gaming 32GB (2x16GB) DDR5 5600 CL46", 2, 16, 5, 5600, 46, ["both"], source_url="https://www.pny.com/en-eu/xlr8-gaming-ddr5-5600-mhz-desktop-memory-kit"),
    entry("pny", "MD32GK2D560032MRR", "XLR8 Mako 32GB (2x16GB) DDR5 5600 CL32", 2, 16, 5, 5600, 32, ["xmp"], source_url="https://www.pny.com/file%20library/company/support/product%20brochures/memory/mako-ddr5-dual-channel-kit.pdf"),
    entry("oloy", "MD5U1664320BRLDA", "Blade RGB 32GB (2x16GB) DDR5 6400 CL32", 2, 16, 5, 6400, 32, ["both"], source_url="https://www.oloymemory.com/module.html?pid=MD5U1664320BRLDA"),
    entry("oloy", "MD5U1660306BRLDA", "Blade RGB 32GB (2x16GB) DDR5 6000 CL30", 2, 16, 5, 6000, 30, ["xmp"], rgb=True, source_url="https://www.oloymemory.com/blade5/"),
    entry("geil", "GAVSG532GB6000C38BDC", "ORION V RGB 32GB (2x16GB) DDR5 6000 CL38", 2, 16, 5, 6000, 38, ["both"], rgb=True, source_url="https://geilmemory.com/"),
    entry("geil", "GAVSG532GB5600C38ADC", "ORION V RGB 32GB (2x16GB) DDR5 5600 CL38", 2, 16, 5, 5600, 38, ["both"], rgb=True, source_url="https://geilmemory.com/"),
    entry("mushkin", "MRF5U600AEEM16GX2", "Redline ST 32GB (2x16GB) DDR5 6000 CL30", 2, 16, 5, 6000, 30, ["both"], source_url="https://mushkin.com/product/redline-st-32gb-2x16gb-ddr5-6000-udimm-pc5-6000-30-38-38-30-mrf5u600aeem16gx2/"),
    entry("mushkin", "MLA5C600AEEM16GX2", "Redline Lumina 32GB (2x16GB) DDR5 6000 CL30", 2, 16, 5, 6000, 30, ["both"], source_url="https://www.mushkin.com/product-category/ram-memory/redline-lumina/lumina-ddr5/"),
    entry("mushkin", "MRE5U560LKKD32G", "Redline 32GB DDR5 5600 CL46", 1, 32, 5, 5600, 46, ["jedec"], source_url="https://mushkin.com/product/redline-32gb-ddr5-5600-udimm-pc5-5600-5600mhz-46-45-45-mre5u560lkkd32g/"),
])

# ── Silicon Power, Klevv, Lexar, Apacer, V-Color, Timetec ───────────────────
PRODUCTS.extend([
    entry("silicon_power", "SP032GXLWU60AFDE", "XPOWER Zenith 32GB (2x16GB) DDR5 6000 CL30", 2, 16, 5, 6000, 30, ["both"], source_url="https://www.silicon-power.com/web/product-Zenith_DDR5_Gaming_UDIMM"),
    entry("silicon_power", "SP032GXLWU64AFDK", "XPOWER Storm RGB 32GB (2x16GB) DDR5 6400 CL32", 2, 16, 5, 6400, 32, ["both"], rgb=True, source_url="https://www.silicon-power.com/web/rs/product-Storm_DDR5_RGB_Gaming_UDIMM"),
    entry("silicon_power", "SP032GBLVU560F22", "DDR5 32GB (2x16GB) 5600 CL46", 2, 16, 5, 5600, 46, ["jedec"], source_url="https://www.silicon-power.com/web/product-DDR5_UDIMM"),
    entry("silicon_power", "SP016GBLVU560F02", "DDR5 16GB 5600 CL46", 1, 16, 5, 5600, 46, ["jedec"], source_url="https://www.silicon-power.com/web/product-DDR5_UDIMM"),
    entry("klevv", "KD5AGUA80-60A300G", "CRAS V RGB 32GB (2x16GB) DDR5 6000 CL30", 2, 16, 5, 6000, 30, ["both"], rgb=True, source_url="https://www.klevv.com/ken/products_details/memory/Klevv_CrasVRGB"),
    entry("klevv", "KD5AGUA80-64B300G", "CRAS V RGB 32GB (2x16GB) DDR5 6400 CL30", 2, 16, 5, 6400, 30, ["both"], rgb=True, source_url="https://www.klevv.com/ken/products_details/memory/Klevv_CrasVRGB"),
    entry("klevv", "KD5AGUA80-56G460D", "DDR5 32GB (2x16GB) 5600 CL46", 2, 16, 5, 5600, 46, ["jedec"], source_url="https://www.klevv.com/ken/products_details/memory/D5_UDIMM"),
    entry("klevv", "KD5AGUA80-60B280H", "BOLT V 32GB (2x16GB) DDR5 6000 CL28", 2, 16, 5, 6000, 28, ["both"], source_url="https://www.klevv.com/ken/products_details/memory/Klevv_BoltV.php"),
    entry("lexar", "LD5U16G72C34LA-RGD", "ARES RGB 32GB (2x16GB) DDR5 7200 CL34", 2, 16, 5, 7200, 34, ["both"], rgb=True, source_url="https://americas.lexar.com/product/lexar-ares-rgb-ddr5-desktop-memory/"),
    entry("lexar", "LD5BU016G-R6000GDLA", "ARES RGB 32GB (2x16GB) DDR5 6000 CL30", 2, 16, 5, 6000, 30, ["both"], rgb=True, source_url="https://americas.lexar.com/product/lexar-ares-rgb-ddr5-desktop-memory/"),
    entry("lexar", "LD5U16G60C32LG-RUD", "THOR OC 32GB (2x16GB) DDR5 6000 CL32", 2, 16, 5, 6000, 32, ["both"], source_url="https://americas.lexar.com/product/lexar-thor-oc-ddr5-desktop-memory/"),
    entry("apacer", "AH5U32G64C5527BAA-2", "ZADAK PANTHER 32GB (2x16GB) DDR5 6400 CL32", 2, 16, 5, 6400, 32, ["both"], source_url="https://www.apacer.com/upload/media/download/ZADAK/Data%20Sheet_PANTHER%20DDR5.pdf"),
    entry("apacer", "AH5U32G60C6227BAA-2", "ZADAK PANTHER 32GB (2x16GB) DDR5 6000 CL40", 2, 16, 5, 6000, 40, ["both"], source_url="https://www.apacer.com/upload/media/download/ZADAK/Data%20Sheet_PANTHER%20DDR5.pdf"),
    entry("vcolor", "TMXSAL1660826KWK", "Manta XSky RGB 32GB (2x16GB) DDR5 6000 CL26", 2, 16, 5, 6000, 26, ["expo"], rgb=True, source_url="https://v-color.net/"),
    entry("vcolor", "TMXFL1680838WWK", "Manta XFinity RGB 32GB (2x16GB) DDR5 8000 CL38", 2, 16, 5, 8000, 38, ["both"], rgb=True, source_url="https://v-color.net/"),
    entry("timetec", "75TT48NU1R8-16G", "Premium DDR5 16GB 4800 CL40", 1, 16, 5, 4800, 40, ["jedec"], source_url="https://timetecinc.com/products/timetec-ddr5-4800-udimm"),
    entry("timetec", "75TT56NU1R8-16G", "Premium DDR5 16GB 5600 CL46", 1, 16, 5, 5600, 46, ["jedec"], source_url="https://timetecinc.com/products/timetec-ddr5-4800-udimm"),
    entry("timetec", "TTDDR5-6000-16x2-30", "32GB (2x16GB) DDR5 6000 CL30", 2, 16, 5, 6000, 30, ["xmp"], source_url="https://www.timetecinc.com/collections/ddr5"),
])

# ── Samsung, SK hynix, Micron, Ballistix ─────────────────────────────────────
PRODUCTS.extend([
    entry("samsung", "M323R2GA3BB0-CQK", "DDR5 UDIMM 16GB 4800 CL40", 1, 16, 5, 4800, 40, ["jedec"], source_url="https://www.samsung.com/semiconductor/"),
    entry("samsung", "M323R2GA3DB0-CWM", "DDR5 UDIMM 16GB 5600 CL46", 1, 16, 5, 5600, 46, ["jedec"], source_url="https://www.samsung.com/semiconductor/"),
    entry("hynix", "HMCG78MEBUA081N", "DDR5 UDIMM 16GB 4800 CL40", 1, 16, 5, 4800, 40, ["jedec"], source_url="https://www.skhynix.com/"),
    entry("hynix", "HMCG88MEBUA081N", "DDR5 UDIMM 32GB 4800 CL40", 1, 32, 5, 4800, 40, ["jedec"], source_url="https://www.skhynix.com/"),
    entry("micron", "CP2K16G64C32U5B", "Crucial Pro 32GB (2x16GB) DDR5 6400 CL32", 2, 16, 5, 6400, 32, ["both"], source_url="https://www.crucial.com/memory/ddr5/cp2k16g64c32u5b"),
    entry("micron", "CP2K16G60C48U5", "Crucial Pro 32GB (2x16GB) DDR5 6000 CL48", 2, 16, 5, 6000, 48, ["both"], source_url="https://www.crucial.com/memory/ddr5/cp2k16g60c48u5"),
    entry("micron", "CB16GU4800", "Crucial Basics 16GB DDR5 4800 CL40", 1, 16, 5, 4800, 40, ["jedec"], source_url="https://content.crucial.com/content/dam/crucial/dram-products/basics/flyer/crucial-basics-memory-productflyer.pdf"),
    entry("ballistix", "BLT2K8G4D32AET4K", "Tactical Tracer RGB 16GB (2x8GB) DDR4 3200 CL16", 2, 8, 4, 3200, 16, ["xmp"], rgb=True, source_url="https://content.crucial.com/content/dam/ballistix/dram-products/tactical-series/ddr4/tactical-tracer-ddr4/flyer/ballistix-tactical-tracer-rgb-productflyer.pdf"),
    entry("ballistix", "BLT4K8G4D32AET4K", "Tactical Tracer RGB 32GB (4x8GB) DDR4 3200 CL16", 4, 8, 4, 3200, 16, ["xmp"], rgb=True, source_url="https://content.crucial.com/content/dam/ballistix/dram-products/tactical-series/ddr4/tactical-tracer-ddr4/flyer/ballistix-tactical-tracer-rgb-productflyer.pdf"),
    entry("ballistix", "BLT2K8G4D30AET4K", "Tactical Tracer RGB 16GB (2x8GB) DDR4 3000 CL15", 2, 8, 4, 3000, 15, ["xmp"], rgb=True, source_url="https://content.crucial.com/content/dam/ballistix/dram-products/tactical-series/ddr4/tactical-tracer-ddr4/flyer/ballistix-tactical-tracer-rgb-productflyer.pdf"),
])


def dedupe(products: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for p in products:
        key = (p["brand"], p["part_number"].upper())
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    out.sort(key=lambda p: (p["brand"], p["generation"], p["speed_mts"], p["total_gb"], p["part_number"]))
    return out


def main() -> None:
    products = dedupe(PRODUCTS)
    payload = {
        "version": 2,
        "updated": VERIFIED,
        "description": "Verified manufacturer catalog SKUs. Only products listed here are returned by the generator.",
        "products": products,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    OUT.write_text(text, encoding="utf-8")
    DOCS.write_text(text, encoding="utf-8")
    brands = sorted({p["brand"] for p in products})
    print(f"Wrote {len(products)} products across {len(brands)} brands")
    print("Brands:", ", ".join(brands))


if __name__ == "__main__":
    main()

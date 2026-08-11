#!/usr/bin/env python3
"""
RAM part number generator for DDR4/DDR5 kits.

Converts specs (sticks, total capacity, speed, profile) into manufacturer-style
part numbers across major consumer memory brands.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from typing import Callable, Literal

from product_validation import validate_kit_spec, validation_to_dict, valid_speeds
from spd_serial import generate_spd_serials, spd_serial_to_dict

Profile = Literal["jedec", "xmp", "expo", "both"]
Generation = Literal[4, 5]
BrandResult = str | list[str]
BrandBuilder = Callable[["RamSpec", int], BrandResult]


@dataclass(frozen=True)
class RamSpec:
    sticks: int
    total_gb: int
    generation: Generation
    speed_mts: int
    profile: Profile
    cas_latency: int | None = None
    rgb: bool = False
    ecc: bool = False
    form_factor: Literal["dimm", "sodimm"] = "dimm"

    @property
    def per_stick_gb(self) -> int:
        if self.total_gb % self.sticks != 0:
            raise ValueError(
                f"Total capacity {self.total_gb} GB is not evenly divisible "
                f"across {self.sticks} stick(s)."
            )
        return self.total_gb // self.sticks

    def validate(self) -> None:
        if self.sticks < 1:
            raise ValueError("Stick count must be at least 1.")
        if self.total_gb < 1:
            raise ValueError("Total capacity must be at least 1 GB.")

        result = validate_kit_spec(
            sticks=self.sticks,
            total_gb=self.total_gb,
            generation=self.generation,
            speed_mts=self.speed_mts,
            profile=self.profile,
            per_stick_gb=self.per_stick_gb,
            form_factor=self.form_factor,
            ecc=self.ecc,
        )
        if result.errors:
            raise ValueError(" ".join(result.errors))

    def validation_result(self):
        return validate_kit_spec(
            sticks=self.sticks,
            total_gb=self.total_gb,
            generation=self.generation,
            speed_mts=self.speed_mts,
            profile=self.profile,
            per_stick_gb=self.per_stick_gb,
            form_factor=self.form_factor,
            ecc=self.ecc,
        )


def default_cl(generation: Generation, speed_mts: int, profile: Profile) -> int:
    if profile == "jedec":
        if generation == 5:
            return {4800: 40, 5200: 42, 5600: 46, 6000: 48, 6400: 52}.get(
                speed_mts, max(36, speed_mts // 125)
            )
        return {2133: 15, 2400: 17, 2666: 19, 2933: 21, 3200: 22}.get(
            speed_mts, max(14, speed_mts // 200)
        )

    if generation == 5:
        if speed_mts >= 7200:
            return 34
        if speed_mts >= 6400:
            return 32
        if speed_mts >= 6000:
            return 30
        if speed_mts >= 5600:
            return 36
        return 40
    if speed_mts >= 3600:
        return 18
    if speed_mts >= 3200:
        return 16
    if speed_mts >= 3000:
        return 15
    return 16


def kit_suffix(sticks: int) -> str:
    return f"K{sticks}" if sticks > 1 else ""


def gskill_kit_suffix(sticks: int) -> str:
    return f"X{sticks}" if sticks > 1 else ""


def gskill_subtimings(cl: int) -> str:
    trcd = cl
    trp = cl
    tras = cl + 10
    return f"{cl:02d}{trcd:02d}{trp:02d}{tras:02d}"


def gskill_series(generation: Generation, rgb: bool, profile: Profile) -> str:
    if generation == 5:
        if rgb:
            return "TZ5RK" if profile in {"expo", "both"} else "TR5RG"
        return "TZ5K" if profile in {"expo", "both"} else "TR5G"
    return "TZRK" if rgb else "TZK"


def corsair_series_letter(generation: Generation, rgb: bool) -> str:
    if generation == 5:
        return "H" if rgb else "K"
    return "W" if rgb else "K"


def corsair_profile_letter(profile: Profile) -> str:
    if profile == "expo":
        return "Z"
    return "C"


def kingston_line(generation: Generation, profile: Profile, rgb: bool) -> str:
    if profile in {"xmp", "expo", "both"}:
        return "KF"
    return "KVR"


def kingston_profile_bits(profile: Profile) -> str:
    if profile in {"expo", "both"}:
        return "E"
    if profile == "xmp":
        return "A"
    return "B"


def build_kingston(spec: RamSpec, cl: int) -> str:
    line = kingston_line(spec.generation, spec.profile, spec.rgb)
    gen = str(spec.generation)
    speed = (
        str(spec.speed_mts // 100)
        if spec.generation == 5
        else str(spec.speed_mts // 100)
    )
    rank = "2"
    features = kingston_profile_bits(spec.profile)
    kit = kit_suffix(spec.sticks)
    return f"{line}{gen}{speed}C{cl:02d}BB{rank}{features}{kit}-{spec.total_gb}"


def build_corsair(spec: RamSpec, cl: int) -> list[str]:
    series = corsair_series_letter(spec.generation, spec.rgb)
    gen = spec.generation
    module_count = f"M{spec.sticks}"
    revision = "B"
    speed = spec.speed_mts
    profile_letter = corsair_profile_letter(spec.profile)
    base = f"CM{series}{spec.total_gb}GX{gen}{module_count}{revision}{speed}{profile_letter}{cl:02d}"

    if spec.profile == "both":
        expo_variant = base.replace(f"{speed}C", f"{speed}Z", 1)
        return [
            f"{base}   (Intel XMP 3.0)",
            f"{expo_variant}   (AMD EXPO)",
        ]
    return [base]


def build_gskill(spec: RamSpec, cl: int) -> str:
    gen_prefix = f"F{spec.generation}"
    sub = gskill_subtimings(cl)
    capacity = f"G{spec.total_gb}G"
    kit = gskill_kit_suffix(spec.sticks)
    series = gskill_series(spec.generation, spec.rgb, spec.profile)
    return f"{gen_prefix}-{spec.speed_mts}J{sub}{capacity}{kit}-{series}"


def build_crucial(spec: RamSpec, cl: int) -> str:
    speed = str(spec.speed_mts // 100)
    gen = spec.generation
    per = spec.per_stick_gb
    if spec.sticks == 1:
        return f"CT{per}G{speed}C{cl:02d}U{gen}"
    return f"CT{spec.sticks}K{per}G{speed}C{cl:02d}U{gen}"


def build_teamgroup(spec: RamSpec, cl: int) -> str:
    gen_code = f"D{spec.generation}"
    per = f"{spec.per_stick_gb}G"
    heat = "H" if spec.rgb or spec.profile != "jedec" else ""
    kit = "DC" if spec.sticks > 1 else ""
    line = "FF3" if spec.profile != "jedec" else "TPD"
    return f"{line}{gen_code}{per}{spec.speed_mts}{heat}C{cl:02d}A{kit}01"


def build_patriot(spec: RamSpec, cl: int) -> str:
    series = "PVV5" if spec.generation == 5 else "PVS4"
    speed_code = spec.speed_mts // 10
    suffix = "K" if spec.sticks > 1 else ""
    rgb = "R" if spec.rgb else ""
    return f"{series}{spec.total_gb}G{speed_code}C{cl:02d}{rgb}{suffix}"


def build_xpg(spec: RamSpec, cl: int) -> str:
    gen = spec.generation
    per = spec.per_stick_gb
    if spec.sticks > 1:
        kit = "-DCLARBK" if spec.rgb else "-DCLABBK"
    else:
        kit = "-CLARBK" if spec.rgb else "-CLABBK"
    return f"AX{gen}U{spec.speed_mts}C{cl:02d}{per}G{kit}"


def build_pny(spec: RamSpec, cl: int) -> str:
    kit = f"K{spec.sticks}" if spec.sticks > 1 else ""
    rgb = "RGB" if spec.rgb else "R"
    return f"MD{spec.total_gb}G{kit}D{spec.speed_mts}{cl:03d}M{rgb}"


def build_oloy(spec: RamSpec, cl: int) -> str:
    gen = spec.generation
    speed_field = f"{spec.speed_mts // 100}{cl:02d}"
    kit = "K" if spec.sticks > 1 else ""
    rgb = "BR" if spec.rgb else "B"
    return f"MD{gen}U{speed_field}0{rgb}{kit}DE"


def build_geil(spec: RamSpec, cl: int) -> str:
    kit = f"DC{spec.total_gb}G" if spec.sticks > 1 else f"{spec.per_stick_gb}G"
    rgb = "R" if spec.rgb else ""
    return f"GSLZ{spec.generation}S{spec.speed_mts}C{cl:02d}{kit}{rgb}"


def build_mushkin(spec: RamSpec, cl: int) -> str:
    kit = f"X{spec.sticks}" if spec.sticks > 1 else ""
    return f"MRB{spec.generation}U{spec.speed_mts // 100}MMPP{spec.total_gb}G{kit}"


def build_silicon_power(spec: RamSpec, cl: int) -> str:
    per = spec.per_stick_gb
    kit = f"x{spec.sticks}" if spec.sticks > 1 else ""
    return f"SP{per:03d}GXLZU{spec.speed_mts}B{cl:02d}A{spec.generation}{kit}"


def build_klevv(spec: RamSpec, cl: int) -> str:
    speed = spec.speed_mts // 100
    rgb = "RGD" if spec.rgb else "BK"
    kit = f"-{spec.sticks}x{spec.per_stick_gb}" if spec.sticks > 1 else ""
    return f"KD{spec.generation}AGUA{spec.total_gb}-{speed}B300C{cl:02d}{rgb}{kit}"


def build_lexar(spec: RamSpec, cl: int) -> str:
    speed = spec.speed_mts // 100
    per = spec.per_stick_gb
    rgb = "-RGD" if spec.rgb else "-BK"
    kit = f"-{spec.sticks}x" if spec.sticks > 1 else ""
    return f"LD{spec.generation}U{per}G{speed}C{cl:02d}LA{kit}{rgb}"


def build_apacer(spec: RamSpec, cl: int) -> str:
    per = spec.per_stick_gb
    kit = f"-{spec.sticks}" if spec.sticks > 1 else "-1"
    return f"AH{spec.generation}U{per}G{spec.speed_mts}C{cl:02d}AA{kit}"


def build_vcolor(spec: RamSpec, cl: int) -> str:
    return f"TD{spec.generation}{spec.per_stick_gb}G{spec.speed_mts // 100}C{cl:02d}U{spec.sticks * 10 + 1}"


def build_timetec(spec: RamSpec, cl: int) -> str:
    return f"TTDDR{spec.generation}-{spec.speed_mts}-{spec.per_stick_gb}x{spec.sticks}-{cl}"


def build_adata(spec: RamSpec, cl: int) -> str:
    speed = spec.speed_mts // 100
    per = spec.per_stick_gb
    kit = f"{spec.sticks}x" if spec.sticks > 1 else ""
    return f"AD{spec.generation}U{speed}{kit}{per}G-C{cl:02d}"


def build_samsung(spec: RamSpec, cl: int) -> str:
    if spec.form_factor == "sodimm":
        return f"M3{spec.generation}R{spec.per_stick_gb}GA{spec.speed_mts // 800}BB0-CQ{cl:02d}D"
    per_code = {8: "2", 16: "4", 32: "6", 64: "8"}.get(spec.per_stick_gb, "4")
    return f"M3{spec.generation}R{per_code}GA{spec.speed_mts // 400}BB0-CQ{cl:02d}D"


def build_hynix(spec: RamSpec, cl: int) -> str:
    speed_class = spec.speed_mts // 100
    kit = f"-{spec.sticks}x{spec.per_stick_gb}G" if spec.sticks > 1 else f"-{spec.per_stick_gb}G"
    return f"HMCG{speed_class}MEBUA{cl}.N{spec.generation}{kit}"


def build_micron(spec: RamSpec, cl: int) -> str:
    density = {8: "8", 16: "4", 32: "5", 64: "6"}.get(spec.per_stick_gb, "4")
    speed_bin = {4800: "48", 5200: "52", 5600: "56", 6000: "60", 6400: "64"}.get(
        spec.speed_mts, str(spec.speed_mts // 100)
    )
    kit = f"K{spec.sticks}" if spec.sticks > 1 else ""
    return f"MTC{spec.generation}{density}A{speed_bin}C{cl:02d}{kit}"


def build_ballistix(spec: RamSpec, cl: int) -> str:
    speed = spec.speed_mts // 100
    if spec.sticks == 1:
        return f"BL{spec.per_stick_gb}G{speed}C{cl:02d}U{spec.generation}"
    return f"BL{spec.sticks}K{spec.per_stick_gb}G{speed}C{cl:02d}U{spec.generation}"


BRAND_REGISTRY: list[tuple[str, str, BrandBuilder]] = [
    ("kingston", "Kingston", build_kingston),
    ("corsair", "Corsair", build_corsair),
    ("gskill", "G.Skill", build_gskill),
    ("crucial", "Crucial", build_crucial),
    ("teamgroup", "TeamGroup T-Force", build_teamgroup),
    ("patriot", "Patriot", build_patriot),
    ("xpg", "XPG (ADATA)", build_xpg),
    ("pny", "PNY", build_pny),
    ("oloy", "OLOy", build_oloy),
    ("geil", "GeIL", build_geil),
    ("mushkin", "Mushkin", build_mushkin),
    ("silicon_power", "Silicon Power", build_silicon_power),
    ("klevv", "Klevv", build_klevv),
    ("lexar", "Lexar", build_lexar),
    ("apacer", "Apacer", build_apacer),
    ("vcolor", "V-Color", build_vcolor),
    ("timetec", "Timetec", build_timetec),
    ("adata", "ADATA", build_adata),
    ("samsung", "Samsung", build_samsung),
    ("hynix", "SK hynix", build_hynix),
    ("micron", "Micron", build_micron),
    ("ballistix", "Ballistix (legacy)", build_ballistix),
]

BRAND_IDS = [brand_id for brand_id, _, _ in BRAND_REGISTRY]
BRAND_NAMES = {brand_id: name for brand_id, name, _ in BRAND_REGISTRY}


def build_all(spec: RamSpec) -> dict[str, str | list[str] | int]:
    cl = spec.cas_latency or default_cl(spec.generation, spec.speed_mts, spec.profile)
    results: dict[str, str | list[str] | int] = {"assumed_cl": cl}
    for brand_id, _, builder in BRAND_REGISTRY:
        results[brand_id] = builder(spec, cl)
    return results


def normalize_brand_result(value: BrandResult) -> list[dict[str, str | None]]:
    if isinstance(value, list):
        entries = []
        for line in value:
            if "   " in line:
                part, label = line.split("   ", 1)
                entries.append({"part_number": part.strip(), "label": label.strip()})
            else:
                entries.append({"part_number": line.strip(), "label": None})
        return entries
    return [{"part_number": value, "label": None}]


def enrich_brand_entries(
    brand_id: str,
    entries: list[dict[str, str | None]],
    generation: Generation,
    stick_count: int,
) -> list[dict]:
    enriched = []
    for entry in entries:
        part = entry["part_number"]
        serials = generate_spd_serials(brand_id, part, generation, stick_count)
        enriched.append(
            {
                **entry,
                "spd_serials": [spd_serial_to_dict(s) for s in serials],
            }
        )
    return enriched


def generate_report(spec: RamSpec) -> dict:
    spec.validate()
    validation = validation_to_dict(spec.validation_result())
    results = build_all(spec)
    cl = results["assumed_cl"]

    brands = {}
    brand_meta = []
    for brand_id, brand_name, _ in BRAND_REGISTRY:
        value = results[brand_id]
        assert isinstance(value, (str, list))
        entries = normalize_brand_result(value)
        brands[brand_id] = enrich_brand_entries(
            brand_id, entries, spec.generation, spec.sticks
        )
        brand_meta.append({"id": brand_id, "name": brand_name})

    return {
        "validation": validation,
        "valid_speeds": valid_speeds(spec.generation),
        "spec": {
            "sticks": spec.sticks,
            "per_stick_gb": spec.per_stick_gb,
            "total_gb": spec.total_gb,
            "generation": spec.generation,
            "speed_mts": spec.speed_mts,
            "profile": spec.profile,
            "cas_latency": cl,
            "cas_latency_custom": spec.cas_latency is not None,
            "rgb": spec.rgb,
            "ecc": spec.ecc,
            "form_factor": spec.form_factor,
        },
        "brand_meta": brand_meta,
        "brands": brands,
        "brand_count": len(BRAND_REGISTRY),
    }


PROFILE_ALIASES = {
    "jedec": "jedec",
    "standard": "jedec",
    "none": "jedec",
    "xmp": "xmp",
    "xmp3": "xmp",
    "xmp2": "xmp",
    "expo": "expo",
    "amd": "expo",
    "both": "both",
    "dual": "both",
    "xmp+expo": "both",
    "xmp and expo": "both",
    "xmp/expo": "both",
}


def parse_profile(text: str) -> Profile:
    key = text.strip().lower()
    if key not in PROFILE_ALIASES:
        raise ValueError(f"Unknown profile {text!r}. Use jedec, xmp, expo, or both.")
    return PROFILE_ALIASES[key]  # type: ignore[return-value]


def parse_natural_language(text: str) -> RamSpec:
    lowered = text.lower()

    per_stick_match = re.search(r"(\d+)\s*x\s*(\d+)\s*(?:gb|g)\b", lowered)
    if per_stick_match:
        sticks = int(per_stick_match.group(1))
        per_stick_gb = int(per_stick_match.group(2))
        total_gb = sticks * per_stick_gb
    else:
        sticks_match = re.search(r"(\d+)\s*(?:x|sticks?|modules?|dimms?)", lowered)
        if not sticks_match:
            sticks_match = re.search(r"(\d+)\s*stick", lowered)
        sticks = int(sticks_match.group(1)) if sticks_match else 2

        total_match = re.search(
            r"(\d+)\s*(?:gb|g)\s*(?:total|combined|kit)?|(?:total|combined|kit)\s*(\d+)\s*(?:gb|g)",
            lowered,
        )
        if not total_match:
            total_match = re.search(r"(\d+)\s*(?:gb|g)", lowered)
        if not total_match:
            raise ValueError("Could not find total capacity (e.g. '32 gb' or '2x16gb').")
        total_gb = int(next(g for g in total_match.groups() if g))

    if "ddr5" in lowered or "ddr 5" in lowered:
        generation = 5
    elif "ddr4" in lowered or "ddr 4" in lowered:
        generation = 4
    else:
        generation = 5

    speed_match = re.search(
        r"(?:speed|ddr\d[\s-]?|)(\d{4,5})\s*(?:mt/s|mts|mhz)?", lowered
    )
    if not speed_match:
        speed_match = re.search(r"\b(4\d{3}|5\d{3}|6\d{3}|7\d{3}|8\d{3})\b", lowered)
    if not speed_match:
        raise ValueError("Could not find speed (e.g. '6000' or 'DDR5-6000').")
    speed_mts = int(speed_match.group(1))

    if "both" in lowered or "xmp and expo" in lowered or "xmp/expo" in lowered:
        profile: Profile = "both"
    elif "expo" in lowered:
        profile = "expo"
    elif "xmp" in lowered:
        profile = "xmp"
    else:
        profile = "jedec"

    cl_match = re.search(r"\bcl\s*(\d{1,2})\b|\bc(\d{1,2})\b", lowered)
    cas_latency = int(cl_match.group(1) or cl_match.group(2)) if cl_match else None
    rgb = "rgb" in lowered
    ecc = "ecc" in lowered
    form_factor = "sodimm" if "sodimm" in lowered or "so-dimm" in lowered else "dimm"

    spec = RamSpec(
        sticks=sticks,
        total_gb=total_gb,
        generation=generation,
        speed_mts=speed_mts,
        profile=profile,
        cas_latency=cas_latency,
        rgb=rgb,
        ecc=ecc,
        form_factor=form_factor,
    )
    spec.validate()
    return spec


def format_output(spec: RamSpec, results: dict[str, str | list[str] | int]) -> str:
    cl = results["assumed_cl"]
    lines = [
        "RAM Part Number Generator",
        "========================",
        "",
        "Input spec:",
        f"  Kit:           {spec.sticks}x {spec.per_stick_gb} GB ({spec.total_gb} GB total)",
        f"  Generation:    DDR{spec.generation}",
        f"  Speed:         {spec.speed_mts} MT/s",
        f"  Profile:       {spec.profile.upper()}",
        f"  CAS latency:   CL{cl}" + (" (default)" if spec.cas_latency is None else ""),
        f"  Form factor:   {spec.form_factor.upper()}",
        "",
        "Generated part numbers:",
    ]

    for brand_id, brand_name, _ in BRAND_REGISTRY:
        value = results[brand_id]
        if isinstance(value, list):
            lines.append(f"  {brand_name}:")
            for item in value:
                lines.append(f"    {item}")
        else:
            lines.append(f"  {brand_name}:  {value}")

    lines.extend(
        [
            "",
            "Notes:",
            "  - Part numbers follow each vendor's public naming scheme.",
            "  - Always verify against the manufacturer's product page before buying.",
        ]
    )
    return "\n".join(lines)


def spec_from_form(data: dict) -> RamSpec:
    sticks = int(data["sticks"])
    total_gb = int(data["total_gb"])
    generation = int(data["generation"])
    speed_mts = int(data["speed_mts"])
    profile = data.get("profile", "jedec")
    cas_latency = data.get("cas_latency")
    if cas_latency in ("", None):
        cas_latency = None
    else:
        cas_latency = int(cas_latency)

    spec = RamSpec(
        sticks=sticks,
        total_gb=total_gb,
        generation=generation,  # type: ignore[arg-type]
        speed_mts=speed_mts,
        profile=profile,  # type: ignore[arg-type]
        cas_latency=cas_latency,
        rgb=bool(data.get("rgb")),
        ecc=bool(data.get("ecc")),
        form_factor=data.get("form_factor", "dimm"),  # type: ignore[arg-type]
    )
    spec.validate()
    return spec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate RAM part numbers from kit specifications.",
    )
    parser.add_argument(
        "description",
        nargs="?",
        help='Natural language spec, e.g. "2 sticks 32 gb total ddr5 speed 6000 both xmp and expo"',
    )
    parser.add_argument("--sticks", type=int, help="Number of modules in the kit")
    parser.add_argument("--total-gb", type=int, help="Total kit capacity in GB")
    parser.add_argument("--generation", type=int, choices=[4, 5], help="DDR generation")
    parser.add_argument("--speed", type=int, help="Speed in MT/s (e.g. 6000)")
    parser.add_argument(
        "--profile",
        choices=["jedec", "xmp", "expo", "both"],
        default="jedec",
        help="Memory profile (default: jedec)",
    )
    parser.add_argument("--cl", type=int, help="CAS latency (optional)")
    parser.add_argument("--rgb", action="store_true", help="RGB series variant")
    parser.add_argument("--ecc", action="store_true", help="ECC module")
    parser.add_argument(
        "--brand",
        choices=[*BRAND_IDS, "all"],
        default="all",
        help="Only show one brand",
    )
    return parser


def spec_from_args(args: argparse.Namespace) -> RamSpec:
    if args.description and any(
        v is not None
        for v in (args.sticks, args.total_gb, args.generation, args.speed)
    ):
        raise ValueError("Use either a natural-language description or explicit flags, not both.")

    if args.description:
        return parse_natural_language(args.description)

    missing = [
        name
        for name, value in (
            ("--sticks", args.sticks),
            ("--total-gb", args.total_gb),
            ("--generation", args.generation),
            ("--speed", args.speed),
        )
        if value is None
    ]
    if missing:
        raise ValueError(f"Missing required flags: {', '.join(missing)}")

    spec = RamSpec(
        sticks=args.sticks,
        total_gb=args.total_gb,
        generation=args.generation,
        speed_mts=args.speed,
        profile=args.profile,
        cas_latency=args.cl,
        rgb=args.rgb,
        ecc=args.ecc,
    )
    spec.validate()
    return spec


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        spec = spec_from_args(args)
        results = build_all(spec)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.brand != "all":
        cl = results["assumed_cl"]
        value = results[args.brand]
        print(value if isinstance(value, str) else value[0])
        return 0

    print(format_output(spec, results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

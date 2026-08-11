"""Validate RAM kit specs against known JEDEC/retail speed tiers and common kits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Generation = Literal[4, 5]
Profile = Literal["jedec", "xmp", "expo", "both"]

# Standard JEDEC + common retail overclock speeds (MT/s).
# Part numbers are only meaningful when speed matches a real product tier.
DDR4_SPEEDS: tuple[int, ...] = (
    1600,
    1867,
    2133,
    2400,
    2667,
    2933,
    3000,
    3200,
    3600,
    3733,
    3866,
    4000,
    4133,
    4266,
    4400,
    4600,
    4800,
    5000,
    5100,
)

DDR5_SPEEDS: tuple[int, ...] = (
    4800,
    5200,
    5600,
    6000,
    6200,
    6400,
    6600,
    6800,
    7000,
    7200,
    7600,
    7800,
    8000,
    8200,
    8400,
    8600,
    8800,
    9000,
    9200,
)

# Speeds that exist in JEDEC tables but rarely appear as retail desktop kits.
DDR5_NON_RETAIL_SPEEDS = frozenset({4000, 4400, 6400})  # 6400 is retail actually - remove

# Retail DDR5 essentially starts at 4800 for desktop UDIMMs.
DDR5_MIN_RETAIL = 4800

# Common per-stick capacities for consumer kits.
CONSUMER_PER_STICK_GB = frozenset({4, 8, 16, 24, 32, 48})

# Typical total kit sizes at retail.
COMMON_TOTAL_GB = frozenset({8, 16, 32, 48, 64, 96, 128})

# Speeds where XMP/EXPO kits are commonly sold (not strict JEDEC-only bins).
DDR4_OC_SPEEDS = frozenset({3000, 3200, 3600, 3733, 3866, 4000, 4133, 4266, 4400, 4600, 4800, 5000, 5100})
DDR5_OC_SPEEDS = frozenset({6000, 6200, 6400, 6600, 6800, 7000, 7200, 7600, 7800, 8000, 8200, 8400, 8600, 8800, 9000, 9200})

# JEDEC baseline speeds (no XMP required).
DDR4_JEDEC_SPEEDS = frozenset({1600, 1867, 2133, 2400, 2667, 2933, 3200})
DDR5_JEDEC_SPEEDS = frozenset({4800, 5200, 5600, 6000, 6400})


@dataclass(frozen=True)
class ValidationResult:
    errors: list[str]
    warnings: list[str]
    speed_tier: str  # jedec | oc | unknown
    retail_likely: bool

    @property
    def ok(self) -> bool:
        return not self.errors


def valid_speeds(generation: Generation) -> list[int]:
    return list(DDR5_SPEEDS if generation == 5 else DDR4_SPEEDS)


def nearest_valid_speed(generation: Generation, speed_mts: int) -> int:
    speeds = valid_speeds(generation)
    return min(speeds, key=lambda s: abs(s - speed_mts))


def _speed_tier(generation: Generation, speed_mts: int) -> str:
    if generation == 5:
        if speed_mts in DDR5_JEDEC_SPEEDS:
            return "jedec"
        if speed_mts in DDR5_OC_SPEEDS:
            return "oc"
    else:
        if speed_mts in DDR4_JEDEC_SPEEDS:
            return "jedec"
        if speed_mts in DDR4_OC_SPEEDS:
            return "oc"
    return "unknown"


def validate_kit_spec(
    *,
    sticks: int,
    total_gb: int,
    generation: Generation,
    speed_mts: int,
    profile: Profile,
    per_stick_gb: int,
    form_factor: str = "dimm",
    ecc: bool = False,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    allowed = DDR5_SPEEDS if generation == 5 else DDR4_SPEEDS
    if speed_mts not in allowed:
        nearest = nearest_valid_speed(generation, speed_mts)
        gen_label = f"DDR{generation}"
        allowed_str = ", ".join(str(s) for s in allowed)
        errors.append(
            f"{speed_mts} MT/s is not a standard {gen_label} retail speed. "
            f"Valid speeds: {allowed_str}. "
            f"Nearest match: {nearest} MT/s."
        )

    if generation == 5 and speed_mts < DDR5_MIN_RETAIL:
        errors.append(
            f"DDR5 desktop kits rarely exist below {DDR5_MIN_RETAIL} MT/s. "
            f"You entered {speed_mts} MT/s — that speed tier is not sold as a "
            f"32 GB retail kit from major brands."
        )

    if per_stick_gb not in CONSUMER_PER_STICK_GB:
        warnings.append(
            f"{per_stick_gb} GB per stick is uncommon. Most retail kits use "
            f"4/8/16/24/32/48 GB modules."
        )

    if total_gb not in COMMON_TOTAL_GB:
        warnings.append(
            f"{total_gb} GB total is an unusual kit size. Common kits: "
            f"8/16/32/48/64/96/128 GB."
        )

    tier = _speed_tier(generation, speed_mts)

    if profile in {"xmp", "expo", "both"} and tier == "jedec":
        warnings.append(
            f"DDR{generation}-{speed_mts} is typically a JEDEC speed. "
            f"XMP/EXPO kits at this speed exist but are less common — "
            f"verify the profile matches the product you want."
        )

    if profile == "jedec" and tier == "oc":
        warnings.append(
            f"DDR{generation}-{speed_mts} is usually sold as an XMP/EXPO overclock kit, "
            f"not plain JEDEC. Generated part numbers may not match JEDEC SKUs."
        )

    if generation == 5 and speed_mts >= 7200 and total_gb >= 64:
        warnings.append(
            "High-speed DDR5 (7200+) at 64 GB+ is rare — only a few brands sell this combo."
        )

    if form_factor == "sodimm" and profile in {"xmp", "expo", "both"}:
        warnings.append(
            "SO-DIMM XMP/EXPO kits are limited. Many generated laptop part numbers "
            "may not exist at retail."
        )

    if ecc:
        warnings.append(
            "ECC part number formats differ from consumer UDIMMs. "
            "Generated numbers are approximate."
        )

    # Always warn: format-generated, not looked up in a product database.
    warnings.append(
        "Part numbers follow naming rules only — they are NOT verified against "
        "manufacturer catalogs. Always confirm speed and capacity on the vendor "
        "website before buying."
    )

    retail_likely = not errors and tier in {"jedec", "oc"}

    return ValidationResult(
        errors=errors,
        warnings=warnings,
        speed_tier=tier,
        retail_likely=retail_likely,
    )


def validation_to_dict(result: ValidationResult) -> dict:
    return {
        "errors": result.errors,
        "warnings": result.warnings,
        "speed_tier": result.speed_tier,
        "retail_likely": result.retail_likely,
        "ok": result.ok,
    }

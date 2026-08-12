"""Derive RAM timing, voltage, and module details from catalog kit specs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Profile = Literal["jedec", "xmp", "expo", "both"]

# JEDEC baseline primary timings: speed MT/s -> (CL, tRCD, tRP, tRAS)
DDR5_JEDEC_TIMINGS: dict[int, tuple[int, int, int, int]] = {
    4800: (40, 40, 40, 77),
    5200: (42, 42, 42, 84),
    5600: (46, 45, 45, 89),
    6000: (48, 48, 48, 96),
    6400: (52, 52, 52, 103),
}

DDR4_JEDEC_TIMINGS: dict[int, tuple[int, int, int, int]] = {
    1600: (11, 11, 11, 28),
    1867: (13, 13, 13, 32),
    2133: (15, 15, 15, 35),
    2400: (17, 17, 17, 39),
    2667: (19, 19, 19, 43),
    2933: (21, 21, 21, 47),
    3200: (22, 22, 22, 52),
}

# Typical refresh cycle counts by die density (per channel module)
DDR4_TRFC_BY_GB: dict[int, int] = {4: 350, 8: 560, 16: 880, 32: 1250}
DDR5_TRFC_BY_GB: dict[int, int] = {8: 560, 16: 880, 24: 980, 32: 1250, 48: 1760, 64: 2100}


@dataclass(frozen=True)
class PrimaryTimings:
    cl: int
    trcd: int
    trp: int
    tras: int

    @property
    def trc(self) -> int:
        return self.trcd + self.tras

    @property
    def label(self) -> str:
        return f"CL{self.cl}-{self.trcd}-{self.trp}-{self.tras}"


def _speed_tier(generation: int, speed_mts: int, profiles: tuple[str, ...] | list[str]) -> str:
    profile_set = set(profiles)
    if generation == 5:
        if speed_mts in DDR5_JEDEC_TIMINGS and profile_set <= {"jedec"}:
            return "jedec"
        return "oc"
    if speed_mts in DDR4_JEDEC_TIMINGS and profile_set <= {"jedec"}:
        return "jedec"
    return "oc"


def _estimate_oc_subtimings(cl: int, speed_mts: int, generation: int) -> PrimaryTimings:
    if generation == 5:
        trcd = cl + (8 if speed_mts >= 7200 else 6 if speed_mts >= 6400 else 4 if speed_mts >= 6000 else 2)
        trp = trcd
        tras = cl + (46 if speed_mts >= 7200 else 42 if speed_mts >= 6400 else 38 if speed_mts >= 6000 else 34)
    else:
        trcd = cl + (2 if speed_mts >= 3600 else 1 if speed_mts >= 3200 else 0)
        trp = trcd
        tras = cl + (22 if speed_mts >= 3600 else 18 if speed_mts >= 3200 else 16)
    return PrimaryTimings(cl=cl, trcd=trcd, trp=trp, tras=tras)


def _primary_timings(
    generation: int,
    speed_mts: int,
    cas_latency: int,
    profiles: tuple[str, ...] | list[str],
) -> PrimaryTimings:
    tier = _speed_tier(generation, speed_mts, profiles)
    table = DDR5_JEDEC_TIMINGS if generation == 5 else DDR4_JEDEC_TIMINGS

    if tier == "jedec" and speed_mts in table:
        cl, trcd, trp, tras = table[speed_mts]
        return PrimaryTimings(cl=cl, trcd=trcd, trp=trp, tras=tras)

    return _estimate_oc_subtimings(cas_latency, speed_mts, generation)


def _tck_ns(speed_mts: int) -> float:
    return round(2000 / speed_mts, 3)


def _bandwidth_gbps(speed_mts: int) -> float:
    return round(speed_mts * 8 / 1000, 1)


def _trfc_cycles(generation: int, per_stick_gb: int) -> int:
    table = DDR5_TRFC_BY_GB if generation == 5 else DDR4_TRFC_BY_GB
    if per_stick_gb in table:
        return table[per_stick_gb]
    keys = sorted(table)
    return table[min(keys, key=lambda k: abs(k - per_stick_gb))]


def _voltages(
    generation: int,
    speed_mts: int,
    profiles: tuple[str, ...] | list[str],
) -> dict[str, float]:
    profile_set = set(profiles)
    oc = _speed_tier(generation, speed_mts, profiles) == "oc" or bool(
        profile_set & {"xmp", "expo", "both"}
    )

    if generation == 5:
        if oc:
            vdd = 1.40 if speed_mts >= 7200 else 1.35 if speed_mts >= 6400 else 1.30
            return {"vdd": vdd, "vddq": vdd, "vpp": 1.80}
        return {"vdd": 1.10, "vddq": 1.10, "vpp": 1.80}

    if oc:
        return {"vdd": 1.35, "vddq": None, "vpp": None}
    return {"vdd": 1.20, "vddq": None, "vpp": None}


def _command_rate(generation: int, speed_mts: int, profiles: tuple[str, ...] | list[str]) -> str:
    tier = _speed_tier(generation, speed_mts, profiles)
    if tier == "oc":
        return "1T"
    if generation == 5 and speed_mts >= 5600:
        return "2T"
    if generation == 4 and speed_mts >= 2933:
        return "2T"
    return "1T"


def build_ram_details(
    *,
    brand: str,
    part_number: str,
    product_name: str,
    sticks: int,
    per_stick_gb: int,
    total_gb: int,
    generation: int,
    speed_mts: int,
    cas_latency: int,
    profiles: tuple[str, ...] | list[str],
    requested_profile: Profile,
    rgb: bool = False,
    ecc: bool = False,
    form_factor: str = "dimm",
    verified: str | None = None,
    spd_serials: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a structured timing and module detail payload for UI display."""
    primary = _primary_timings(generation, speed_mts, cas_latency, profiles)
    tck = _tck_ns(speed_mts)
    per_stick_bw = _bandwidth_gbps(speed_mts)
    voltages = _voltages(generation, speed_mts, profiles)
    trfc = _trfc_cycles(generation, per_stick_gb)
    tier = _speed_tier(generation, speed_mts, profiles)

    vdd = voltages["vdd"]
    voltage_label = f"{vdd:.2f}V"
    if voltages.get("vddq") is not None and voltages["vddq"] != vdd:
        voltage_label = f"{vdd:.2f}/{voltages['vddq']:.2f}V"

    summary = (
        f"DDR{generation}-{speed_mts} {primary.label} @ {voltage_label} "
        f"({sticks}×{per_stick_gb} GB)"
    )

    sections: list[dict[str, Any]] = [
        {
            "title": "Primary timings",
            "rows": [
                {"label": "CAS Latency (CL)", "value": str(primary.cl)},
                {"label": "tRCD", "value": str(primary.trcd)},
                {"label": "tRP", "value": str(primary.trp)},
                {"label": "tRAS", "value": str(primary.tras)},
                {"label": "tRC", "value": str(primary.trc)},
                {"label": "Timing string", "value": primary.label},
            ],
        },
        {
            "title": "Extended timings",
            "rows": [
                {"label": "tCK", "value": f"{tck} ns"},
                {"label": "tRFC", "value": f"{trfc} cycles (~{round(trfc * tck)} ns)"},
                {"label": "tWR", "value": "24" if generation == 5 else "16"},
                {"label": "Command rate", "value": _command_rate(generation, speed_mts, profiles)},
            ],
        },
        {
            "title": "Voltage",
            "rows": [
                {"label": "VDD", "value": f"{voltages['vdd']:.2f} V"},
                *(
                    [{"label": "VDDQ", "value": f"{voltages['vddq']:.2f} V"}]
                    if voltages.get("vddq") is not None
                    else []
                ),
                *(
                    [{"label": "VPP", "value": f"{voltages['vpp']:.2f} V"}]
                    if voltages.get("vpp") is not None
                    else []
                ),
            ],
        },
        {
            "title": "Module",
            "rows": [
                {"label": "Brand", "value": brand},
                {"label": "Part number", "value": part_number},
                {"label": "Product", "value": product_name},
                {"label": "Kit", "value": f"{sticks}×{per_stick_gb} GB ({total_gb} GB total)"},
                {"label": "Generation", "value": f"DDR{generation}"},
                {"label": "Speed", "value": f"{speed_mts} MT/s"},
                {"label": "Form factor", "value": form_factor.upper()},
                {"label": "ECC", "value": "Yes" if ecc else "No"},
                {"label": "RGB", "value": "Yes" if rgb else "No"},
                {"label": "Profiles", "value": ", ".join(profiles)},
                {"label": "Speed tier", "value": tier.upper()},
                *([{"label": "Verified", "value": verified}] if verified else []),
            ],
        },
        {
            "title": "Performance",
            "rows": [
                {"label": "Per module", "value": f"{per_stick_bw} GB/s (64-bit)"},
                {"label": "Kit aggregate", "value": f"{round(per_stick_bw * sticks, 1)} GB/s"},
                {"label": "Channels", "value": f"{sticks} module{'s' if sticks != 1 else ''}"},
            ],
        },
    ]

    if spd_serials:
        spd_rows = []
        for serial in spd_serials:
            prefix = f"Stick {serial.get('stick_index', '?')}"
            spd_rows.extend(
                [
                    {"label": f"{prefix} serial", "value": serial.get("serial_number", "—")},
                    {"label": f"{prefix} encoding", "value": serial.get("encoding", "—")},
                    {"label": f"{prefix} module ID", "value": serial.get("module_unique_id", "—")},
                ]
            )
        sections.append(
            {
                "title": "SPD programming",
                "rows": spd_rows,
            }
        )

    notes = [
        "Primary and extended timings are estimated from catalog speed, CL, and profile tier.",
        "Verify against the manufacturer XMP/EXPO profile or SPD dump before tuning.",
    ]

    return {
        "summary": summary,
        "primary_timings": {
            "cl": primary.cl,
            "trcd": primary.trcd,
            "trp": primary.trp,
            "tras": primary.tras,
            "trc": primary.trc,
            "label": primary.label,
        },
        "tck_ns": tck,
        "trfc_cycles": trfc,
        "command_rate": _command_rate(generation, speed_mts, profiles),
        "voltages": voltages,
        "speed_tier": tier,
        "requested_profile": requested_profile,
        "sections": sections,
        "notes": notes,
    }

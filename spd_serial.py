"""SPD assembly serial number generation for DDR4/DDR5 modules.

Serial bytes 325-328 follow each brand's observed factory programming model:
production lot counter (+ kit step), blank fields where vendors leave SPD unset,
and module unique ID (320-328) using catalog verification date — not today's date.
"""

from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass
from typing import Literal

Generation = Literal[4, 5]

# JEDEC module manufacturer ID (bytes 320-321)
JEDEC_MODULE_IDS: dict[str, tuple[int, int]] = {
    "kingston": (0x01, 0x98),
    "corsair": (0x02, 0x9E),
    "gskill": (0x04, 0xCD),
    "crucial": (0x00, 0x2C),
    "micron": (0x00, 0x2C),
    "teamgroup": (0x04, 0xFE),
    "patriot": (0x02, 0x94),
    "xpg": (0x04, 0xCB),
    "adata": (0x04, 0xCB),
    "pny": (0x01, 0xA8),
    "oloy": (0x06, 0xBA),
    "geil": (0x04, 0xFE),
    "mushkin": (0x01, 0x94),
    "silicon_power": (0x06, 0xE7),
    "klevv": (0x06, 0xCB),
    "lexar": (0x04, 0xCB),
    "apacer": (0x04, 0xCB),
    "vcolor": (0x06, 0xCB),
    "timetec": (0x06, 0xE7),
    "samsung": (0x00, 0xCE),
    "hynix": (0x00, 0xAD),
    "ballistix": (0x00, 0x2C),
}

SERIAL_SCHEMES: dict[str, str] = {
    "gskill": "empty",
    "corsair": "binary_le",
    "kingston": "binary_be",
    "crucial": "binary_be",
    "micron": "binary_be",
    "samsung": "binary_le",
    "hynix": "binary_le",
    "teamgroup": "tester_seq_le",
    "patriot": "binary_le",
    "xpg": "binary_le",
    "adata": "binary_le",
    "pny": "binary_le",
    "oloy": "binary_le",
    "geil": "binary_le",
    "mushkin": "binary_le",
    "silicon_power": "tester_seq_le",
    "klevv": "binary_le",
    "lexar": "binary_le",
    "apacer": "binary_le",
    "vcolor": "binary_le",
    "timetec": "binary_le",
    "ballistix": "binary_be",
}

SCHEME_NOTES = {
    "empty": "Factory blank SPD serial (0x00000000)",
    "binary_le": "Production counter, little-endian (+1 per module in kit)",
    "binary_be": "Production counter, big-endian (+1 per module in kit)",
    "binary_be_batch": "Micron production batch (+1105 per module in kit)",
    "tester_seq_le": "Factory tester ID (byte 325) + LE production counter (326-328)",
    "ascii4": "Four ASCII characters in bytes 325-328",
}

MICRON_BATCH_STEP = 1105


@dataclass(frozen=True)
class SpdSerialInfo:
    stick_index: int
    serial_number: str
    serial_plain: str
    module_unique_id: str
    raw_bytes: bytes
    raw_bytes_spaced: str
    spd_offset: str
    encoding: str
    encoding_note: str
    uint32_le: int
    uint32_be: int


def parse_verified_date(verified: str | None) -> datetime.date | None:
    if not verified:
        return None
    try:
        return datetime.date.fromisoformat(verified)
    except ValueError:
        return None


def resolve_serial_scheme(
    brand: str,
    profiles: tuple[str, ...] | list[str] | None = None,
) -> tuple[str, int]:
    """Return (encoding scheme, per-stick counter step) for a catalog product."""
    profile_set = set(profiles or [])

    if brand == "gskill":
        return "empty", 0

    if brand == "corsair":
        jedec_only = profile_set <= {"jedec"} and "jedec" in profile_set
        if jedec_only:
            return "empty", 0
        return "binary_le", 1

    if brand == "kingston":
        return "binary_be", 1

    if brand in ("crucial", "micron", "ballistix"):
        return "binary_be", MICRON_BATCH_STEP

    if brand in ("teamgroup", "silicon_power"):
        return "tester_seq_le", 1

    default = SERIAL_SCHEMES.get(brand, "binary_le")
    return default, 1


def _batch_base(part_number: str, serial_salt: int, generation: Generation) -> int:
    """Deterministic production-lot start counter from SKU + batch salt."""
    payload = f"{part_number}|{generation}|{serial_salt}".encode()
    digest = hashlib.sha256(payload).digest()
    value = int.from_bytes(digest[:4], "little") & 0x00FFFFFF
    return value or 0x0424A9


def _tester_id(serial_salt: int) -> int:
    return ((serial_salt >> 8) & 0xFF) % 0x0F or 0x01


def _mfg_date_bcd(when: datetime.date | None = None) -> tuple[int, int]:
    when = when or datetime.date.today()
    year = when.year % 100
    week = when.isocalendar().week
    return _to_bcd(year), _to_bcd(min(week, 53))


def _to_bcd(value: int) -> int:
    return ((value // 10) << 4) | (value % 10)


def format_assembly_serial(raw: bytes) -> tuple[str, str]:
    """Format like decode-dimms / Thaiphoon: 0x + byte325..328."""
    if len(raw) != 4:
        raise ValueError("SPD assembly serial must be exactly 4 bytes")
    plain = "".join(f"{b:02X}" for b in raw)
    return f"0x{plain}", plain


def build_module_unique_id(
    brand: str,
    raw_serial: bytes,
    when: datetime.date | None = None,
) -> str:
    """JEDEC 9-byte unique module identifier (bytes 320-328)."""
    cont, code = JEDEC_MODULE_IDS.get(brand, (0x01, 0x98))
    year_bcd, week_bcd = _mfg_date_bcd(when)
    block = bytes([cont, code, 0x01, year_bcd, week_bcd]) + raw_serial
    return "0x" + block.hex().upper()


def _counter_for_stick(base: int, stick_index: int, step: int) -> int:
    return (base + (stick_index - 1) * step) & 0xFFFFFFFF


def _encode_counter(
    scheme: str,
    counter: int,
    *,
    tester_id: int = 1,
) -> bytes:
    if scheme == "empty":
        return b"\x00\x00\x00\x00"

    if scheme == "tester_seq_le":
        body = counter & 0xFFFFFF
        return bytes([tester_id & 0xFF]) + body.to_bytes(3, "little")

    if scheme == "binary_be":
        return counter.to_bytes(4, "big")

    if scheme == "ascii4":
        chars = f"{counter & 0xFFFF:04X}"[:4]
        return chars.encode("ascii")

    return counter.to_bytes(4, "little")


def _encoding_label(scheme: str, step: int) -> tuple[str, str]:
    if scheme == "empty":
        return scheme, SCHEME_NOTES["empty"]
    if scheme == "tester_seq_le":
        return scheme, SCHEME_NOTES["tester_seq_le"]
    if step == MICRON_BATCH_STEP:
        return "binary_be_batch", SCHEME_NOTES["binary_be_batch"]
    note = SCHEME_NOTES.get(scheme, scheme)
    return scheme, note


def generate_spd_serials(
    brand: str,
    part_number: str,
    generation: Generation,
    stick_count: int,
    serial_salt: int = 0,
    profiles: tuple[str, ...] | list[str] | None = None,
    verified: str | None = None,
) -> list[SpdSerialInfo]:
    scheme, step = resolve_serial_scheme(brand, profiles)
    mfg_date = parse_verified_date(verified)
    base = _batch_base(part_number, serial_salt, generation)
    tester = _tester_id(serial_salt)
    encoding, encoding_note = _encoding_label(scheme, step)
    results: list[SpdSerialInfo] = []

    for stick in range(1, stick_count + 1):
        counter = _counter_for_stick(base, stick, step)
        raw = _encode_counter(scheme, counter, tester_id=tester)
        serial_number, serial_plain = format_assembly_serial(raw)
        results.append(
            SpdSerialInfo(
                stick_index=stick,
                serial_number=serial_number,
                serial_plain=serial_plain,
                module_unique_id=build_module_unique_id(brand, raw, mfg_date),
                raw_bytes=raw,
                raw_bytes_spaced=" ".join(f"{b:02X}" for b in raw),
                spd_offset="325-328 (0x145-0x148)",
                encoding=encoding,
                encoding_note=encoding_note,
                uint32_le=int.from_bytes(raw, "little"),
                uint32_be=int.from_bytes(raw, "big"),
            )
        )
    return results


def generate_crucial_batch_serials(
    part_number: str,
    existing_serials: list[str],
    count: int,
    step: int = MICRON_BATCH_STEP,
) -> list[SpdSerialInfo]:
    """Extrapolate Crucial/Micron batch serials (+1105 BE step pattern)."""
    parsed = [int(s.removeprefix("0x").removeprefix("0X"), 16) for s in existing_serials]
    start = max(parsed)
    seen = set(parsed)
    results: list[SpdSerialInfo] = []
    cur = start

    for stick in range(len(parsed) + 1, len(parsed) + count + 1):
        cur += step
        while cur in seen:
            cur += 1
        seen.add(cur)
        raw = cur.to_bytes(4, "big")
        serial_number, serial_plain = format_assembly_serial(raw)
        results.append(
            SpdSerialInfo(
                stick_index=stick,
                serial_number=serial_number,
                serial_plain=serial_plain,
                module_unique_id=build_module_unique_id("crucial", raw),
                raw_bytes=raw,
                raw_bytes_spaced=" ".join(f"{b:02X}" for b in raw),
                spd_offset="325-328 (0x145-0x148)",
                encoding="binary_be_batch",
                encoding_note=f"Micron batch step +{step} from observed serials",
                uint32_le=int.from_bytes(raw, "little"),
                uint32_be=int.from_bytes(raw, "big"),
            )
        )
    return results


def spd_serial_to_dict(info: SpdSerialInfo) -> dict:
    return {
        "stick_index": info.stick_index,
        "serial_number": info.serial_number,
        "serial_plain": info.serial_plain,
        "module_unique_id": info.module_unique_id,
        "raw_bytes": info.raw_bytes_spaced,
        "spd_offset": info.spd_offset,
        "encoding": info.encoding,
        "encoding_note": info.encoding_note,
        "uint32_le": f"0x{info.uint32_le:08X}",
        "uint32_be": f"0x{info.uint32_be:08X}",
    }

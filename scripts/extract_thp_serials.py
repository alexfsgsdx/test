#!/usr/bin/env python3
"""Extract SPD assembly serial numbers from Thaiphoon .thp dumps.

Decoding logic reversed from SPD-Reader-Writer (Thaiphoon TH2/TH4/TH5 import).
Works on passnet-spd/Unsorted-SPD-Dumps and compatible .thp collections.

Usage:
  python3 scripts/extract_thp_serials.py /path/to/dumps -o data/spd_dump_serials.csv
"""

from __future__ import annotations

import argparse
import csv
import struct
from pathlib import Path

GO0 = bytes.fromhex("040000")
GO1 = bytes.fromhex("e38f0c")
ROLL_INIT = 15053 ^ 0x3B1A
ROLL_ADD = 44692 ^ 0x9F3B


def crc16(data: bytes, init: int = 0) -> int:
    crc = init
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return crc


def validate_spd(spd: bytes) -> tuple[bool, str]:
    if len(spd) < 3:
        return False, "?"
    t = spd[2]
    if t == 0x0B and len(spd) >= 126:
        return True, "DDR3"
    if t == 0x0C and len(spd) >= 384:
        ok = crc16(spd[0:126]) == int.from_bytes(spd[126:128], "little")
        return ok, "DDR4"
    if t == 0x12 and len(spd) >= 512:
        ok = crc16(spd[0:510]) == int.from_bytes(spd[510:512], "little")
        return ok, "DDR5"
    return False, "?"


def decrypt_roll(body: bytes, size: int) -> bytes:
    arr = bytearray(body[:size])
    num20 = ROLL_INIT
    for i in range(len(arr)):
        b = (num20 >> 8) & 0xFF
        num20 = (num20 + arr[i] + ROLL_ADD) & 0xFFFF
        arr[i] ^= b
    return bytes(arr)


def decrypt_text3(body: bytes, key: bytes, size: int = 512) -> bytes:
    arr = bytearray(body[:size])
    text3 = key.hex().upper().encode("ascii")
    for i in range(1, len(arr)):
        arr[i] ^= text3[(i - 1) % len(text3)]
    return bytes(arr)


def decrypt_xor_index(body: bytes, size: int = 256) -> bytes:
    return bytes((b ^ (i & 0xFF)) & 0xFF for i, b in enumerate(body[:size]))


def decode_thp(raw: bytes) -> tuple[str, bytes | None, str]:
    if len(raw) < 5 or raw[0] != 0x04:
        return "?", None, "?"
    tag = raw[1:5].decode("ascii", "replace")
    body = raw[5:]
    candidates: list[bytes] = []

    if tag in ("TH43", "TH42"):
        candidates.append(decrypt_roll(body, 512))
    elif tag in ("TH53", "TH50"):
        candidates.append(decrypt_roll(body, 1024))
    elif tag == "TH20":
        candidates.append(decrypt_xor_index(body, 256))
    elif tag == "TH41":
        candidates.extend([decrypt_text3(body, GO1), decrypt_text3(body, GO0)])
    else:
        candidates.extend(
            [
                decrypt_roll(body, 512),
                decrypt_text3(body, GO1),
                decrypt_text3(body, GO0),
            ]
        )

    for spd in candidates:
        ok, gen = validate_spd(spd)
        if ok:
            return tag, spd, gen
    return tag, None, "?"


def serial_hex(spd: bytes) -> str:
    off = {0x0B: 122, 0x0C: 325, 0x12: 517}.get(spd[2], 325)
    return spd[off : off + 4].hex().upper()


def iter_thp(root: Path):
    for path in sorted(root.rglob("*.thp")):
        if path.is_file():
            yield path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump_dir", type=Path, help="Directory containing .thp files")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output CSV path")
    args = parser.parse_args()

    rows: list[dict[str, str]] = []
    for path in iter_thp(args.dump_dir):
        tag, spd, gen = decode_thp(path.read_bytes())
        if spd is None:
            rows.append(
                {
                    "filename": path.name,
                    "format": tag,
                    "generation": "?",
                    "serial_hex": "",
                    "valid": "no",
                }
            )
            continue
        rows.append(
            {
                "filename": path.name,
                "format": tag,
                "generation": gen,
                "serial_hex": "0x" + serial_hex(spd),
                "valid": "yes",
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["filename", "format", "generation", "serial_hex", "valid"]
        )
        writer.writeheader()
        writer.writerows(rows)

    valid = sum(1 for r in rows if r["valid"] == "yes")
    print(f"Wrote {len(rows)} rows to {args.output} ({valid} CRC-valid)")


if __name__ == "__main__":
    main()

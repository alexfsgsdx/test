"""Scan .pyd binaries for embedded Python bytecode and extract .pyc files."""

from __future__ import annotations

import marshal
import struct
from dataclasses import dataclass
from pathlib import Path

from pyd_decompiler.magic import HEADER_SIZES, identify_magic


@dataclass
class EmbeddedPyc:
    offset: int
    version: str
    header_size: int
    size: int
    module_name: str | None
    valid_marshal: bool
    code_name: str | None = None


def _try_load_code_object(data: bytes, header_size: int) -> tuple[bool, str | None]:
    """Validate marshal payload after pyc header."""
    payload = data[header_size:]
    if not payload:
        return False, None
    try:
        obj = marshal.loads(payload)
    except (ValueError, TypeError, EOFError):
        return False, None
    if hasattr(obj, "co_name"):
        return True, obj.co_name  # type: ignore[attr-defined]
    return True, None


def _estimate_pyc_size(data: bytes, offset: int, header_size: int) -> int:
    """Estimate embedded pyc blob size by scanning marshal object."""
    payload_start = offset + header_size
    payload = data[payload_start:]
    if not payload:
        return header_size

    # Walk marshal stream for top-level code object.
    try:
        obj = marshal.loads(payload)
        consumed = _marshal_consumed_size(payload, obj)
        if consumed:
            return header_size + consumed
    except (ValueError, TypeError, EOFError):
        pass

    # Fallback: scan until next magic or cap size.
    max_scan = min(len(data) - offset, 512 * 1024)
    for end in range(header_size + 64, max_scan, 64):
        chunk = data[offset : offset + end]
        ok, _ = _try_load_code_object(chunk, header_size)
        if ok:
            return end
    return min(max_scan, len(data) - offset)


def _marshal_consumed_size(payload: bytes, obj: object) -> int | None:
    """Approximate bytes consumed by marshal.loads via re-serialization probe."""
    try:
        reserialized = marshal.dumps(obj)
    except (ValueError, TypeError):
        return None
    # Find reserialized blob inside payload (best-effort).
    idx = payload.find(reserialized)
    if idx == 0:
        return len(reserialized)
    # If not at start, assume entire first object length from successful load.
    return len(reserialized)


def scan_for_pyc(data: bytes) -> list[EmbeddedPyc]:
    """Find candidate embedded .pyc headers in binary data."""
    found: list[EmbeddedPyc] = []
    seen_offsets: set[int] = set()
    magics = [
        b"\x61\x0d\r\n",
        b"\x6f\x0d\r\n",
        b"\xa7\x0d\r\n",
        b"\xcb\x0d\r\n",
        b"\xed\x0d\r\n",
        b"\x55\x0d\r\n",
        b"\x42\x0d\r\n",
        b"\x33\x0d\r\n",
        b"\x17\x0d\r\n",
        b"\x03\xf3\r\n",
    ]

    for magic in magics:
        start = 0
        while True:
            idx = data.find(magic, start)
            if idx == -1:
                break
            if idx in seen_offsets:
                start = idx + 1
                continue

            version, header_size = identify_magic(data, idx)
            if not version:
                start = idx + 1
                continue

            # Require plausible header: flags/timestamp region not all zeros-only check
            if idx + header_size >= len(data):
                start = idx + 1
                continue

            valid, code_name = _try_load_code_object(
                data[idx : idx + min(len(data) - idx, 1024 * 1024)],
                header_size,
            )
            if not valid:
                start = idx + 1
                continue

            size = _estimate_pyc_size(data, idx, header_size)
            seen_offsets.add(idx)

            found.append(
                EmbeddedPyc(
                    offset=idx,
                    version=version,
                    header_size=header_size,
                    size=size,
                    module_name=code_name,
                    valid_marshal=True,
                    code_name=code_name,
                )
            )
            start = idx + 4

    found.sort(key=lambda x: x.offset)
    return _dedupe_overlapping(found)


def _dedupe_overlapping(candidates: list[EmbeddedPyc]) -> list[EmbeddedPyc]:
    if not candidates:
        return []
    result = [candidates[0]]
    for cand in candidates[1:]:
        prev = result[-1]
        if cand.offset < prev.offset + prev.size:
            continue
        result.append(cand)
    return result


def extract_pyc_files(
    data: bytes,
    candidates: list[EmbeddedPyc],
    output_dir: Path,
    *,
    stem: str = "embedded",
) -> list[Path]:
    """Write extracted .pyc files to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for i, cand in enumerate(candidates):
        blob = data[cand.offset : cand.offset + cand.size]
        if len(blob) < cand.header_size:
            continue

        name_parts = [stem, f"{i:03d}", f"py{cand.version.replace('.', '')}"]
        if cand.code_name:
            safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in cand.code_name)
            name_parts.insert(1, safe)
        out_path = output_dir / ("_".join(name_parts) + ".pyc")
        out_path.write_bytes(blob)
        written.append(out_path)

    return written


def repair_pyc_header(data: bytes, version: str) -> bytes:
    """Ensure pyc has a valid header for the given Python version."""
    from pyd_decompiler.magic import PYTHON_MAGICS

    header_size = HEADER_SIZES.get(version, 16)
    magic = next((m for m, v in PYTHON_MAGICS.items() if v == version), None)
    if magic is None:
        return data

    if data[:4] == magic and len(data) >= header_size:
        return data

    # Build minimal header: magic + 12 zero bytes (flags/hash/timestamp).
    header = magic + b"\x00" * (header_size - 4)
    if data[:4] in PYTHON_MAGICS:
        return header + data[header_size:]
    return header + data

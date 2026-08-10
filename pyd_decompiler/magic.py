"""Python bytecode magic number registry."""

from __future__ import annotations

# Common CPython magic numbers (little-endian uint32 as bytes prefix).
# Source: CPython importlib/_bootstrap_external.py across versions.
PYTHON_MAGICS: dict[bytes, str] = {
    b"\x03\xf3\r\n": "2.7",
    b"\xb3\xf2\r\n": "3.0",
    b"\xcb\xd2\r\n": "3.1",
    b"\xd1\xe2\r\n": "3.2",
    b"\xa6\x1d\r\n": "3.3",
    b"\xee\x0c\r\n": "3.4",
    b"\x17\x0d\r\n": "3.5",
    b"\x33\x0d\r\n": "3.6",
    b"\x42\x0d\r\n": "3.7",
    b"\x55\x0d\r\n": "3.8",
    b"\x61\x0d\r\n": "3.9",
    b"\x6f\x0d\r\n": "3.10",
    b"\xa7\x0d\r\n": "3.11",
    b"\xcb\x0d\r\n": "3.12",
    b"\xed\x0d\r\n": "3.13",
    b"\x2b\x0e\r\n": "3.14",
}

# Minimum header sizes by era (magic + fields before marshal payload).
HEADER_SIZES: dict[str, int] = {
    "2.7": 8,
    "3.0": 12,
    "3.1": 12,
    "3.2": 12,
    "3.3": 12,
    "3.4": 12,
    "3.5": 12,
    "3.6": 16,
    "3.7": 16,
    "3.8": 16,
    "3.9": 16,
    "3.10": 16,
    "3.11": 16,
    "3.12": 16,
    "3.13": 16,
    "3.14": 16,
}


def identify_magic(data: bytes, offset: int) -> tuple[str | None, int]:
    """Return (python_version, header_size) if magic at offset is valid."""
    if offset + 4 > len(data):
        return None, 0
    magic = data[offset : offset + 4]
    if magic not in PYTHON_MAGICS:
        return None, 0
    version = PYTHON_MAGICS[magic]
    return version, HEADER_SIZES.get(version, 16)


def all_magic_prefixes() -> list[bytes]:
    return list(PYTHON_MAGICS.keys())

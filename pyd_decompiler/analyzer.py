"""PE analysis and module-type detection for .pyd files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import pefile
except ImportError as exc:  # pragma: no cover
    raise ImportError("pefile is required. Install with: pip install pefile") from exc


@dataclass
class ExportInfo:
    name: str
    ordinal: int | None = None
    address: int | None = None


@dataclass
class ImportInfo:
    dll: str
    functions: list[str] = field(default_factory=list)


@dataclass
class SectionInfo:
    name: str
    virtual_address: int
    virtual_size: int
    raw_size: int
    entropy: float


@dataclass
class AnalysisReport:
    path: Path
    file_size: int
    architecture: str
    python_init: str | None
    module_type: str
    confidence: str
    indicators: list[str] = field(default_factory=list)
    exports: list[ExportInfo] = field(default_factory=list)
    imports: list[ImportInfo] = field(default_factory=list)
    sections: list[SectionInfo] = field(default_factory=list)
    strings: list[str] = field(default_factory=list)
    cython_symbols: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "file_size": self.file_size,
            "architecture": self.architecture,
            "python_init": self.python_init,
            "module_type": self.module_type,
            "confidence": self.confidence,
            "indicators": self.indicators,
            "exports": [e.name for e in self.exports],
            "imports": {i.dll: i.functions for i in self.imports},
            "sections": [
                {
                    "name": s.name,
                    "virtual_address": hex(s.virtual_address),
                    "virtual_size": s.virtual_size,
                    "raw_size": s.raw_size,
                    "entropy": round(s.entropy, 3),
                }
                for s in self.sections
            ],
            "cython_symbol_count": len(self.cython_symbols),
            "string_count": len(self.strings),
            "error": self.error,
        }


CYTHON_PATTERNS = (
    re.compile(r"__pyx_", re.I),
    re.compile(r"PyInit___pyx_", re.I),
    re.compile(r"cython", re.I),
    re.compile(r"__Pyx_", re.I),
)

NUITKA_PATTERNS = (
    re.compile(r"nuitka", re.I),
    re.compile(r"__nuitka", re.I),
    re.compile(r"Nuitka_", re.I),
)

PYBIND_PATTERNS = (
    re.compile(r"pybind11", re.I),
    re.compile(r"Pybind11", re.I),
)

NUMPY_PATTERNS = (
    re.compile(r"numpy", re.I),
    re.compile(r"_multiarray", re.I),
)


def _entropy(data: bytes) -> float:
    if not data:
        return 0.0
    import math

    freq = [0] * 256
    for byte in data:
        freq[byte] += 1
    entropy = 0.0
    length = len(data)
    for count in freq:
        if count:
            p = count / length
            entropy -= p * math.log2(p)
    return entropy


def _extract_printable_strings(data: bytes, min_length: int = 6) -> list[str]:
    pattern = re.compile(rb"[\x20-\x7e]{%d,}" % min_length)
    seen: set[str] = set()
    results: list[str] = []
    for match in pattern.finditer(data):
        text = match.group().decode("ascii", errors="ignore")
        if text not in seen:
            seen.add(text)
            results.append(text)
    return sorted(results, key=len, reverse=True)


def _detect_module_type(
    exports: list[str],
    strings: list[str],
    imports: list[str],
) -> tuple[str, str, list[str]]:
    indicators: list[str] = []
    corpus = " ".join(exports + strings + imports).lower()

    cython_hits = sum(1 for p in CYTHON_PATTERNS if p.search(corpus))
    nuitka_hits = sum(1 for p in NUITKA_PATTERNS if p.search(corpus))
    pybind_hits = sum(1 for p in PYBIND_PATTERNS if p.search(corpus))

    if nuitka_hits >= 2 or "nuitka" in corpus:
        indicators.append("Nuitka markers in binary")
        return "nuitka", "high" if nuitka_hits >= 2 else "medium", indicators

    if cython_hits >= 2 or any("__pyx_" in e.lower() for e in exports):
        indicators.append("Cython __pyx_ symbols detected")
        return "cython", "high" if cython_hits >= 2 else "medium", indicators

    if pybind_hits >= 1:
        indicators.append("pybind11 markers detected")
        return "pybind11", "medium", indicators

    if any("python3" in i.lower() or "python311" in i.lower() for i in imports):
        indicators.append("Links against Python runtime DLL")

    if any(e.startswith("PyInit_") or e.startswith("init") for e in exports):
        indicators.append("Standard Python module entry point")
        return "cpython_extension", "high", indicators

    return "unknown_native", "low", indicators


def analyze_pyd(path: Path, *, max_strings: int = 500) -> AnalysisReport:
    """Analyze a .pyd (PE) file and return a structured report."""
    path = Path(path)
    raw = path.read_bytes()
    report = AnalysisReport(
        path=path,
        file_size=len(raw),
        architecture="unknown",
        python_init=None,
        module_type="unknown",
        confidence="low",
    )

    try:
        pe = pefile.PE(data=raw, fast_load=True)
    except pefile.PEFormatError as exc:
        report.error = f"Invalid PE file: {exc}"
        return report

    machine = pe.FILE_HEADER.Machine
    arch_map = {
        0x014C: "x86",
        0x8664: "x64",
        0xAA64: "ARM64",
    }
    report.architecture = arch_map.get(machine, hex(machine))

    pe.parse_data_directories(
        directories=[
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"],
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
        ]
    )

    exports: list[ExportInfo] = []
    if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        for sym in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            if sym.name:
                name = sym.name.decode("utf-8", errors="replace")
                exports.append(
                    ExportInfo(name=name, ordinal=sym.ordinal, address=sym.address)
                )
                if name.startswith("PyInit_"):
                    report.python_init = name
                elif name.startswith("init") and report.python_init is None:
                    report.python_init = name

    report.exports = exports
    report.cython_symbols = [e.name for e in exports if "__pyx_" in e.name.lower()]

    imports: list[ImportInfo] = []
    import_names: list[str] = []
    if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            dll = entry.dll.decode("utf-8", errors="replace")
            funcs = []
            for imp in entry.imports:
                if imp.name:
                    fname = imp.name.decode("utf-8", errors="replace")
                    funcs.append(fname)
                    import_names.append(fname)
            imports.append(ImportInfo(dll=dll, functions=funcs))

    report.imports = imports

    for section in pe.sections:
        name = section.Name.rstrip(b"\x00").decode("utf-8", errors="replace")
        data = section.get_data()
        report.sections.append(
            SectionInfo(
                name=name,
                virtual_address=section.VirtualAddress,
                virtual_size=section.Misc_VirtualSize,
                raw_size=section.SizeOfRawData,
                entropy=_entropy(data),
            )
        )

    report.strings = _extract_printable_strings(raw)[:max_strings]

    module_type, confidence, indicators = _detect_module_type(
        [e.name for e in exports],
        report.strings,
        import_names + [i.dll for i in imports],
    )
    report.module_type = module_type
    report.confidence = confidence
    report.indicators = indicators

    pe.close()
    return report

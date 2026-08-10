"""Command-line interface for pyd_decompiler."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pyd_decompiler import __version__
from pyd_decompiler.analyzer import AnalysisReport, analyze_pyd
from pyd_decompiler.bytecode import extract_pyc_files, scan_for_pyc
from pyd_decompiler.decompiler import decompile_all


def _write_report(report: AnalysisReport, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "analysis_report.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    text_lines = [
        "=" * 60,
        "PYD DECOMPILER — ANALYSIS REPORT",
        "=" * 60,
        f"File:           {report.path}",
        f"Size:           {report.file_size:,} bytes",
        f"Architecture:   {report.architecture}",
        f"Module type:    {report.module_type} ({report.confidence} confidence)",
        f"Python init:    {report.python_init or 'not found'}",
        "",
        "Indicators:",
    ]
    for item in report.indicators or ["(none)"]:
        text_lines.append(f"  • {item}")

    text_lines.extend(["", "Exports:"])
    for exp in report.exports[:30]:
        text_lines.append(f"  • {exp.name}")
    if len(report.exports) > 30:
        text_lines.append(f"  ... and {len(report.exports) - 30} more")

    text_lines.extend(["", "Imports:"])
    for imp in report.imports[:20]:
        funcs = ", ".join(imp.functions[:5])
        suffix = "..." if len(imp.functions) > 5 else ""
        text_lines.append(f"  • {imp.dll}: {funcs}{suffix}")

    text_lines.extend(["", "Notable strings (top 25):"])
    for s in report.strings[:25]:
        display = s if len(s) <= 100 else s[:97] + "..."
        text_lines.append(f"  • {display}")

    if report.module_type in ("cython", "nuitka", "cpython_extension", "pybind11"):
        text_lines.extend(
            [
                "",
                "NOTE:",
                "  Native .pyd modules are compiled machine code (C/C++/Cython/Nuitka).",
                "  Full source recovery is generally NOT possible without RE tools",
                "  (Ghidra, IDA). This tool extracts embedded bytecode when present.",
            ]
        )

    text_path = output_dir / "analysis_report.txt"
    text_path.write_text("\n".join(text_lines) + "\n", encoding="utf-8")
    return report_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyd-decompiler",
        description=(
            "Analyze and decompile Python .pyd extension modules. "
            "Scans for embedded bytecode and decompiles .pyc when found."
        ),
    )
    parser.add_argument("input", type=Path, help="Path to .pyd file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: <input>_decompiled/)",
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Only analyze PE structure; skip bytecode scan/decompile",
    )
    parser.add_argument(
        "--no-decompile",
        action="store_true",
        help="Extract embedded .pyc files but skip decompilation",
    )
    parser.add_argument(
        "--backend",
        choices=["decompyle3", "uncompyle6", "pycdc", "dis"],
        default=None,
        help="Preferred decompiler backend",
    )
    parser.add_argument(
        "--strings",
        type=int,
        default=500,
        metavar="N",
        help="Max printable strings to collect (default: 500)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path: Path = args.input
    if not input_path.is_file():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        return 1

    if input_path.suffix.lower() not in (".pyd", ".dll", ".so"):
        print(
            f"Warning: expected .pyd extension, got {input_path.suffix}",
            file=sys.stderr,
        )

    output_dir = args.output or Path(f"{input_path.stem}_decompiled")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Analyzing {input_path} ...")
    report = analyze_pyd(input_path, max_strings=args.strings)
    _write_report(report, output_dir)

    if report.error:
        print(f"[!] PE analysis error: {report.error}", file=sys.stderr)
        return 1

    print(f"[+] Type: {report.module_type} ({report.confidence})")
    print(f"[+] Architecture: {report.architecture}")
    if report.python_init:
        print(f"[+] Entry point: {report.python_init}")
    print(f"[+] Report: {output_dir / 'analysis_report.txt'}")

    if args.scan_only:
        return 0

    raw = input_path.read_bytes()
    print("[*] Scanning for embedded Python bytecode ...")
    candidates = scan_for_pyc(raw)
    print(f"[+] Found {len(candidates)} embedded .pyc candidate(s)")

    if not candidates:
        if report.module_type in ("cython", "nuitka", "cpython_extension"):
            print(
                "[!] No embedded bytecode found. This appears to be native compiled code.",
                file=sys.stderr,
            )
            print(
                "[!] Use the analysis report + a disassembler (Ghidra/IDA) for RE.",
                file=sys.stderr,
            )
        return 0

    pyc_dir = output_dir / "extracted_pyc"
    pyc_files = extract_pyc_files(raw, candidates, pyc_dir, stem=input_path.stem)
    for pyc in pyc_files:
        print(f"    extracted: {pyc.name}")

    if args.no_decompile:
        return 0

    print("[*] Decompiling extracted bytecode ...")
    source_dir = output_dir / "decompiled_source"
    results = decompile_all(
        pyc_files, source_dir, preferred_backend=args.backend
    )

    ok_count = sum(1 for r in results if r.success)
    print(f"[+] Decompiled {ok_count}/{len(results)} file(s) -> {source_dir}")

    for result in results:
        if result.success and args.verbose:
            print(f"    {result.source_path.name} via {result.backend}")
        elif not result.success:
            print(
                f"    [!] Failed {result.source_path.name}: {result.message}",
                file=sys.stderr,
            )

    return 0 if ok_count or not pyc_files else 1


if __name__ == "__main__":
    raise SystemExit(main())

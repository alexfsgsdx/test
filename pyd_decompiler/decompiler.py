"""Multi-backend Python bytecode decompiler."""

from __future__ import annotations

import dis
import io
import marshal
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class DecompileResult:
    source_path: Path
    output_path: Path | None
    backend: str
    success: bool
    message: str
    source_preview: str = ""


def _read_code_object(pyc_path: Path) -> tuple[object | None, str]:
    data = pyc_path.read_bytes()
    if len(data) < 16:
        return None, "File too small for pyc header"

    header_sizes = (8, 12, 16)
    for header_size in header_sizes:
        if len(data) <= header_size:
            continue
        try:
            return marshal.loads(data[header_size:]), ""
        except (ValueError, TypeError, EOFError):
            continue
    return None, "Could not unmarshal code object"


def _decompile_uncompyle6(pyc_path: Path) -> tuple[bool, str, str]:
    try:
        import uncompyle6
    except ImportError:
        return False, "", "uncompyle6 not installed"

    out = io.StringIO()
    try:
        uncompyle6.decompile_file(str(pyc_path), out)
        text = out.getvalue()
        return bool(text.strip()), text, ""
    except Exception as exc:  # noqa: BLE001
        return False, "", str(exc)


def _decompile_decompyle3(pyc_path: Path) -> tuple[bool, str, str]:
    try:
        from decompyle3 import decompile_file
    except ImportError:
        return False, "", "decompyle3 not installed"

    out = io.StringIO()
    try:
        decompile_file(str(pyc_path), out)
        text = out.getvalue()
        return bool(text.strip()), text, ""
    except Exception as exc:  # noqa: BLE001
        return False, "", str(exc)


def _decompile_pycdc(pyc_path: Path) -> tuple[bool, str, str]:
    pycdc = shutil.which("pycdc")
    if not pycdc:
        for candidate in ("./pycdc", "/usr/local/bin/pycdc"):
            if Path(candidate).is_file():
                pycdc = candidate
                break
    if not pycdc:
        return False, "", "pycdc not found on PATH"

    try:
        proc = subprocess.run(
            [pycdc, str(pyc_path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, "", str(exc)

    text = proc.stdout or ""
    if proc.returncode == 0 and text.strip():
        return True, text, ""
    err = (proc.stderr or "").strip() or f"exit code {proc.returncode}"
    return False, text, err


def _decompile_dis(pyc_path: Path) -> tuple[bool, str, str]:
    code, err = _read_code_object(pyc_path)
    if code is None:
        return False, "", err

    out = io.StringIO()
    out.write(f"# Bytecode disassembly fallback for {pyc_path.name}\n")
    out.write(f"# Python {sys.version_info.major}.{sys.version_info.minor}\n\n")
    try:
        dis.dis(code, file=out)
    except Exception as exc:  # noqa: BLE001
        return False, "", str(exc)
    text = out.getvalue()
    return True, text, ""


BACKENDS: list[tuple[str, Callable[[Path], tuple[bool, str, str]]]] = [
    ("decompyle3", _decompile_decompyle3),
    ("uncompyle6", _decompile_uncompyle6),
    ("pycdc", _decompile_pycdc),
    ("dis", _decompile_dis),
]


def decompile_pyc(
    pyc_path: Path,
    output_dir: Path,
    *,
    preferred_backend: str | None = None,
) -> DecompileResult:
    """Decompile a single .pyc file using available backends."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / (pyc_path.stem + ".py")

    backends = BACKENDS
    if preferred_backend:
        backends = sorted(
            BACKENDS,
            key=lambda b: 0 if b[0] == preferred_backend else 1,
        )

    errors: list[str] = []
    for name, fn in backends:
        ok, text, err = fn(pyc_path)
        if ok and text.strip():
            out_path.write_text(text, encoding="utf-8")
            preview = "\n".join(text.splitlines()[:20])
            return DecompileResult(
                source_path=pyc_path,
                output_path=out_path,
                backend=name,
                success=True,
                message=f"Decompiled with {name}",
                source_preview=preview,
            )
        if err:
            errors.append(f"{name}: {err}")

    return DecompileResult(
        source_path=pyc_path,
        output_path=None,
        backend="none",
        success=False,
        message="; ".join(errors) or "All backends failed",
    )


def decompile_all(
    pyc_files: list[Path],
    output_dir: Path,
    *,
    preferred_backend: str | None = None,
) -> list[DecompileResult]:
    return [
        decompile_pyc(p, output_dir, preferred_backend=preferred_backend)
        for p in pyc_files
    ]

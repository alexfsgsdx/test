"""Basic tests for pyd_decompiler."""

from __future__ import annotations

import marshal
import struct
import tempfile
import unittest
from pathlib import Path

from pyd_decompiler.bytecode import scan_for_pyc
from pyd_decompiler.magic import identify_magic


def _make_pyc(version_magic: bytes, code_obj) -> bytes:
    header = version_magic + b"\x00" * 12
    return header + marshal.dumps(code_obj)


class TestBytecodeScanner(unittest.TestCase):
    def test_identify_magic_py311(self):
        magic = b"\xa7\x0d\r\n"
        version, size = identify_magic(magic + b"\x00" * 12, 0)
        self.assertEqual(version, "3.11")
        self.assertEqual(size, 16)

    def test_scan_embedded_pyc(self):
        code = compile("x = 1 + 2", "<test>", "exec")
        pyc = _make_pyc(b"\xa7\x0d\r\n", code)
        blob = b"\x00" * 1024 + pyc + b"\xff" * 512
        found = scan_for_pyc(blob)
        self.assertGreaterEqual(len(found), 1)
        self.assertEqual(found[0].version, "3.11")
        self.assertTrue(found[0].valid_marshal)


class TestCLI(unittest.TestCase):
    def test_help(self):
        from pyd_decompiler.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["dummy.pyd"])
        self.assertEqual(args.input, Path("dummy.pyd"))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Backward-compatible wrapper — use merge_catalog.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from merge_catalog import main  # noqa: E402

if __name__ == "__main__":
    main()

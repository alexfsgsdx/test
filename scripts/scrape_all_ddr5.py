#!/usr/bin/env python3
"""Run all DDR5 scrapers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [
    "scrape_corsair_ddr5.py",
    "scrape_gskill_ddr5.py",
    "scrape_kingston_ddr5.py",
    "scrape_teamgroup_ddr5.py",
    "scrape_misc_ddr5.py",
]


def main() -> None:
    for name in SCRIPTS:
        path = ROOT / "scripts" / name
        if not path.exists():
            print(f"skip missing {name}")
            continue
        print(f"\n=== {name} ===")
        rc = subprocess.call([sys.executable, str(path)], cwd=ROOT)
        if rc != 0:
            print(f"WARNING: {name} exited {rc}")


if __name__ == "__main__":
    main()

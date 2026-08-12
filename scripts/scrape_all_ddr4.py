#!/usr/bin/env python3
"""Run all DDR4 manufacturer scrapers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

SCRAPERS = [
    "scrape_corsair_ddr4.py",
    "scrape_gskill_ddr4.py",
    "scrape_teamgroup_ddr4.py",
    "scrape_kingston_ddr4.py",
    "scrape_misc_ddr4.py",
]


def main() -> None:
    for name in SCRAPERS:
        path = SCRIPTS / name
        print(f"\n=== {name} ===")
        subprocess.run([sys.executable, str(path)], check=True)
    print("\n=== merge_catalog.py ===")
    subprocess.run([sys.executable, str(SCRIPTS / "merge_catalog.py")], check=True)


if __name__ == "__main__":
    main()

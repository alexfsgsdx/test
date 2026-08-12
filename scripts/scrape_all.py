#!/usr/bin/env python3
"""Run all DDR4 + DDR5 scrapers and rebuild the catalog."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(name: str) -> None:
    path = SCRIPTS / name
    if not path.exists():
        print(f"skip missing {name}")
        return
    print(f"\n=== {name} ===")
    rc = subprocess.call([sys.executable, str(path)], cwd=ROOT)
    if rc != 0:
        raise SystemExit(f"{name} exited {rc}")


def main() -> None:
    for name in (
        "scrape_all_ddr5.py",
        "scrape_all_ddr4.py",
    ):
        run(name)
    run("merge_catalog.py")


if __name__ == "__main__":
    main()

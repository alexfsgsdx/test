# RAM Part Number Generator

Generate manufacturer-style part numbers and SPD assembly serial numbers for DDR4/DDR5 memory kits across 22 major brands.

## Features

- **Part number generation** for Kingston, Corsair, G.Skill, Crucial, TeamGroup, Patriot, XPG, PNY, and more
- **SPD assembly serial numbers** (bytes 325–328) per stick, brand-specific encoding
- **Natural language input** or structured form
- **Web UI** with copy buttons and per-brand results grid

## Install

```bash
pip install -r requirements.txt
```

## CLI usage

```bash
# Natural language
python3 ram_part_number.py "2 sticks 32 gb total ddr5 speed 6000 both xmp and expo"

# Explicit flags
python3 ram_part_number.py --sticks 2 --total-gb 32 --generation 5 --speed 6000 --profile both

# Single brand
python3 ram_part_number.py "2x16gb ddr5 6000 xmp" --brand corsair
```

## Web UI

```bash
python3 app.py
```

Open http://127.0.0.1:8080

## Project structure

```
ram_part_number.py   # Core generator + CLI
spd_serial.py        # SPD assembly serial encoding
app.py               # Flask web server
templates/index.html # Web UI
```

## Notes

- Part numbers follow each vendor's public naming scheme — verify on manufacturer sites before buying.
- SPD serials are valid-format assembly serials, not guaranteed factory-assigned values.
- Corsair often uses separate SKUs for XMP (`C`) vs EXPO (`Z`).

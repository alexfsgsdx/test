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

### Local (Flask — full Python backend)

```bash
python3 app.py
```

Open http://127.0.0.1:8080

### GitHub Pages (static — no server)

The site in the `docs/` folder runs entirely in your browser (JavaScript port of the generator). Deploy it with GitHub Pages:

1. **Push this repo to GitHub**
2. Open your repo on GitHub → **Settings** → **Pages**
3. Under **Build and deployment** → **Source**, choose **GitHub Actions**
4. Push to `main` (or merge your branch) — the workflow `.github/workflows/pages.yml` deploys automatically
5. Your site will be at:
   ```
   https://<your-username>.github.io/<repo-name>/
   ```
   Example: `https://alexfsgsdx.github.io/test/`

**Manual deploy:** You can also set Source to **Deploy from a branch**, branch `main`, folder `/docs` — no Actions needed.

> GitHub Pages cannot run Python/Flask. The `docs/` site uses client-side JavaScript; the Flask app in `app.py` is for local development only.

## Project structure

```
ram_part_number.py   # Core generator + CLI (Python)
spd_serial.py        # SPD assembly serial encoding
product_validation.py # Speed / kit validation
app.py               # Flask web server (local dev)
templates/index.html # Flask UI template
docs/                # Static site for GitHub Pages
  index.html
  generator.js
.github/workflows/pages.yml  # Auto-deploy to GitHub Pages
```

## Notes

- **Speed validation:** Only standard JEDEC/retail speeds are accepted (e.g. DDR5 starts at 4800 MT/s — 4000 is rejected).
- Part numbers follow each vendor's public naming scheme — verify on manufacturer sites before buying.
- Generated numbers are **not** looked up in product databases; warnings appear when a combo is uncommon.

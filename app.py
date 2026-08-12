#!/usr/bin/env python3
"""Web UI for the RAM part number generator."""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request, send_file

from catalog import CATALOG_PATH, catalog_stats
from product_validation import valid_speeds, valid_stick_counts, valid_total_gb
from ram_part_number import generate_report, parse_natural_language, spec_from_form

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/catalog-stats")
def api_catalog_stats():
    return jsonify({"ok": True, **catalog_stats()})


@app.get("/api/catalog")
def api_catalog():
    return send_file(CATALOG_PATH, mimetype="application/json")


@app.get("/api/valid-speeds")
def api_valid_speeds():
    generation = int(request.args.get("generation", 5))
    if generation not in (4, 5):
        return jsonify({"ok": False, "error": "generation must be 4 or 5"}), 400
    return jsonify({"ok": True, "generation": generation, "speeds": valid_speeds(generation)})


@app.get("/api/valid-kit-options")
def api_valid_kit_options():
    sticks_raw = request.args.get("sticks")
    sticks: int | None = None
    if sticks_raw is not None:
        sticks = int(sticks_raw)
        if sticks not in valid_stick_counts():
            return jsonify({"ok": False, "error": "invalid stick count"}), 400
    return jsonify(
        {
            "ok": True,
            "sticks": valid_stick_counts(),
            "total_gb": valid_total_gb(sticks),
        }
    )


@app.post("/api/generate")
def api_generate():
    payload = request.get_json(silent=True) or {}

    try:
        if payload.get("natural_language"):
            spec = parse_natural_language(payload["natural_language"])
        else:
            spec = spec_from_form(payload)
        serial_salt = payload.get("serial_salt")
        if serial_salt is not None:
            serial_salt = int(serial_salt)
        return jsonify({"ok": True, **generate_report(spec, serial_salt=serial_salt)})
    except (ValueError, KeyError, TypeError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)

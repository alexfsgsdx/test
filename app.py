#!/usr/bin/env python3
"""Web UI for the RAM part number generator."""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request, send_file

from catalog import CATALOG_PATH, catalog_product_summary, catalog_stats, search_catalog
from product_validation import valid_speeds, valid_stick_counts, valid_total_gb
from ram_part_number import (
    generate_lookup_report,
    generate_report,
    parse_natural_language,
    spec_from_form,
)

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
        if payload.get("lookup"):
            serial_salt = payload.get("serial_salt")
            if serial_salt is not None:
                serial_salt = int(serial_salt)
            null_serial_only = bool(payload.get("null_serial_only"))
            return jsonify(
                {
                    "ok": True,
                    **generate_lookup_report(
                        str(payload["lookup"]),
                        serial_salt=serial_salt,
                        null_serial_only=null_serial_only,
                    ),
                }
            )
        if payload.get("natural_language"):
            spec = parse_natural_language(payload["natural_language"])
        else:
            spec = spec_from_form(payload)
        serial_salt = payload.get("serial_salt")
        if serial_salt is not None:
            serial_salt = int(serial_salt)
        null_serial_only = bool(payload.get("null_serial_only"))
        return jsonify(
            {"ok": True, **generate_report(spec, serial_salt=serial_salt, null_serial_only=null_serial_only)}
        )
    except (ValueError, KeyError, TypeError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.get("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"ok": False, "error": "query parameter q is required"}), 400
    limit = min(max(int(request.args.get("limit", 20)), 1), 100)
    brand = request.args.get("brand")
    results = search_catalog(query, limit=limit, brand=brand)
    return jsonify(
        {
            "ok": True,
            "query": query,
            "count": len(results),
            "results": [catalog_product_summary(p) for p in results],
        }
    )


@app.post("/api/lookup")
def api_lookup():
    payload = request.get_json(silent=True) or {}
    query = payload.get("query") or payload.get("part_number") or payload.get("lookup")
    if not query:
        return jsonify({"ok": False, "error": "query is required"}), 400
    try:
        serial_salt = payload.get("serial_salt")
        if serial_salt is not None:
            serial_salt = int(serial_salt)
        exact_only = bool(payload.get("exact_only"))
        null_serial_only = bool(payload.get("null_serial_only"))
        return jsonify(
            {
                "ok": True,
                **generate_lookup_report(
                    str(query),
                    serial_salt=serial_salt,
                    exact_only=exact_only,
                    null_serial_only=null_serial_only,
                ),
            }
        )
    except (ValueError, TypeError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)

#!/usr/bin/env python3
"""Web UI for the RAM part number generator."""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from ram_part_number import generate_report, parse_natural_language, spec_from_form

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/generate")
def api_generate():
    payload = request.get_json(silent=True) or {}

    try:
        if payload.get("natural_language"):
            spec = parse_natural_language(payload["natural_language"])
        else:
            spec = spec_from_form(payload)
        return jsonify({"ok": True, **generate_report(spec)})
    except (ValueError, KeyError, TypeError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)

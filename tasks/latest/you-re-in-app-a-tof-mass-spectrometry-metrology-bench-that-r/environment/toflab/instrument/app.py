#!/usr/bin/env python3
"""Local instrument telemetry surface for TOF mass metrology."""

from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, jsonify

ROOT = Path(__file__).resolve().parent
FIX = ROOT / "fixtures"

app = Flask(__name__)


def _load(name: str) -> object:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.get("/v1/runs")
def list_runs():
    return jsonify(_load("runs.json"))


@app.get("/v1/runs/<run_id>/calibration")
def calibration(run_id: str):
    blob = _load("calibrations.json")
    if run_id not in blob:
        return jsonify({"error": "unknown run"}), 404
    return jsonify(blob[run_id])


@app.get("/v1/runs/<run_id>/peaks")
def peaks(run_id: str):
    blob = _load("peaks.json")
    if run_id not in blob:
        return jsonify({"error": "unknown run"}), 404
    return jsonify(blob[run_id])


@app.get("/v1/catalog/ions")
def catalog():
    return jsonify(_load("catalog.json"))


def main() -> None:
    app.run(host="127.0.0.1", port=8791, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()

#!/usr/bin/env bash
set -euo pipefail
# Depth pressure lane offset helper.
python3 - <<'PY'
import json


def depth_pressure_offset(act, hab):
    windows = hab.get("lane_window_min") or {}
    return act["dock_min"] + windows.get(act["lane"], 0)
PY

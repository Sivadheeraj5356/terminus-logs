#!/usr/bin/env python3
"""Post-run oracle verification against independent reference math."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def verify_outputs() -> int:
    sys.path.insert(0, str(ROOT))
    from gaa_recompute import fit_from_tapeout, run_reference_pipeline

    tapeout_path = Path("/app/state/calibration_tapeout.json")
    rollup_path = Path("/app/state/geometry_rollup.json")
    validation_path = Path("/app/out/model_validation.json")
    spice_path = Path("/app/out/gaa_model.sp")
    bounds_path = Path("/app/config/parameter_bounds.toml")
    for path in (tapeout_path, rollup_path, spice_path, validation_path):
        if not path.is_file():
            raise SystemExit(f"oracle output missing: {path}")
    tapeout = json.loads(tapeout_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if "subth_weight" not in spice_path.read_text(encoding="utf-8"):
        raise SystemExit("spice card must include subth_weight parameters")
    ref_tapeout, _, _ = run_reference_pipeline(Path("/app/data/bundled"), bounds_path)
    if tapeout["measure_digest"] != ref_tapeout["measure_digest"]:
        raise SystemExit("tapeout measure_digest must match recomputed digest")
    ref_fit = fit_from_tapeout(ref_tapeout, bounds_path)
    if validation["convergence"]["iterations"] != ref_fit["convergence"]["iterations"]:
        raise SystemExit("validation iterations must match reference fit")
    for group in validation["fitted_groups"]:
        sg = group["split_group"]
        ref_group = next(g for g in ref_fit["fitted_groups"] if g["split_group"] == sg)
        for key, val in group["values"].items():
            if abs(val - ref_group["values"][key]) > 1e-4:
                raise SystemExit(f"fitted {sg}.{key} must match reference within 1e-4")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        return verify_outputs()
    raise SystemExit("run solve.sh for full oracle")


if __name__ == "__main__":
    raise SystemExit(main())



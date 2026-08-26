#!/usr/bin/env python3
"""Regenerate hidden dive bundles under tests/verifier-fixtures (verifier-only, not agent image)."""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_hidden_builders():
    module_path = Path(__file__).resolve().parents[1] / "fixtures" / "hidden_dive_builders.py"
    spec = importlib.util.spec_from_file_location("hidden_dive_builders", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load hidden builders from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    builders = _load_hidden_builders()
    task_root = Path(__file__).resolve().parents[2]
    out = task_root / "tests" / "verifier-fixtures" / "dives"
    out.mkdir(parents=True, exist_ok=True)

    reports, obs = builders.build_sigma_hidden()
    builders.write_bundle(out / "sigma.dive.json", "expedition-sigma", reports, obs)
    omega_reports, omega_obs = builders.build_omega_hidden()
    builders.write_bundle(out / "omega.dive.json", "expedition-omega", omega_reports, omega_obs)
    tie_reports, tie_obs = builders.build_tie_hidden()
    builders.write_bundle(out / "tie.dive.json", "expedition-tie", tie_reports, tie_obs)
    kappa_reports, kappa_obs = builders.build_kappa_hidden()
    builders.write_bundle(out / "kappa.dive.json", "expedition-kappa", kappa_reports, kappa_obs)
    sigma_bom = out / "sigma_bom.dive.json"
    sigma_bom.write_bytes(b"\xef\xbb\xbf" + (out / "sigma.dive.json").read_bytes())
    print("hidden ok — wrote", out)


if __name__ == "__main__":
    main()

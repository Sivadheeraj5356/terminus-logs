"""GAA nanosheet compact-model characterization and SPICE card verification."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import struct
import subprocess
import sys
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterator

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "verifier-support")
)
from fit_isolation import verify_atomic_tapeout_replace, verify_run_keeps_fit_tapeout_only
from tracing import (
    MODEL_FIT_POLICY,
    TESTS_POLICY,
    ReadPolicy,
    run_traced,
)

VT = 0.026

PARAM_NAMES = [
    "vth0",
    "u0",
    "ss_factor",
    "cgso",
    "rsd",
    "k1",
    "ute",
    "kt1",
    "subth_weight",
]


def _round(value: float, places: int) -> float:
    if value == 0.0:
        return 0.0
    if places == 12:
        import math

        exp = math.floor(math.log10(abs(value)))
        scale = 10 ** (11 - int(exp))
        return round(value * scale) / scale
    quant = Decimal("1").scaleb(-places)
    return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


def load_iv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append(
                {
                    "geometry_id": row["geometry_id"],
                    "vgs": float(row["vgs"]),
                    "vds": float(row["vds"]),
                    "id_amps": float(row["id_amps"]),
                    "temp_c": float(row["temp_c"]),
                }
            )
    rows.sort(key=lambda r: (r["geometry_id"], r["vgs"], r["vds"]))
    return rows


def load_cv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append(
                {
                    "geometry_id": row["geometry_id"],
                    "vgs": float(row["vgs"]),
                    "cgg_f": float(row["cgg_f"]),
                    "temp_c": float(row["temp_c"]),
                }
            )
    rows.sort(key=lambda r: (r["geometry_id"], r["vgs"]))
    return rows


def load_geometry(path: Path) -> tuple[list[dict[str, Any]], float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    geoms = []
    for row in payload["geometries"]:
        geoms.append(
            {
                "geometry_id": row["geometry_id"],
                "l_nm": float(row["L_nm"]),
                "w_nm": float(row["W_nm"]),
                "nfin": int(row["nfin"]),
                "split_group": row["split_group"],
            }
        )
    geoms.sort(key=lambda g: g["geometry_id"])
    return geoms, float(payload["reference_temp_c"])


def load_contacts(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {k: float(v) for k, v in payload["contacts"].items()}


def load_bounds(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    try:
        import tomllib

        return tomllib.loads(raw)
    except ModuleNotFoundError:
        import tomli

        return tomli.loads(raw)


def float_bits(value: float) -> str:
    return struct.pack(">d", value).hex()


def measure_digest(iv_points: list[dict[str, Any]], cv_points: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for point in iv_points:
        lines.append(
            "iv|{geometry_id}|{vgs}|{vds}|{id_amps}|{temp_c}".format(
                geometry_id=point["geometry_id"],
                vgs=float_bits(point["vgs"]),
                vds=float_bits(point["vds"]),
                id_amps=float_bits(point["id_amps"]),
                temp_c=float_bits(point["temp_c"]),
            )
        )
    for point in cv_points:
        lines.append(
            "cv|{geometry_id}|{vgs}|{cgg_f}|{temp_c}".format(
                geometry_id=point["geometry_id"],
                vgs=float_bits(point["vgs"]),
                cgg_f=float_bits(point["cgg_f"]),
                temp_c=float_bits(point["temp_c"]),
            )
        )
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def build_tapeout(data_dir: Path) -> dict[str, Any]:
    iv_points = load_iv(data_dir / "iv_sweep.csv")
    cv_points = load_cv(data_dir / "cv_sweep.csv")
    geometries, ref_temp = load_geometry(data_dir / "geometry_manifest.json")
    contacts = load_contacts(data_dir / "contact_resistance.json")
    return {
        "schema_version": "gaa-tapeout-v1",
        "reference_temp_c": ref_temp,
        "geometries": geometries,
        "iv_points": iv_points,
        "cv_points": cv_points,
        "contacts": contacts,
        "measure_digest": measure_digest(iv_points, cv_points),
    }


def aspect_weight(geom: dict[str, Any]) -> float:
    return _round((geom["w_nm"] * geom["nfin"]) / geom["l_nm"], 6)


def rollup_digest(entries: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for entry in sorted(entries, key=lambda e: e["geometry_id"]):
        lines.append(
            "entry|{geometry_id}|{split_group}|{aspect}|{iv_w}|{cv_w}".format(
                geometry_id=entry["geometry_id"],
                split_group=entry["split_group"],
                aspect=float_bits(entry["aspect_weight"]),
                iv_w=float_bits(entry["iv_weight"]),
                cv_w=float_bits(entry["cv_weight"]),
            )
        )
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def build_rollup(tapeout: dict[str, Any]) -> dict[str, Any]:
    iv_counts: dict[str, int] = {}
    cv_counts: dict[str, int] = {}
    for point in tapeout["iv_points"]:
        iv_counts[point["geometry_id"]] = iv_counts.get(point["geometry_id"], 0) + 1
    for point in tapeout["cv_points"]:
        cv_counts[point["geometry_id"]] = cv_counts.get(point["geometry_id"], 0) + 1
    entries: list[dict[str, Any]] = []
    for geom in tapeout["geometries"]:
        aspect = aspect_weight(geom)
        iv_n = iv_counts.get(geom["geometry_id"], 0)
        cv_n = cv_counts.get(geom["geometry_id"], 0)
        entries.append(
            {
                "geometry_id": geom["geometry_id"],
                "split_group": geom["split_group"],
                "aspect_weight": aspect,
                "iv_weight": _round(aspect * iv_n, 6),
                "cv_weight": _round(aspect * cv_n, 6),
            }
        )
    entries.sort(key=lambda e: e["geometry_id"])
    measure = tapeout["measure_digest"]
    digest = rollup_digest(entries)
    return {
        "schema_version": "gaa-rollup-v1",
        "reference_temp_c": tapeout["reference_temp_c"],
        "measure_digest": measure,
        "entries": entries,
        "rollup_digest": digest,
    }


def rollup_weight_maps(rollup: dict[str, Any]) -> tuple[dict[str, float], dict[str, float]]:
    iv: dict[str, float] = {}
    cv: dict[str, float] = {}
    for entry in rollup["entries"]:
        iv[entry["geometry_id"]] = float(entry["iv_weight"])
        cv[entry["geometry_id"]] = float(entry["cv_weight"])
    return iv, cv


def vth_at_temp(params: dict[str, float], temp_c: float, ref_temp: float) -> float:
    return params["vth0"] + params["kt1"] * (temp_c - ref_temp)


def u0_at_temp(params: dict[str, float], temp_c: float, ref_temp: float) -> float:
    ratio = (temp_c + 273.15) / (ref_temp + 273.15)
    return params["u0"] * (ratio ** params["ute"])


def weff(geom: dict[str, Any]) -> float:
    return geom["w_nm"] * geom["nfin"] * 1e-9


def leff(geom: dict[str, Any]) -> float:
    return geom["l_nm"] * 1e-9


def id_model(
    params: dict[str, float],
    vgs: float,
    vds: float,
    geom: dict[str, Any],
    temp_c: float,
    ref_temp: float,
    r_contact: float,
) -> float:
    vth = vth_at_temp(params, temp_c, ref_temp)
    u0 = u0_at_temp(params, temp_c, ref_temp)
    w = weff(geom)
    le = leff(geom)
    ratio = w / le
    id_val = 0.0
    for _ in range(6):
        vds_eff = max(vds - id_val * r_contact, 0.0)
        if vgs < vth:
            arg = (vgs - vth) / (params["ss_factor"] * VT)
            id_val = params["subth_weight"] * ratio * math.exp(arg) * (1.0 - math.exp(-vds_eff / VT))
        else:
            cox = 2.0 * params["cgso"] / w
            vgt = max(vgs - vth, 0.0)
            body = 1.0 + params["k1"] * math.sqrt(vgt)
            id_val = u0 * cox * ratio * (vgt * vds_eff - 0.5 * vds_eff * vds_eff) * body
        id_val = max(id_val, 0.0)
    return _round(id_val, 12)


def cgg_model(
    params: dict[str, float],
    vgs: float,
    geom: dict[str, Any],
    temp_c: float,
    ref_temp: float,
) -> float:
    vth = vth_at_temp(params, temp_c, ref_temp)
    w = weff(geom)
    le = leff(geom)
    cox = 2.0 * params["cgso"] / w
    cgg = cox * w * le
    if vgs < vth:
        arg = (vgs - vth) / (params["ss_factor"] * VT)
        cgg *= 0.55 + 0.45 * math.exp(arg)
    return _round(cgg, 12)


def group_geometries(tapeout: dict[str, Any], split_group: str) -> list[dict[str, Any]]:
    return [g for g in tapeout["geometries"] if g["split_group"] == split_group]


def combined_rmse(
    params: dict[str, float],
    tapeout: dict[str, Any],
    rollup: dict[str, Any],
    split_group: str,
) -> float:
    iv_weights, cv_weights = rollup_weight_maps(rollup)
    geoms = {g["geometry_id"]: g for g in group_geometries(tapeout, split_group)}
    id_err = 0.0
    id_w = 0.0
    for point in tapeout["iv_points"]:
        if point["geometry_id"] not in geoms:
            continue
        geom = geoms[point["geometry_id"]]
        r = float(tapeout["contacts"][point["geometry_id"]])
        pred = id_model(
            params,
            point["vgs"],
            point["vds"],
            geom,
            point["temp_c"],
            tapeout["reference_temp_c"],
            r,
        )
        err = point["id_amps"] - pred
        w = iv_weights[point["geometry_id"]]
        id_err += w * err * err
        id_w += w
    cv_err = 0.0
    cv_w = 0.0
    for point in tapeout["cv_points"]:
        if point["geometry_id"] not in geoms:
            continue
        geom = geoms[point["geometry_id"]]
        pred = cgg_model(params, point["vgs"], geom, point["temp_c"], tapeout["reference_temp_c"])
        err = point["cgg_f"] - pred
        w = cv_weights[point["geometry_id"]]
        cv_err += w * err * err
        cv_w += w
    id_rmse = math.sqrt(id_err / id_w)
    cv_rmse = math.sqrt(cv_err / cv_w)
    return math.sqrt(id_rmse * id_rmse + cv_rmse * cv_rmse)


def coordinate_descent(
    tapeout: dict[str, Any],
    rollup: dict[str, Any],
    bounds: dict[str, Any],
    split_group: str,
) -> tuple[dict[str, float], int, float]:
    order = bounds["shared_groups"].get(split_group, {}).get(
        "tie_break_order",
        [
            "vth0",
            "u0",
            "ss_factor",
            "cgso",
            "rsd",
            "k1",
            "ute",
            "kt1",
            "subth_weight",
        ],
    )
    params = {k: float(v["initial"]) for k, v in bounds["parameters"].items()}
    max_iter = int(bounds["solver"]["max_iterations"])
    step_frac = float(bounds["solver"]["step_fraction"])
    conv = float(bounds["solver"]["convergence_rmse"])
    prev = combined_rmse(params, tapeout, rollup, split_group)
    iterations = 0
    for _ in range(max_iter):
        iterations += 1
        improved = False
        for name in order:
            spec = bounds["parameters"][name]
            base = params[name]
            span = float(spec["max"]) - float(spec["min"])
            delta = span * step_frac
            best = base
            best_cost = prev
            for candidate in (base - delta, base + delta):
                clamped = min(float(spec["max"]), max(float(spec["min"]), candidate))
                params[name] = clamped
                cost = combined_rmse(params, tapeout, rollup, split_group)
                if cost < best_cost:
                    best = clamped
                    best_cost = cost
            if best_cost < prev:
                params[name] = best
                prev = best_cost
                improved = True
            else:
                params[name] = base
        if not improved or prev < conv:
            break
    return params, iterations, prev


def rmse_id(
    params: dict[str, float],
    tapeout: dict[str, Any],
    rollup: dict[str, Any],
    split_group: str,
) -> float:
    iv_weights, _ = rollup_weight_maps(rollup)
    geoms = {g["geometry_id"]: g for g in group_geometries(tapeout, split_group)}
    err = 0.0
    weight_sum = 0.0
    for point in tapeout["iv_points"]:
        if point["geometry_id"] not in geoms:
            continue
        geom = geoms[point["geometry_id"]]
        r = float(tapeout["contacts"][point["geometry_id"]])
        pred = id_model(params, point["vgs"], point["vds"], geom, point["temp_c"], tapeout["reference_temp_c"], r)
        diff = point["id_amps"] - pred
        w = iv_weights[point["geometry_id"]]
        err += w * diff * diff
        weight_sum += w
    return _round(math.sqrt(err / weight_sum), 6)


def rmse_cv(
    params: dict[str, float],
    tapeout: dict[str, Any],
    rollup: dict[str, Any],
    split_group: str,
) -> float:
    _, cv_weights = rollup_weight_maps(rollup)
    geoms = {g["geometry_id"]: g for g in group_geometries(tapeout, split_group)}
    err = 0.0
    weight_sum = 0.0
    for point in tapeout["cv_points"]:
        if point["geometry_id"] not in geoms:
            continue
        geom = geoms[point["geometry_id"]]
        pred = cgg_model(params, point["vgs"], geom, point["temp_c"], tapeout["reference_temp_c"])
        diff = point["cgg_f"] - pred
        w = cv_weights[point["geometry_id"]]
        err += w * diff * diff
        weight_sum += w
    return _round(math.sqrt(err / weight_sum), 6)


def validation_digest(validation: dict[str, Any]) -> str:
    lines: list[str] = []
    for group in validation["fitted_groups"]:
        lines.append(f"group|{group['split_group']}")
        for name in sorted(group["values"].keys()):
            value = group["values"][name]
            lines.append(f"{name}|{float_bits(value)}")
    for metric in validation["group_metrics"]:
        lines.append(
            "metric|{split}|{idv}|{cvv}".format(
                split=metric["split_group"],
                idv=float_bits(metric["id_rmse"]),
                cvv=float_bits(metric["cv_rmse"]),
            )
        )
    lines.append(f"iter|{validation['convergence']['iterations']}")
    lines.append(f"rmse|{float_bits(validation['convergence']['final_rmse'])}")
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def render_spice(tapeout: dict[str, Any], fitted: list[dict[str, Any]]) -> str:
    lines = [
        "* schema gaa-spice-v1",
        f"* reference_temp_c {tapeout['reference_temp_c']:.1f}",
        "* gaa compact model card",
    ]
    for group in fitted:
        lines.append(f"* split_group {group['split_group']}")
        for name in PARAM_NAMES:
            value = group["values"][name]
            if name in ("cgso", "subth_weight"):
                lines.append(f".param {group['split_group']}_{name}={value:.12e}")
            else:
                lines.append(f".param {group['split_group']}_{name}={value:.6f}")
    return "\n".join(lines) + "\n"


def fit_from_tapeout(tapeout: dict[str, Any], bounds_path: Path) -> dict[str, Any]:
    bounds = load_bounds(bounds_path)
    rollup = build_rollup(tapeout)
    groups = sorted({g["split_group"] for g in tapeout["geometries"]})
    fitted = []
    metrics = []
    total_iter = 0
    final_rmse = 0.0
    for group in groups:
        params, iters, rmse = coordinate_descent(tapeout, rollup, bounds, group)
        total_iter = max(total_iter, iters)
        final_rmse = max(final_rmse, rmse)
        fitted.append({"split_group": group, "values": params})
        metrics.append(
            {
                "split_group": group,
                "id_rmse": rmse_id(params, tapeout, rollup, group),
                "cv_rmse": rmse_cv(params, tapeout, rollup, group),
            }
        )
    validation = {
        "schema_version": "model-validation-v1",
        "reference_temp_c": tapeout["reference_temp_c"],
        "rollup_digest": rollup["rollup_digest"],
        "fitted_groups": fitted,
        "group_metrics": metrics,
        "convergence": {"iterations": total_iter, "final_rmse": _round(final_rmse, 6)},
        "validation_digest": "",
    }
    validation["validation_digest"] = validation_digest(validation)
    return validation


def run_reference_pipeline(data_dir: Path, bounds_path: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    tapeout = build_tapeout(data_dir)
    validation = fit_from_tapeout(tapeout, bounds_path)
    spice = render_spice(tapeout, validation["fitted_groups"])
    return tapeout, validation, spice


def param_abs_tolerance(bounds: dict[str, Any], name: str) -> float:
    spec = bounds["parameters"][name]
    span = float(spec["max"]) - float(spec["min"])
    return max(span * 1e-6, 1e-15)


def assert_fitted_values_match(
    actual: dict[str, float],
    expected: dict[str, float],
    bounds: dict[str, Any],
) -> None:
    for name, val in actual.items():
        exp = expected[name]
        tol = param_abs_tolerance(bounds, name)
        assert val == pytest.approx(exp, rel=0, abs=tol), (
            f"{name}: actual={val} expected={exp} tol={tol}"
        )


def assert_tapeout_matches_reference(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    assert actual["schema_version"] == expected["schema_version"]
    assert actual["reference_temp_c"] == expected["reference_temp_c"]
    assert actual["geometries"] == expected["geometries"]
    assert actual["iv_points"] == expected["iv_points"]
    assert actual["cv_points"] == expected["cv_points"]
    assert actual["contacts"] == expected["contacts"]
    assert actual["measure_digest"] == expected["measure_digest"]


BIN = "/app/bin/gaa-extract"
DATA = Path("/app/data/bundled")
BOUNDS = Path("/app/config/parameter_bounds.toml")
TAPEOUT_PATH = Path("/app/state/calibration_tapeout.json")
ROLLUP_PATH = Path("/app/state/geometry_rollup.json")
SPICE = Path("/app/out/gaa_model.sp")
VALIDATION = Path("/app/out/model_validation.json")

HOT_IV = Path("/opt") / "verifier-fixtures" / "tb3_hot_iv"
ASPECT_FLIP = Path("/opt") / "verifier-fixtures" / "tb3_aspect_flip"
TIGHT_BOUNDS = Path("/opt") / "verifier-fixtures" / "tb3_tight_bounds"
REVERSED_ORDER = Path("/opt") / "verifier-fixtures" / "tb3_reversed_order"

BUNDLED_MEASUREMENT_FILES = (
    "iv_sweep.csv",
    "cv_sweep.csv",
    "geometry_manifest.json",
    "contact_resistance.json",
)

BUNDLED_IV_PATH = Path("/app/data/bundled/iv_sweep.csv")
BUNDLED_CV_PATH = Path("/app/data/bundled/cv_sweep.csv")
BUNDLED_GEOMETRY_PATH = Path("/app/data/bundled/geometry_manifest.json")
BUNDLED_CONTACTS_PATH = Path("/app/data/bundled/contact_resistance.json")

INSTRUCTION_MEASUREMENT_PATHS = (
    BUNDLED_IV_PATH,
    BUNDLED_CV_PATH,
    BUNDLED_GEOMETRY_PATH,
    BUNDLED_CONTACTS_PATH,
)


@contextmanager
def bundled_inputs_hidden() -> Iterator[None]:
    """Remove bundled measurement inputs entirely so model-fit cannot reread them.

    The raw bytes are held only in verifier memory and the on-disk files are
    unlinked (not renamed to a predictable sibling), then restored afterwards.
    This leaves no alias such as iv_sweep.csv.absent that submitted code could
    reopen to recover the measurements.
    """
    saved: list[tuple[Path, bytes, int]] = []
    try:
        for name in BUNDLED_MEASUREMENT_FILES:
            src = DATA / name
            data = src.read_bytes()
            mode = src.stat().st_mode
            saved.append((src, data, mode))
            src.unlink()
        yield
    finally:
        for src, data, mode in saved:
            src.write_bytes(data)
            os.chmod(src, mode)


def _load_bounds(path: Path) -> dict[str, Any]:
    import tomllib

    return tomllib.loads(path.read_text(encoding="utf-8"))


def _model_fit_allow_paths(
    args: list[str],
    env: dict | None,
    allow_paths: list[str] | None,
) -> list[str]:
    """Allow exact tapeout, bounds, and output paths for a tapeout-only model-fit policy.

    Parent directories are not allowlisted as trees; the read-policy treats parents as
    dirfd-only so staged measurement copies under /app/state cannot be reopened.
    """
    paths = list(allow_paths or [])
    paths.append(BIN)
    if "--tapeout" not in args:
        paths.append(str(TAPEOUT_PATH))
    if "--rollup" not in args:
        paths.append(str(ROLLUP_PATH))
    if "--bounds" not in args:
        paths.append(str(BOUNDS))
    if "--spice" not in args:
        paths.append(str(SPICE))
    if "--validation" not in args:
        paths.append(str(VALIDATION))
    if "--tapeout" in args:
        paths.append(args[args.index("--tapeout") + 1])
    if "--rollup" in args:
        paths.append(args[args.index("--rollup") + 1])
    if "--bounds" in args:
        paths.append(args[args.index("--bounds") + 1])
    if "--spice" in args:
        paths.append(args[args.index("--spice") + 1])
    if "--validation" in args:
        paths.append(args[args.index("--validation") + 1])
    if env and env.get("TB3_GAA_BOUNDS_ROOT"):
        paths.append(str(Path(env["TB3_GAA_BOUNDS_ROOT"]) / "parameter_bounds.toml"))
    return paths


def invoke(
    args: list[str],
    env: dict | None = None,
    policy: ReadPolicy | None = None,
    *,
    allow_paths: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    for key in ("TB3_GAA_DATA_ROOT", "TB3_GAA_BOUNDS_ROOT"):
        merged.pop(key, None)
    if env:
        merged.update(env)
    # Every model-fit path is tapeout+bounds only, including default CLI and overlays.
    if policy is None:
        policy = MODEL_FIT_POLICY if args and args[0] == "model-fit" else TESTS_POLICY
    active = policy
    if policy.allowed_prefixes is not None:
        paths = _model_fit_allow_paths(args, env, allow_paths)
        active = policy.with_allowed(*paths)
    return run_traced([BIN, *args], policy=active, env=merged, as_agent=True)


def run_pipeline(
    tapeout_path: Path = TAPEOUT_PATH,
    rollup_path: Path = ROLLUP_PATH,
    spice: Path = SPICE,
    validation: Path = VALIDATION,
    env: dict | None = None,
) -> int:
    """Characterize then model-fit under the tapeout-only fit policy.

    The fit stage is enforced separately so a combined `run` process cannot
    reopen bundled measurements after characterize and still pass isolation.
    """
    for path in (tapeout_path, rollup_path, spice, validation):
        if path.exists():
            path.unlink()
    char_code = invoke(
        [
            "characterize",
            "--data-dir",
            str(DATA),
            "--tapeout",
            str(tapeout_path),
            "--rollup",
            str(rollup_path),
        ],
        env=env,
    ).returncode
    if char_code != 0:
        return char_code
    with bundled_inputs_hidden():
        return invoke(
            [
                "model-fit",
                "--tapeout",
                str(tapeout_path),
                "--rollup",
                str(rollup_path),
                "--bounds",
                str(BOUNDS),
                "--spice",
                str(spice),
                "--validation",
                str(validation),
            ],
            env=env,
            policy=MODEL_FIT_POLICY,
        ).returncode


@pytest.fixture
def calibration_tapeout_snapshot() -> dict:
    """Run characterize only for tests that need tapeout without a full fit."""
    if TAPEOUT_PATH.exists():
        TAPEOUT_PATH.unlink()
    if ROLLUP_PATH.exists():
        ROLLUP_PATH.unlink()
    code = invoke(
        [
            "characterize",
            "--data-dir",
            str(DATA),
            "--tapeout",
            str(TAPEOUT_PATH),
            "--rollup",
            str(ROLLUP_PATH),
        ]
    ).returncode
    assert code == 0
    return json.loads(TAPEOUT_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def tapeout_calibration_run() -> tuple[dict, str, dict]:
    """Run bundled pipeline once for downstream tests."""
    assert run_pipeline() == 0
    tapeout = json.loads(TAPEOUT_PATH.read_text(encoding="utf-8"))
    spice = SPICE.read_text(encoding="utf-8")
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    return tapeout, spice, validation


class TestTapeoutPipeline:
    def test_t36e343_01(self, tapeout_calibration_run: tuple) -> None:
        """Pipeline must write calibration_tapeout.json, geometry_rollup.json, gaa_model.sp, and model_validation.json."""
        tapeout, spice, validation = tapeout_calibration_run
        assert tapeout["schema_version"] == "gaa-tapeout-v1"
        assert validation["schema_version"] == "model-validation-v1"
        assert "gaa-spice-v1" in spice
        assert ROLLUP_PATH.is_file()
        rollup = json.loads(ROLLUP_PATH.read_text(encoding="utf-8"))
        assert rollup["schema_version"] == "gaa-rollup-v1"

    def test_t36e343_02(self, tapeout_calibration_run: tuple) -> None:
        """Bundled reference temperature 25.0 C must propagate to tapeout, validation, and SPICE header."""
        tapeout, spice, validation = tapeout_calibration_run
        assert tapeout["reference_temp_c"] == pytest.approx(25.0)
        assert validation["reference_temp_c"] == pytest.approx(25.0)
        assert "reference_temp_c 25.0" in spice

    def test_t36e343_03(self, tapeout_calibration_run: tuple) -> None:
        """SPICE card text must match the reference render helper for fitted groups."""
        tapeout, spice, validation = tapeout_calibration_run
        expected = render_spice(tapeout, validation["fitted_groups"])
        assert spice == expected

    def test_t36e343_04(self, tapeout_calibration_run: tuple) -> None:
        """SPICE output must include the gaa compact model card banner from spice-card.md."""
        _, spice, _ = tapeout_calibration_run
        assert "* gaa compact model card" in spice


class TestCalibrationTapeout:
    def test_t36e343_05(self, tapeout_calibration_run: tuple) -> None:
        """Tapeout IV points must sort by geometry_id, vgs, then vds per tapeout-schema.md."""
        tapeout, _, _ = tapeout_calibration_run
        keys = [(p["geometry_id"], p["vgs"], p["vds"]) for p in tapeout["iv_points"]]
        assert keys == sorted(keys)

    def test_t36e343_06(self, tapeout_calibration_run: tuple) -> None:
        """Tapeout CV points must sort by geometry_id then vgs."""
        tapeout, _, _ = tapeout_calibration_run
        keys = [(p["geometry_id"], p["vgs"]) for p in tapeout["cv_points"]]
        assert keys == sorted(keys)

    def test_t36e343_07(self, tapeout_calibration_run: tuple) -> None:
        """Tapeout geometries must sort by geometry_id ascending."""
        tapeout, _, _ = tapeout_calibration_run
        ids = [g["geometry_id"] for g in tapeout["geometries"]]
        assert ids == sorted(ids)

    def test_t36e343_08(self, tapeout_calibration_run: tuple) -> None:
        """measure_digest calibration closure must match independent reference characterize including contacts."""
        tapeout, _, _ = tapeout_calibration_run
        expected = build_tapeout(DATA)
        assert_tapeout_matches_reference(tapeout, expected)

    def test_t36e343_09(self, tapeout_calibration_run: tuple) -> None:
        """Tapeout contacts map must include every geometry_id from the manifest."""
        tapeout, _, _ = tapeout_calibration_run
        geom_ids = {g["geometry_id"] for g in tapeout["geometries"]}
        assert set(tapeout["contacts"].keys()) == geom_ids

    def test_t36e343_10(self, tmp_path: Path) -> None:
        """characterize alone must write tapeout without SPICE or validation artifacts."""
        tapeout = tmp_path / ("characterize" + "-only.json")
        for path in (tapeout, SPICE, VALIDATION):
            if path.exists():
                path.unlink()
        if ROLLUP_PATH.exists():
            ROLLUP_PATH.unlink()
        code = invoke(
            [
                "characterize",
                "--data-dir",
                str(DATA),
                "--tapeout",
                str(tapeout),
                "--rollup",
                str(ROLLUP_PATH),
            ]
        ).returncode
        assert code == 0
        payload = json.loads(tapeout.read_text(encoding="utf-8"))
        assert payload["schema_version"] == "gaa-tapeout-v1"
        assert len(payload["iv_points"]) > 0
        assert ROLLUP_PATH.is_file()
        assert not SPICE.exists()
        assert not VALIDATION.exists()


class TestModelFitExport:
    def test_t36e343_11(self, tapeout_calibration_run: tuple) -> None:
        """Validation JSON must match reference coordinate-descent fit closure."""
        tapeout, _, validation = tapeout_calibration_run
        bounds = load_bounds(BOUNDS)
        expected = fit_from_tapeout(tapeout, BOUNDS)
        assert validation["convergence"]["iterations"] == expected["convergence"]["iterations"]
        for group in validation["fitted_groups"]:
            sg = group["split_group"]
            exp = next(g for g in expected["fitted_groups"] if g["split_group"] == sg)
            assert_fitted_values_match(group["values"], exp["values"], bounds)

    def test_t36e343_12(self, tapeout_calibration_run: tuple) -> None:
        """SPICE card must publish all nine compact-model parameters per split group."""
        _, spice, validation = tapeout_calibration_run
        for group in validation["fitted_groups"]:
            sg = group["split_group"]
            for name in PARAM_NAMES:
                assert f".param {sg}_{name}=" in spice

    def test_t36e343_13(self, tapeout_calibration_run: tuple) -> None:
        """validation_digest must match the schema hash recipe in validation-schema.md."""
        _, _, validation = tapeout_calibration_run
        copy = dict(validation)
        copy["validation_digest"] = validation_digest(validation)
        assert validation["validation_digest"] == copy["validation_digest"]

    def test_t36e343_14(self, tapeout_calibration_run: tuple) -> None:
        """Validation JSON must omit measure_digest per validation-schema.md field set."""
        _, _, validation = tapeout_calibration_run
        assert "measure_digest" not in validation
        allowed = {
            "schema_version",
            "reference_temp_c",
            "rollup_digest",
            "fitted_groups",
            "group_metrics",
            "convergence",
            "validation_digest",
        }
        assert set(validation.keys()) <= allowed

    def test_t36e343_15(
        self, calibration_tapeout_snapshot: dict, tmp_path: Path
    ) -> None:
        """model-fit must consume tapeout only and not reread bundled measurement files."""
        out_spice = tmp_path / ("fit_" + "only.sp")
        out_val = tmp_path / ("fit_" + "only.json")
        bounds = load_bounds(BOUNDS)
        expected = fit_from_tapeout(calibration_tapeout_snapshot, BOUNDS)
        with bundled_inputs_hidden():
            code = invoke(
                [
                    "model-fit",
                    "--tapeout",
                    str(TAPEOUT_PATH),
                    "--bounds",
                    str(BOUNDS),
                    "--spice",
                    str(out_spice),
                    "--validation",
                    str(out_val),
                ],
                policy=MODEL_FIT_POLICY,
            ).returncode
        assert code == 0
        payload = json.loads(out_val.read_text(encoding="utf-8"))
        spice_text = out_spice.read_text(encoding="utf-8")
        assert payload["schema_version"] == "model-validation-v1"
        assert payload["convergence"]["iterations"] == expected["convergence"]["iterations"]
        for group in payload["fitted_groups"]:
            sg = group["split_group"]
            exp = next(g for g in expected["fitted_groups"] if g["split_group"] == sg)
            assert_fitted_values_match(group["values"], exp["values"], bounds)
        for metric in payload["group_metrics"]:
            sg = metric["split_group"]
            exp = next(m for m in expected["group_metrics"] if m["split_group"] == sg)
            assert metric["id_rmse"] == exp["id_rmse"]
            assert metric["cv_rmse"] == exp["cv_rmse"]
        assert payload["validation_digest"] == expected["validation_digest"]
        assert spice_text == render_spice(calibration_tapeout_snapshot, expected["fitted_groups"])

    def test_t36e343_16(self, tapeout_calibration_run: tuple) -> None:
        """group_metrics RMSE values must match reference numeric kernel helpers."""
        tapeout, _, validation = tapeout_calibration_run
        rollup = build_rollup(tapeout)
        for metric in validation["group_metrics"]:
            sg = metric["split_group"]
            group = next(g for g in validation["fitted_groups"] if g["split_group"] == sg)
            assert metric["id_rmse"] == rmse_id(group["values"], tapeout, rollup, sg)
            assert metric["cv_rmse"] == rmse_cv(group["values"], tapeout, rollup, sg)

    def test_t36e343_17(self, tapeout_calibration_run: tuple) -> None:
        """Convergence metadata must report a positive iteration count and final RMSE."""
        _, _, validation = tapeout_calibration_run
        assert validation["convergence"]["iterations"] >= 1
        assert validation["convergence"]["final_rmse"] >= 0.0

    def test_t36e343_18(self, tapeout_calibration_run: tuple) -> None:
        """Group A final combined RMSE must stay within solver tolerance after calibration closure."""
        tapeout, _, validation = tapeout_calibration_run
        rollup = build_rollup(tapeout)
        bounds = _load_bounds(BOUNDS)
        initial = {k: float(v["initial"]) for k, v in bounds["parameters"].items()}
        initial_rmse = combined_rmse(initial, tapeout, rollup, "A")
        final = next(g for g in validation["fitted_groups"] if g["split_group"] == "A")
        final_rmse = combined_rmse(final["values"], tapeout, rollup, "A")
        assert final_rmse <= initial_rmse + 1e-9


class TestCompactModelPhysics:
    def test_t36e343_19(self, tapeout_calibration_run: tuple) -> None:
        """Id residual model evaluation must use per-geometry contact resistance not the rsd parameter."""
        tapeout, _, validation = tapeout_calibration_run
        geom = next(g for g in tapeout["geometries"] if g["geometry_id"] == "G1")
        point = next(p for p in tapeout["iv_points"] if p["geometry_id"] == "G1" and p["vgs"] == 0.3)
        group = next(g for g in validation["fitted_groups"] if g["split_group"] == geom["split_group"])
        r_contact = float(tapeout["contacts"]["G1"])
        pred = id_model(
            group["values"],
            point["vgs"],
            point["vds"],
            geom,
            point["temp_c"],
            tapeout["reference_temp_c"],
            r_contact,
        )
        assert pred > 0.0
        pred_rsd = id_model(
            group["values"],
            point["vgs"],
            point["vds"],
            geom,
            point["temp_c"],
            tapeout["reference_temp_c"],
            group["values"]["rsd"],
        )
        if r_contact != group["values"]["rsd"]:
            assert pred != pytest.approx(pred_rsd, rel=1e-6)

    def test_t36e343_20(self, tapeout_calibration_run: tuple) -> None:
        """Cgg model must apply subthreshold depletion rolloff below vth."""
        tapeout, _, validation = tapeout_calibration_run
        geom = next(g for g in tapeout["geometries"] if g["geometry_id"] == "G1")
        group = next(g for g in validation["fitted_groups"] if g["split_group"] == geom["split_group"])
        low = cgg_model(group["values"], 0.0, geom, 25.0, tapeout["reference_temp_c"])
        high = cgg_model(group["values"], 0.8, geom, 25.0, tapeout["reference_temp_c"])
        assert high > low

    def test_t36e343_21(self, tapeout_calibration_run: tuple) -> None:
        """Shared split group A must span geometries G1 and G2 with one parameter set."""
        _, _, validation = tapeout_calibration_run
        group_a = next(g for g in validation["fitted_groups"] if g["split_group"] == "A")
        assert group_a is not None
        tapeout_data = json.loads(TAPEOUT_PATH.read_text(encoding="utf-8"))
        ids = [g["geometry_id"] for g in tapeout_data["geometries"] if g["split_group"] == "A"]
        assert set(ids) == {"G1", "G2"}

    def test_t36e343_22(self, tapeout_calibration_run: tuple) -> None:
        """Split group B must produce an independent fitted parameter block."""
        _, _, validation = tapeout_calibration_run
        groups = {g["split_group"] for g in validation["fitted_groups"]}
        assert "B" in groups
        a = next(g for g in validation["fitted_groups"] if g["split_group"] == "A")
        b = next(g for g in validation["fitted_groups"] if g["split_group"] == "B")
        assert a["values"]["vth0"] != pytest.approx(b["values"]["vth0"], rel=0, abs=1e-3)


class TestCliGuardsAndOverlays:
    def test_t36e343_23(self) -> None:
        """characterize must reject relative data directory paths."""
        proc = invoke(
            [
                "characterize",
                "--data-dir",
                "data/bundled",
                "--tapeout",
                "/app/state/calibration_tapeout.json",
            ]
        )
        assert proc.returncode != 0

    def test_t36e343_24(self, tmp_path: Path) -> None:
        """TB3_GAA_DATA_ROOT overlay must replace bundled measurement inputs."""
        # Snapshot verifier ground truth before the agent binary runs so a
        # compromised process cannot rewrite fixtures used as expected values.
        expected = build_tapeout(HOT_IV)
        bundled_staging = build_tapeout(DATA)
        tapeout = tmp_path / ("overlay-" + "tapeout.json")
        code = invoke(
            [
                "characterize",
                "--data-dir",
                str(DATA),
                "--tapeout",
                str(tapeout),
            ],
            env={"TB3_GAA_DATA_ROOT": str(HOT_IV)},
        ).returncode
        assert code == 0
        staging_obj = json.loads(tapeout.read_text(encoding="utf-8"))
        assert_tapeout_matches_reference(staging_obj, expected)
        assert staging_obj["measure_digest"] != bundled_staging["measure_digest"]
        assert any(p["temp_c"] != pytest.approx(25.0) for p in expected["iv_points"])

    def test_t36e343_25(
        self, tapeout_calibration_run: tuple, tmp_path: Path
    ) -> None:
        """TB3_GAA_BOUNDS_ROOT overlay must refit every split group against tight bounds."""
        tapeout_data = json.loads(TAPEOUT_PATH.read_text(encoding="utf-8"))
        default_validation = fit_from_tapeout(tapeout_data, BOUNDS)
        tight_bounds_path = TIGHT_BOUNDS / "parameter_bounds.toml"
        expected = fit_from_tapeout(tapeout_data, tight_bounds_path)
        tight_bounds = load_bounds(tight_bounds_path)
        spice = tmp_path / "tight.sp"
        validation = tmp_path / "tight.json"
        code = invoke(
            [
                "model-fit",
                "--tapeout",
                str(TAPEOUT_PATH),
                "--bounds",
                str(BOUNDS),
                "--spice",
                str(spice),
                "--validation",
                str(validation),
            ],
            env={"TB3_GAA_BOUNDS_ROOT": str(TIGHT_BOUNDS)},
        ).returncode
        assert code == 0
        payload = json.loads(validation.read_text(encoding="utf-8"))
        spice_text = spice.read_text(encoding="utf-8")
        for group in payload["fitted_groups"]:
            sg = group["split_group"]
            exp = next(g for g in expected["fitted_groups"] if g["split_group"] == sg)
            assert_fitted_values_match(group["values"], exp["values"], tight_bounds)
        assert payload["validation_digest"] == expected["validation_digest"]
        assert spice_text == render_spice(tapeout_data, expected["fitted_groups"])
        default_a = next(g for g in default_validation["fitted_groups"] if g["split_group"] == "A")
        tight_a = next(g for g in expected["fitted_groups"] if g["split_group"] == "A")
        assert tight_a["values"]["vth0"] != pytest.approx(
            default_a["values"]["vth0"], rel=0, abs=1e-6
        )
        # Permuted overlay tie_break_order must differ from the bundled walk.
        bundled_order = load_bounds(BOUNDS)["shared_groups"]["A"]["tie_break_order"]
        assert tight_bounds["shared_groups"]["A"]["tie_break_order"] != bundled_order

    def test_t36e343_26(self, calibration_tapeout_snapshot: dict) -> None:
        """TB3_GAA_BOUNDS_ROOT must reject relative overlay paths."""
        proc = invoke(
            [
                "model-fit",
                "--tapeout",
                str(TAPEOUT_PATH),
                "--bounds",
                str(BOUNDS),
                "--spice",
                "/tmp/x.sp",
                "--validation",
                "/tmp/x.json",
            ],
            env={"TB3_GAA_BOUNDS_ROOT": "relative/path"},
        )
        assert proc.returncode != 0

    def test_t36e343_27(self) -> None:
        """TB3_GAA_DATA_ROOT must reject relative overlay paths."""
        proc = invoke(
            [
                "characterize",
                "--data-dir",
                str(DATA),
                "--tapeout",
                "/tmp/x.json",
            ],
            env={"TB3_GAA_DATA_ROOT": "relative/path"},
        )
        assert proc.returncode != 0

    def test_t36e343_28(self, tmp_path: Path) -> None:
        """Shuffled geometry_manifest rows must still tape out sorted by geometry_id."""
        raw = json.loads((DATA / "geometry_manifest.json").read_text(encoding="utf-8"))
        disk_ids = [g["geometry_id"] for g in raw["geometries"]]
        assert disk_ids != sorted(disk_ids)
        tapeout = tmp_path / "sorted-geom-tapeout.json"
        code = invoke(
            [
                "characterize",
                "--data-dir",
                str(DATA),
                "--tapeout",
                str(tapeout),
            ]
        ).returncode
        assert code == 0
        payload = json.loads(tapeout.read_text(encoding="utf-8"))
        ids = [g["geometry_id"] for g in payload["geometries"]]
        assert ids == sorted(ids)
        assert_tapeout_matches_reference(payload, build_tapeout(DATA))

    def test_t36e343_29(self, tmp_path: Path) -> None:
        """Non-reference measurement temperatures must load into the kt1/ute-aware fit."""
        expected_tapeout = build_tapeout(HOT_IV)
        assert any(p["temp_c"] == pytest.approx(85.0) for p in expected_tapeout["iv_points"])
        expected_val = fit_from_tapeout(expected_tapeout, BOUNDS)
        # Ignoring kt1/ute produces a different coordinate-descent fixed point.
        zero_scale = dict(expected_val["fitted_groups"][0]["values"])
        zero_scale["kt1"] = 0.0
        zero_scale["ute"] = 0.0
        expected_rollup = build_rollup(expected_tapeout)
        assert combined_rmse(zero_scale, expected_tapeout, expected_rollup, "A") != pytest.approx(
            combined_rmse(expected_val["fitted_groups"][0]["values"], expected_tapeout, expected_rollup, "A"),
            rel=0,
            abs=1e-18,
        )
        tapeout = tmp_path / "hot-tapeout.json"
        spice = tmp_path / "hot.sp"
        validation = tmp_path / "hot.json"
        code = invoke(
            [
                "characterize",
                "--data-dir",
                str(DATA),
                "--tapeout",
                str(tapeout),
            ],
            env={"TB3_GAA_DATA_ROOT": str(HOT_IV)},
        ).returncode
        assert code == 0
        staging = json.loads(tapeout.read_text(encoding="utf-8"))
        assert_tapeout_matches_reference(staging, expected_tapeout)
        with bundled_inputs_hidden():
            code = invoke(
                [
                    "model-fit",
                    "--tapeout",
                    str(tapeout),
                    "--bounds",
                    str(BOUNDS),
                    "--spice",
                    str(spice),
                    "--validation",
                    str(validation),
                ],
                env={"TB3_GAA_DATA_ROOT": str(HOT_IV)},
                policy=MODEL_FIT_POLICY,
            ).returncode
        assert code == 0
        payload = json.loads(validation.read_text(encoding="utf-8"))
        bounds = load_bounds(BOUNDS)
        for group in payload["fitted_groups"]:
            sg = group["split_group"]
            exp = next(g for g in expected_val["fitted_groups"] if g["split_group"] == sg)
            assert_fitted_values_match(group["values"], exp["values"], bounds)
        assert payload["validation_digest"] == expected_val["validation_digest"]

    def test_t36e343_30(self, tmp_path: Path) -> None:
        """characterize must atomically replace an existing complete tapeout destination."""
        tapeout = tmp_path / "atomic-tapeout.json"
        expected = build_tapeout(DATA)
        stale = dict(expected)
        stale["measure_digest"] = "0" * 64
        stale["reference_temp_c"] = -99.0
        tapeout.write_text(json.dumps(stale, sort_keys=True), encoding="utf-8")
        stale_digest = stale["measure_digest"]
        expected_digest = expected["measure_digest"]

        code, _events = verify_atomic_tapeout_replace(
            cmd=[
                BIN,
                "characterize",
                "--data-dir",
                "/app/data/bundled",
                "--tapeout",
                str(tapeout),
            ],
            destination=tapeout,
        )
        assert code == 0
        payload = json.loads(tapeout.read_text(encoding="utf-8"))
        assert_tapeout_matches_reference(payload, expected)
        assert payload["measure_digest"] != stale_digest
        assert payload["measure_digest"] == expected_digest

    def test_t36e343_31(self, tapeout_calibration_run: tuple, tmp_path: Path) -> None:
        """Reversed tie_break_order overlay must change the fitted validation digest."""
        tapeout_data = json.loads(TAPEOUT_PATH.read_text(encoding="utf-8"))
        default_fit = fit_from_tapeout(tapeout_data, BOUNDS)
        reversed_path = REVERSED_ORDER / "parameter_bounds.toml"
        expected = fit_from_tapeout(tapeout_data, reversed_path)
        assert expected["validation_digest"] != default_fit["validation_digest"]
        spice = tmp_path / "rev.sp"
        validation = tmp_path / "rev.json"
        code = invoke(
            [
                "model-fit",
                "--tapeout",
                str(TAPEOUT_PATH),
                "--bounds",
                str(BOUNDS),
                "--spice",
                str(spice),
                "--validation",
                str(validation),
            ],
            env={"TB3_GAA_BOUNDS_ROOT": str(REVERSED_ORDER)},
        ).returncode
        assert code == 0
        payload = json.loads(validation.read_text(encoding="utf-8"))
        assert payload["validation_digest"] == expected["validation_digest"]
        assert payload["validation_digest"] != default_fit["validation_digest"]

    def test_t36e343_32(self, tmp_path: Path) -> None:
        """model-fit must not reread overlay measurement files when TB3_GAA_DATA_ROOT stays set."""
        tapeout = tmp_path / "overlay-isolate-tapeout.json"
        out_spice = tmp_path / "overlay-isolate.sp"
        out_val = tmp_path / "overlay-isolate.json"
        expected_tapeout = build_tapeout(HOT_IV)
        code = invoke(
            [
                "characterize",
                "--data-dir",
                str(DATA),
                "--tapeout",
                str(tapeout),
            ],
            env={"TB3_GAA_DATA_ROOT": str(HOT_IV)},
        ).returncode
        assert code == 0
        staging = json.loads(tapeout.read_text(encoding="utf-8"))
        assert_tapeout_matches_reference(staging, expected_tapeout)
        expected_val = fit_from_tapeout(expected_tapeout, BOUNDS)
        bounds = load_bounds(BOUNDS)
        code = invoke(
            [
                "model-fit",
                "--tapeout",
                str(tapeout),
                "--bounds",
                str(BOUNDS),
                "--spice",
                str(out_spice),
                "--validation",
                str(out_val),
            ],
            env={"TB3_GAA_DATA_ROOT": str(HOT_IV)},
            policy=MODEL_FIT_POLICY,
        ).returncode
        assert code == 0
        payload = json.loads(out_val.read_text(encoding="utf-8"))
        spice_text = out_spice.read_text(encoding="utf-8")
        for group in payload["fitted_groups"]:
            sg = group["split_group"]
            exp = next(g for g in expected_val["fitted_groups"] if g["split_group"] == sg)
            assert_fitted_values_match(group["values"], exp["values"], bounds)
        assert payload["validation_digest"] == expected_val["validation_digest"]
        assert spice_text == render_spice(expected_tapeout, expected_val["fitted_groups"])

    def test_t36e343_33(self) -> None:
        """characterize with documented default paths must load bundled measurement inputs."""
        if TAPEOUT_PATH.exists():
            TAPEOUT_PATH.unlink()
        for path in INSTRUCTION_MEASUREMENT_PATHS:
            assert path.is_file(), f"missing instruction-cited measurement path {path}"
        code = invoke(["characterize"]).returncode
        assert code == 0
        payload = json.loads(TAPEOUT_PATH.read_text(encoding="utf-8"))
        expected = build_tapeout(DATA)
        assert_tapeout_matches_reference(payload, expected)
        assert payload["iv_points"] == expected["iv_points"]
        assert payload["cv_points"] == expected["cv_points"]
        assert payload["geometries"] == expected["geometries"]
        assert payload["contacts"] == expected["contacts"]

    def test_t36e343_34(self) -> None:
        """run defaults must keep the fit stage tapeout-only even while measurements stay on disk."""
        for path in (TAPEOUT_PATH, SPICE, VALIDATION):
            if path.exists():
                path.unlink()
        expected_tapeout = build_tapeout(DATA)
        poison_tapeout = build_tapeout(HOT_IV)
        assert poison_tapeout["measure_digest"] != expected_tapeout["measure_digest"]
        expected_val = fit_from_tapeout(expected_tapeout, BOUNDS)
        poison_val = fit_from_tapeout(poison_tapeout, BOUNDS)
        assert poison_val["validation_digest"] != expected_val["validation_digest"]
        code, _events = verify_run_keeps_fit_tapeout_only(
            cmd=[BIN, "run"],
            tapeout_path=TAPEOUT_PATH,
            data_dir=DATA,
            measurement_names=BUNDLED_MEASUREMENT_FILES,
        )
        assert code == 0
        tapeout = json.loads(TAPEOUT_PATH.read_text(encoding="utf-8"))
        validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
        assert_tapeout_matches_reference(tapeout, expected_tapeout)
        assert validation["validation_digest"] == expected_val["validation_digest"]
        assert validation["validation_digest"] != poison_val["validation_digest"]
        assert SPICE.read_text(encoding="utf-8") == render_spice(
            tapeout, validation["fitted_groups"]
        )
        # Isolated model-fit under the strict policy must still reproduce the card
        # after measurements are removed entirely.
        if SPICE.exists():
            SPICE.unlink()
        if VALIDATION.exists():
            VALIDATION.unlink()
        with bundled_inputs_hidden():
            code = invoke(["model-fit"], policy=MODEL_FIT_POLICY).returncode
        assert code == 0
        revalidation = json.loads(VALIDATION.read_text(encoding="utf-8"))
        assert revalidation["validation_digest"] == expected_val["validation_digest"]
        assert SPICE.read_text(encoding="utf-8") == render_spice(
            tapeout, revalidation["fitted_groups"]
        )

    def test_t36e343_35(self, calibration_tapeout_snapshot: dict) -> None:
        """model-fit with documented default output paths must fit the persisted tapeout."""
        if SPICE.exists():
            SPICE.unlink()
        if VALIDATION.exists():
            VALIDATION.unlink()
        expected = fit_from_tapeout(calibration_tapeout_snapshot, BOUNDS)
        bounds = load_bounds(BOUNDS)
        code = invoke(["model-fit"]).returncode
        assert code == 0
        payload = json.loads(VALIDATION.read_text(encoding="utf-8"))
        spice_text = SPICE.read_text(encoding="utf-8")
        for group in payload["fitted_groups"]:
            sg = group["split_group"]
            exp = next(g for g in expected["fitted_groups"] if g["split_group"] == sg)
            assert_fitted_values_match(group["values"], exp["values"], bounds)
        assert payload["validation_digest"] == expected["validation_digest"]
        assert spice_text == render_spice(calibration_tapeout_snapshot, expected["fitted_groups"])

    def test_t36e343_36(self, tmp_path: Path) -> None:
        """Empty TB3_GAA_DATA_ROOT must fall back to bundled measurement inputs."""
        tapeout = tmp_path / "empty-data-overlay-tapeout.json"
        expected = build_tapeout(DATA)
        hot = build_tapeout(HOT_IV)
        assert expected["measure_digest"] != hot["measure_digest"]
        code = invoke(
            [
                "characterize",
                "--data-dir",
                str(DATA),
                "--tapeout",
                str(tapeout),
            ],
            env={"TB3_GAA_DATA_ROOT": ""},
        ).returncode
        assert code == 0
        payload = json.loads(tapeout.read_text(encoding="utf-8"))
        assert_tapeout_matches_reference(payload, expected)

    def test_t36e343_37(
        self, calibration_tapeout_snapshot: dict, tmp_path: Path
    ) -> None:
        """Empty TB3_GAA_BOUNDS_ROOT must fall back to the --bounds CLI path."""
        tapeout_data = calibration_tapeout_snapshot
        expected_default = fit_from_tapeout(tapeout_data, BOUNDS)
        tight_expected = fit_from_tapeout(tapeout_data, TIGHT_BOUNDS / "parameter_bounds.toml")
        assert expected_default["validation_digest"] != tight_expected["validation_digest"]
        spice = tmp_path / "empty-bounds.sp"
        validation = tmp_path / "empty-bounds.json"
        code = invoke(
            [
                "model-fit",
                "--tapeout",
                str(TAPEOUT_PATH),
                "--bounds",
                str(BOUNDS),
                "--spice",
                str(spice),
                "--validation",
                str(validation),
            ],
            env={"TB3_GAA_BOUNDS_ROOT": ""},
        ).returncode
        assert code == 0
        payload = json.loads(validation.read_text(encoding="utf-8"))
        assert payload["validation_digest"] == expected_default["validation_digest"]
        assert payload["validation_digest"] != tight_expected["validation_digest"]


class TestGeometryRollupStaging:
    """Geometry rollup closure — characterize must ingest measurements into rollup weights before model-fit."""

    def test_t36e343_38(self, tapeout_calibration_run: tuple) -> None:
        """geometry_rollup.json must match independent reference rollup builder."""
        tapeout, _, _ = tapeout_calibration_run
        rollup = json.loads(ROLLUP_PATH.read_text(encoding="utf-8"))
        expected = build_rollup(tapeout)
        assert rollup == expected

    def test_t36e343_39(self, tapeout_calibration_run: tuple) -> None:
        """rollup measure_digest must bind to the sealed calibration tapeout."""
        tapeout, _, _ = tapeout_calibration_run
        rollup = json.loads(ROLLUP_PATH.read_text(encoding="utf-8"))
        assert rollup["measure_digest"] == tapeout["measure_digest"]

    def test_t36e343_40(self, calibration_tapeout_snapshot: dict, tmp_path: Path) -> None:
        """model-fit must fail when geometry rollup file is missing."""
        out_spice = tmp_path / "no-rollup.sp"
        out_val = tmp_path / "no-rollup.json"
        if ROLLUP_PATH.exists():
            ROLLUP_PATH.unlink()
        proc = invoke(
            [
                "model-fit",
                "--tapeout",
                str(TAPEOUT_PATH),
                "--rollup",
                str(ROLLUP_PATH),
                "--bounds",
                str(BOUNDS),
                "--spice",
                str(out_spice),
                "--validation",
                str(out_val),
            ],
            policy=MODEL_FIT_POLICY,
        )
        assert proc.returncode != 0

    def test_t36e343_41(self, tapeout_calibration_run: tuple) -> None:
        """validation JSON must carry rollup_digest from geometry rollup file."""
        _, _, validation = tapeout_calibration_run
        rollup = json.loads(ROLLUP_PATH.read_text(encoding="utf-8"))
        assert validation["rollup_digest"] == rollup["rollup_digest"]

    def test_t36e343_42(self, tapeout_calibration_run: tuple) -> None:
        """Strong-inversion Id must include k1 body-factor scaling above threshold."""
        tapeout, _, validation = tapeout_calibration_run
        geom = next(g for g in tapeout["geometries"] if g["geometry_id"] == "G1")
        group = next(g for g in validation["fitted_groups"] if g["split_group"] == geom["split_group"])
        params = dict(group["values"])
        vgs = float(params["vth0"]) + 0.40
        vds = 0.20
        with_k1 = id_model(
            params,
            vgs,
            vds,
            geom,
            tapeout["reference_temp_c"],
            tapeout["reference_temp_c"],
            0.0,
        )
        no_k1 = dict(params)
        no_k1["k1"] = 0.0
        without_k1 = id_model(
            no_k1,
            vgs,
            vds,
            geom,
            tapeout["reference_temp_c"],
            tapeout["reference_temp_c"],
            0.0,
        )
        assert with_k1 > 0.0
        assert with_k1 != pytest.approx(without_k1, rel=0, abs=1e-15)
        assert with_k1 > without_k1

    def test_t36e343_43(self, tmp_path: Path) -> None:
        """Aspect geometry overlay must change rollup weights and fitted validation digest."""
        bundled_tapeout = build_tapeout(DATA)
        flip_tapeout = build_tapeout(ASPECT_FLIP)
        assert bundled_tapeout["measure_digest"] == flip_tapeout["measure_digest"]
        bundled_rollup = build_rollup(bundled_tapeout)
        flip_rollup = build_rollup(flip_tapeout)
        assert bundled_rollup["rollup_digest"] != flip_rollup["rollup_digest"]
        bundled_fit = fit_from_tapeout(bundled_tapeout, BOUNDS)
        flip_fit = fit_from_tapeout(flip_tapeout, BOUNDS)
        assert flip_fit["validation_digest"] != bundled_fit["validation_digest"]
        tapeout = tmp_path / "aspect-flip-tapeout.json"
        rollup = tmp_path / "aspect-flip-rollup.json"
        spice = tmp_path / "aspect-flip.sp"
        validation = tmp_path / "aspect-flip.json"
        code = invoke(
            [
                "characterize",
                "--data-dir",
                str(DATA),
                "--tapeout",
                str(tapeout),
                "--rollup",
                str(rollup),
            ],
            env={"TB3_GAA_DATA_ROOT": str(ASPECT_FLIP)},
        ).returncode
        assert code == 0
        staging = json.loads(tapeout.read_text(encoding="utf-8"))
        assert_tapeout_matches_reference(staging, flip_tapeout)
        staging_rollup = json.loads(rollup.read_text(encoding="utf-8"))
        assert staging_rollup == flip_rollup
        with bundled_inputs_hidden():
            code = invoke(
                [
                    "model-fit",
                    "--tapeout",
                    str(tapeout),
                    "--rollup",
                    str(rollup),
                    "--bounds",
                    str(BOUNDS),
                    "--spice",
                    str(spice),
                    "--validation",
                    str(validation),
                ],
                policy=MODEL_FIT_POLICY,
            ).returncode
        assert code == 0
        payload = json.loads(validation.read_text(encoding="utf-8"))
        bounds = load_bounds(BOUNDS)
        for group in payload["fitted_groups"]:
            sg = group["split_group"]
            exp = next(g for g in flip_fit["fitted_groups"] if g["split_group"] == sg)
            assert_fitted_values_match(group["values"], exp["values"], bounds)
        assert payload["validation_digest"] == flip_fit["validation_digest"]
        assert payload["rollup_digest"] == flip_rollup["rollup_digest"]

    def test_t36e343_44(self, tapeout_calibration_run: tuple) -> None:
        """Unweighted RMSE objective must diverge from weighted coordinate-descent closure."""
        tapeout, _, validation = tapeout_calibration_run
        rollup = build_rollup(tapeout)
        group_a = next(g for g in validation["fitted_groups"] if g["split_group"] == "A")
        geoms = {g["geometry_id"]: g for g in group_geometries(tapeout, "A")}
        unweighted_err = 0.0
        unweighted_n = 0
        for point in tapeout["iv_points"]:
            if point["geometry_id"] not in geoms:
                continue
            geom = geoms[point["geometry_id"]]
            r = float(tapeout["contacts"][point["geometry_id"]])
            pred = id_model(
                group_a["values"],
                point["vgs"],
                point["vds"],
                geom,
                point["temp_c"],
                tapeout["reference_temp_c"],
                r,
            )
            diff = point["id_amps"] - pred
            unweighted_err += diff * diff
            unweighted_n += 1
        unweighted_id = math.sqrt(unweighted_err / unweighted_n)
        weighted_id = rmse_id(group_a["values"], tapeout, rollup, "A")
        assert weighted_id != pytest.approx(unweighted_id, rel=0, abs=1e-12)
















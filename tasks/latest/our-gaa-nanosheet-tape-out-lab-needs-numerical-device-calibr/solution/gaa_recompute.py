"""Contract evaluation helpers for GAA nanosheet compact-model calibration."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import struct
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

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
    return {
        "schema_version": "gaa-rollup-v1",
        "reference_temp_c": tapeout["reference_temp_c"],
        "measure_digest": tapeout["measure_digest"],
        "entries": entries,
        "rollup_digest": rollup_digest(entries),
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






"""Independent Ambergate assay reference — mixing, enrichment, feasibility."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def round6(x: float) -> float:
    return round(x * 1_000_000.0) / 1_000_000.0


def rho_ideal(f_au: float, f_ag: float, f_cu: float, metals: dict) -> float:
    inv = f_au / metals["rho_au"] + f_ag / metals["rho_ag"] + f_cu / metals["rho_cu"]
    return 1.0 / inv


def rho_of(
    f_au: float,
    f_ag: float,
    f_cu: float,
    mixing_rule: str,
    kappa: float | None,
    metals: dict,
) -> float:
    base = rho_ideal(f_au, f_ag, f_cu, metals)
    if mixing_rule == "nonideal":
        k = 0.0 if kappa is None else float(kappa)
        return base * (1.0 + k * f_au * f_cu)
    return base


def sample_simplex(grid_n: int) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    if grid_n < 2:
        return out
    n = grid_n - 1
    for i in range(n + 1):
        for j in range(n - i + 1):
            f_au = i / n
            f_ag = j / n
            f_cu = 1.0 - f_au - f_ag
            if f_cu >= -1e-12:
                out.append((f_au, f_ag, max(0.0, f_cu)))
    return out


def enrichment_delta(model: dict) -> float:
    return min(model["enrichment_cap"], model["rate_per_year"] * model["burial_years"])


def corrected_xrf_bound(
    f_au_s: float,
    f_ag_s: float,
    f_cu_s: float,
    sigma: float,
    model: dict,
    k_sigma: float,
) -> dict:
    delta = enrichment_delta(model)
    ks = k_sigma * sigma
    return {
        "f_au_min": round6(max(0.0, f_au_s - delta - ks)),
        "f_au_max": round6(min(1.0, f_au_s + ks)),
        "f_ag_min": round6(max(0.0, f_ag_s - delta - ks)),
        "f_ag_max": round6(min(1.0, f_ag_s + ks)),
        "f_cu_min": round6(max(0.0, f_cu_s - ks)),
        "f_cu_max": round6(min(1.0, f_cu_s + delta + ks)),
        "delta": round6(delta),
        "model_id": model["model_id"],
    }


def in_bound(a: float, g: float, c: float, b: dict) -> bool:
    return (
        b["f_au_min"] - 1e-12 <= a <= b["f_au_max"] + 1e-12
        and b["f_ag_min"] - 1e-12 <= g <= b["f_ag_max"] + 1e-12
        and b["f_cu_min"] - 1e-12 <= c <= b["f_cu_max"] + 1e-12
    )


def region_from_points(points: list[tuple[float, float, float]]) -> dict | None:
    if not points:
        return None
    aus = [p[0] for p in points]
    ags = [p[1] for p in points]
    cus = [p[2] for p in points]
    return {
        "f_au_min": round6(min(aus)),
        "f_au_max": round6(max(aus)),
        "f_ag_min": round6(min(ags)),
        "f_ag_max": round6(max(ags)),
        "f_cu_min": round6(min(cus)),
        "f_cu_max": round6(max(cus)),
    }


def density_band_summary(points: list[tuple[float, float, float]]) -> dict | None:
    region = region_from_points(points)
    if region is None:
        return None
    return {
        "point_count": len(points),
        **region,
    }


def evaluate_coin(coin: dict, metals: dict, models: dict, cfg: dict) -> dict:
    model_by_id = {m["model_id"]: m for m in models["models"]}
    rec: dict[str, Any] = {
        "coin_id": coin["coin_id"],
        "status": "insufficient_data",
        "reason": None,
        "feasible_region": None,
        "density_band": None,
        "xrf_bound": None,
        "intersection_point_count": 0,
        "enrichment_model_id": coin["enrichment_model_id"],
    }
    if coin.get("density") is None or coin.get("density_sigma") is None:
        rec["reason"] = "missing_density"
        return rec

    grid = sample_simplex(int(cfg["grid_n"]))
    band = [
        p
        for p in grid
        if abs(
            rho_of(p[0], p[1], p[2], coin["mixing_rule"], coin.get("kappa"), metals)
            - float(coin["density"])
        )
        <= float(coin["density_sigma"]) + 1e-12
    ]
    rec["density_band"] = density_band_summary(band)

    xrf_present = (
        coin.get("xrf_au") is not None
        and coin.get("xrf_ag") is not None
        and coin.get("xrf_cu") is not None
    )
    if not xrf_present:
        rec["status"] = "density_only"
        rec["feasible_region"] = region_from_points(band)
        rec["intersection_point_count"] = len(band)
        return rec

    if coin.get("xrf_sigma") is None:
        rec["reason"] = "missing_xrf_uncertainty"
        return rec

    model = model_by_id[coin["enrichment_model_id"]]
    bound = corrected_xrf_bound(
        float(coin["xrf_au"]),
        float(coin["xrf_ag"]),
        float(coin["xrf_cu"]),
        float(coin["xrf_sigma"]),
        model,
        float(cfg["k_sigma"]),
    )
    rec["xrf_bound"] = bound
    hit = [p for p in band if in_bound(p[0], p[1], p[2], bound)]
    rec["intersection_point_count"] = len(hit)
    region = region_from_points(hit)
    if region is None:
        rec["status"] = "inconsistent"
        rec["reason"] = "empty_intersection"
    else:
        rec["status"] = "feasible"
        rec["feasible_region"] = region
    return rec


def build_products(app: Path) -> dict:
    cfg = load_json(app / "data" / "assay-config.json")
    coins = load_json(app / "data" / "coins.json")
    metals = load_json(app / "data" / "metal-densities.json")
    models = load_json(app / "data" / "enrichment-models.json")
    records = [evaluate_coin(c, metals, models, cfg) for c in coins["coins"]]
    records.sort(key=lambda r: r["coin_id"])
    inconsistent = sorted(r["coin_id"] for r in records if r["status"] == "inconsistent")
    return {
        "coins": records,
        "inconsistent": inconsistent,
        "feasible_count": sum(1 for r in records if r["status"] == "feasible"),
        "density_only_count": sum(1 for r in records if r["status"] == "density_only"),
        "insufficient_count": sum(1 for r in records if r["status"] == "insufficient_data"),
        "inconsistent_count": len(inconsistent),
    }

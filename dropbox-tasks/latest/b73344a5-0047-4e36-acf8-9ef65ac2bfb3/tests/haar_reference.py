"""Independent Haar DWT + MAD soft-threshold reference for the verifier."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


def round12(x: float) -> float:
    return round(x * 1e12) / 1e12


def round_vec12(v: list[float]) -> list[float]:
    return [round12(x) for x in v]


def max_levels_for_length(n: int) -> int:
    if n < 2:
        return 0
    levels = 0
    v = n
    while v >= 2:
        levels += 1
        v //= 2
    return levels


def clamp_levels(requested: int, max_levels: int, n: int) -> int:
    return min(requested, max_levels, max_levels_for_length(n))


def forward_haar_level(samples: list[float]) -> tuple[list[float], list[float], int]:
    pre_pad = len(samples)
    work = list(samples)
    if len(work) % 2 == 1:
        work.append(work[-1])
    s = math.sqrt(2.0)
    approx: list[float] = []
    detail: list[float] = []
    for i in range(len(work) // 2):
        x0 = work[2 * i]
        x1 = work[2 * i + 1]
        approx.append((x0 + x1) / s)
        detail.append((x0 - x1) / s)
    return approx, detail, pre_pad


def inverse_haar_level(approx: list[float], detail: list[float], pre_pad: int) -> list[float]:
    s = math.sqrt(2.0)
    out: list[float] = []
    for a, d in zip(approx, detail):
        out.append((a + d) / s)
        out.append((a - d) / s)
    if len(out) > pre_pad:
        out = out[:pre_pad]
    return out


def forward_pyramid(
    samples: list[float], levels: int
) -> tuple[list[float], list[list[float]], list[int]]:
    approx = list(samples)
    details: list[list[float]] = []
    pads: list[int] = []
    for _ in range(levels):
        a, d, pre = forward_haar_level(approx)
        pads.append(pre)
        details.append(d)
        approx = a
    return approx, details, pads


def inverse_pyramid(
    approx: list[float], details: list[list[float]], pads: list[int]
) -> list[float]:
    a = list(approx)
    for lvl in range(len(details) - 1, -1, -1):
        a = inverse_haar_level(a, details[lvl], pads[lvl])
    return a


def median_abs(values: list[float]) -> float:
    if not values:
        return 0.0
    v = sorted(abs(x) for x in values)
    n = len(v)
    if n % 2 == 1:
        return v[n // 2]
    return 0.5 * (v[n // 2 - 1] + v[n // 2])


def soft_threshold(c: float, lam: float) -> float:
    a = abs(c)
    if a <= lam:
        return 0.0
    return math.copysign(a - lam, c)


def select_policy(policy_dir: Path, case_id: str) -> dict[str, Any]:
    matched = []
    for path in sorted(policy_dir.glob("*.json")):
        p = json.loads(path.read_text(encoding="utf-8"))
        if p.get("case_id") == case_id:
            matched.append(p)
    if not matched:
        raise ValueError(f"no policy for {case_id}")
    matched.sort(key=lambda p: (p["effective_at"], p["revision_id"]), reverse=True)
    return matched[0]


def load_bundle(data_dir: Path) -> dict[str, Any]:
    cfg = json.loads((data_dir / "denoise-config.json").read_text(encoding="utf-8"))
    policy = select_policy(data_dir / "threshold-policies", cfg["case_id"])
    traces = []
    for path in sorted((data_dir / "traces").glob("*.json")):
        traces.append(json.loads(path.read_text(encoding="utf-8")))
    traces.sort(key=lambda t: t["trace_id"])
    return {"config": cfg, "policy": policy, "traces": traces}


def full_reference(data_dir: Path) -> dict[str, Any]:
    bundle = load_bundle(data_dir)
    cfg = bundle["config"]
    policy = bundle["policy"]
    traces = bundle["traces"]

    pyramids = []
    finest_pool: list[float] = []
    detail_coeff_count = 0
    global_levels = 0
    for t in traces:
        samples = [float(x) for x in t["samples"]]
        levels = clamp_levels(int(cfg["requested_levels"]), int(cfg["max_levels"]), len(samples))
        global_levels = max(global_levels, levels)
        approx, details, pads = forward_pyramid(samples, levels)
        for d in details:
            detail_coeff_count += len(d)
        if details:
            finest_pool.extend(details[0])
        pyramids.append(
            {
                "trace_id": t["trace_id"],
                "samples": samples,
                "levels": levels,
                "approx": approx,
                "details": details,
                "pads": pads,
            }
        )

    sigma = median_abs(finest_pool) / 0.6745
    n_ref = max((len(t["samples"]) for t in traces), default=2)
    l0 = policy["mad_multiplier"] * sigma * math.sqrt(2.0 * math.log(max(n_ref, 2)))
    lambdas = []
    for j in range(1, global_levels + 1):
        lambdas.append(l0 / (2.0 ** ((j - 1) / 2.0)))

    zero_count = 0
    entries = []
    for pyr in pyramids:
        details_out = []
        for j, band in enumerate(pyr["details"]):
            lam = lambdas[j] if j < len(lambdas) else 0.0
            thr = [soft_threshold(c, lam) for c in band]
            for a, b in zip(band, thr):
                if b == 0.0 and a != 0.0:
                    zero_count += 1
            details_out.append(thr)
        y = inverse_pyramid(pyr["approx"], details_out, pyr["pads"])
        y = round_vec12(y)
        signal_energy = sum(x * x for x in pyr["samples"])
        residual_energy = sum((x - yy) ** 2 for x, yy in zip(pyr["samples"], y))
        relative = residual_energy / max(signal_energy, 1e-18)
        entries.append(
            {
                "trace_id": pyr["trace_id"],
                "original_length": len(pyr["samples"]),
                "effective_levels": pyr["levels"],
                "approx": round_vec12(pyr["approx"]),
                "details": [round_vec12(d) for d in details_out],
                "pad_lengths": pyr["pads"],
                "denoised": y,
                "signal_energy": round12(signal_energy),
                "residual_energy": round12(residual_energy),
                "relative_residual": round12(relative),
            }
        )

    entries.sort(key=lambda e: e["trace_id"])
    total_signal = sum(e["signal_energy"] for e in entries)
    total_resid = sum(e["residual_energy"] for e in entries)
    mean_rel = (
        sum(e["relative_residual"] for e in entries) / len(entries) if entries else 0.0
    )

    return {
        "policy_revision_id": policy["revision_id"],
        "mad_multiplier": round12(float(policy["mad_multiplier"])),
        "mad_sigma": round12(sigma),
        "lambda0": round12(l0),
        "lambdas": round_vec12(lambdas),
        "effective_levels": global_levels,
        "detail_coeff_count": detail_coeff_count,
        "thresholded_zero_count": zero_count,
        "entries": entries,
        "total_signal_energy": round12(total_signal),
        "total_residual_energy": round12(total_resid),
        "mean_relative_residual": round12(mean_rel),
    }


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot_digest(snap: dict[str, Any]) -> str:
    payload = {
        "case_id": snap["case_id"],
        "mad_multiplier": snap["mad_multiplier"],
        "max_levels": snap["max_levels"],
        "policy_revision_id": snap["policy_revision_id"],
        "requested_levels": snap["requested_levels"],
        "schema_version": snap["schema_version"],
        "traces": snap["traces"],
    }
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _fmt12(x: float) -> str:
    return f"{x:.12f}"


def pack_seal(snapshot_digest_hex: str, policy_revision_id: int, entries: list[dict[str, Any]]) -> str:
    parts: list[str] = [snapshot_digest_hex, "|", str(policy_revision_id), "|"]
    for entry in entries:
        parts.append(entry["trace_id"])
        parts.append("|")
        parts.append(str(int(entry["original_length"])))
        parts.append("|")
        parts.append(str(int(entry["effective_levels"])))
        parts.append("|")
        for p in entry["pad_lengths"]:
            parts.append(str(int(p)))
            parts.append(",")
        parts.append("|")
        for v in entry["approx"]:
            parts.append(_fmt12(float(v)))
            parts.append(",")
        parts.append("|")
        for band in entry["details"]:
            for v in band:
                parts.append(_fmt12(float(v)))
                parts.append(",")
            parts.append(";")
        parts.append("#")
    return hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()


def hard_threshold(c: float, lam: float) -> float:
    return 0.0 if abs(c) <= lam else c


def hard_threshold_denoised(data_dir: Path) -> list[float]:
    """Almost-correct path: hard-keep above lambda instead of soft shrink."""
    bundle = load_bundle(data_dir)
    cfg = bundle["config"]
    policy = bundle["policy"]
    traces = bundle["traces"]
    # single-trace helper for near-lambda fixture
    t = traces[0]
    samples = [float(x) for x in t["samples"]]
    levels = clamp_levels(int(cfg["requested_levels"]), int(cfg["max_levels"]), len(samples))
    approx, details, pads = forward_pyramid(samples, levels)
    finest = details[0] if details else []
    sigma = median_abs(finest) / 0.6745
    n_ref = max(len(samples), 2)
    l0 = float(policy["mad_multiplier"]) * sigma * math.sqrt(2.0 * math.log(n_ref))
    lambdas = [l0 / (2.0 ** ((j - 1) / 2.0)) for j in range(1, levels + 1)]
    details_out = []
    for j, band in enumerate(details):
        lam = lambdas[j] if j < len(lambdas) else 0.0
        details_out.append([hard_threshold(c, lam) for c in band])
    return round_vec12(inverse_pyramid(approx, details_out, pads))

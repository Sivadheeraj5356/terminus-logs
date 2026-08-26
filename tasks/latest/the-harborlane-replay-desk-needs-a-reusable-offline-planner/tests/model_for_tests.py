#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


PLAN_COLUMNS = ["segment_id", "enabled", "threshold_param", "priority", "routing_tier"]
ACTIVE_TIERS = {"EDGE", "BULK", "DEFER"}
N_ACTIVE = 44
CPU_LIMIT = 660
MEM_LIMIT = 1060
TIER_RANGES = {"EDGE": (12, 17), "BULK": (12, 20), "DEFER": (9, 17)}
STREAM_RANGES = {"ingest": (10, 12), "ledger": (10, 12), "cache": (10, 12), "repair": (10, 12)}
TIER_STREAM_MIN = 2
THRESHOLD_BUCKET_RANGES = {"track": (16, 24), "guard": (12, 20), "quarantine": (4, 10)}
GATES = {
    "total_score": 0.880,
    "replay_score": 0.900,
    "work_score": 0.875,
    "drift_score": 0.935,
    "risk_score": 0.650,
    "balance_score": 0.920,
    "stress_score": 0.835,
}
PRIORITY_BAND_SIZE = 11
PRIORITY_BAND_TIER_RANGES = {"EDGE": (2, 5), "BULK": (2, 5), "DEFER": (2, 5)}
PRIORITY_BAND_STREAM_RANGE = (2, 4)
PRIORITY_BAND_BASIN_MIN = 5
PRIORITY_BAND_OVERLAP_MAX = 2
AFFINITY_MATCH_MIN = 30

STRESS_SCENARIOS = (
    {
        "name": "north-easterly-surge",
        "basins": {"north": 1.08, "east": 1.06, "quay": 0.95},
        "streams": {"ingest": 1.05, "repair": 0.96},
        "tiers": {"EDGE": 1.03, "BULK": 0.99, "DEFER": 0.96},
        "risk": 1.10,
        "drift": 0.98,
    },
    {
        "name": "cache-ledger-backpressure",
        "basins": {"delta": 1.06, "reef": 1.05, "gate": 0.94},
        "streams": {"cache": 1.07, "ledger": 1.04, "repair": 0.95},
        "tiers": {"EDGE": 0.97, "BULK": 1.04, "DEFER": 0.98},
        "risk": 1.06,
        "drift": 1.01,
    },
    {
        "name": "lease-rollover-shadow",
        "basins": {"west": 1.05, "lock": 1.06, "south": 0.96},
        "streams": {"repair": 1.06, "ingest": 0.97},
        "tiers": {"EDGE": 0.98, "BULK": 0.99, "DEFER": 1.05},
        "risk": 1.13,
        "drift": 0.97,
    },
)


def _p(root, path):
    return Path(root) / path.lstrip("/")


def _rows(path):
    with Path(path).open(newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _load(root):
    seg_rows = _rows(_p(root, "/var/lib/harborlane/data/segments.tsv"))
    segments = {}
    order = []
    for row in seg_rows:
        sid = row["segment_id"]
        order.append(sid)
        segments[sid] = {
            "segment_id": sid,
            "basin": row["basin"],
            "stream_class": row["stream_class"],
            "cpu": int(row["cpu"]),
            "mem": int(row["mem"]),
            "value": float(row["value"]),
            "replay": float(row["replay"]),
            "work": float(row["work"]),
            "drift": float(row["drift"]),
            "risk": float(row["risk"]),
            "threshold": float(row["threshold"]),
            "noise": float(row["noise"]),
            "overlap": row["overlap"],
            "affinity": row["affinity"],
            "lease": row["lease"],
        }
    policies = {}
    for row in _rows(_p(root, "/etc/harborlane/policy.tsv")):
        policies[row["basin"]] = (
            int(row["min_enabled"]),
            int(row["max_enabled"]),
            int(row["target_enabled"]),
        )
    conflicts = set()
    for row in _rows(_p(root, "/var/lib/harborlane/data/conflicts.tsv")):
        conflicts.add(tuple(sorted((row["left_segment"], row["right_segment"]))))
    held = set()
    for row in _rows(_p(root, "/var/cache/harborlane/state/leases.tsv")):
        if row["state"] == "held":
            held.add(row["segment_id"])
    rec_sum = defaultdict(float)
    rec_count = defaultdict(int)
    for row in _rows(_p(root, "/var/lib/harborlane/data/replay.tsv")):
        sid = row["segment_id"]
        h = float(row["heat"])
        q = float(row["pressure"])
        spicy = int(row["spicy"])
        x = (0.45 + 1.7 * h + 0.8 * q) * (1.15 if spicy else 0.72)
        if segments[sid]["affinity"] == "EDGE":
            x *= 1.09
        if segments[sid]["risk"] > 0.7 and spicy:
            x *= 1.18
        rec_sum[sid] += x
        rec_count[sid] += 1
    replay_hist = {sid: rec_sum[sid] / rec_count[sid] for sid in order}
    return order, segments, policies, conflicts, held, replay_hist


def verify_manifest(root):
    manifest = _p(root, "/var/lib/harborlane/data/MANIFEST.sha256")
    for line in manifest.read_text().splitlines():
        if not line.strip():
            continue
        digest, rel = line.split(None, 1)
        rel = rel.strip()
        actual = hashlib.sha256(_p(root, rel).read_bytes()).hexdigest()
        if actual != digest:
            return False, rel
    return True, None


def _parse_plan(plan_path, order):
    if not Path(plan_path).exists():
        return None, "missing-plan"
    with Path(plan_path).open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if reader.fieldnames != PLAN_COLUMNS:
            return None, "bad-header"
        rows = list(reader)
    if [r.get("segment_id") for r in rows] != order:
        return None, "wrong-segment-order"
    out = {}
    for row in rows:
        sid = row["segment_id"]
        try:
            enabled = int(row["enabled"])
            threshold = float(row["threshold_param"])
            priority = int(row["priority"])
        except ValueError:
            return None, f"bad-numeric-field:{sid}"
        tier = row["routing_tier"]
        if enabled not in (0, 1):
            return None, f"bad-enabled:{sid}"
        if enabled == 0:
            if threshold != 0.0 or priority != 0 or tier != "OFF":
                return None, f"disabled-row-not-zeroed:{sid}"
        else:
            if not (0.5 <= threshold <= 2.0):
                return None, f"threshold-out-of-range:{sid}"
            if priority < 1:
                return None, f"bad-priority:{sid}"
            if tier not in ACTIVE_TIERS:
                return None, f"bad-tier:{sid}"
        out[sid] = {
            "enabled": enabled,
            "threshold": threshold,
            "priority": priority,
            "tier": tier,
        }
    return out, None


def _threshold_bucket(threshold):
    if threshold <= 1.54:
        return "track"
    if threshold <= 1.64:
        return "guard"
    return "quarantine"


def _active_by_priority(plan):
    return sorted((sid for sid, row in plan.items() if row["enabled"]), key=lambda sid: plan[sid]["priority"])


def _hard(plan, segments, policies, conflicts, held):
    active = _active_by_priority(plan)
    if len(active) != N_ACTIVE:
        return False, "wrong-active-count"
    priorities = sorted(plan[sid]["priority"] for sid in active)
    if priorities != list(range(1, N_ACTIVE + 1)):
        return False, "priorities-not-contiguous"
    if sum(segments[sid]["cpu"] for sid in active) > CPU_LIMIT:
        return False, "cpu-limit"
    if sum(segments[sid]["mem"] for sid in active) > MEM_LIMIT:
        return False, "mem-limit"
    for sid in active:
        if sid in held or segments[sid]["lease"] == "held":
            return False, "held-lease-enabled"
    active_set = set(active)
    for a, b in conflicts:
        if a in active_set and b in active_set:
            return False, "conflict-pair-enabled"
    by_basin = defaultdict(int)
    by_tier = defaultdict(int)
    by_stream = defaultdict(int)
    by_tier_stream = defaultdict(int)
    by_overlap = defaultdict(int)
    by_bucket = defaultdict(int)
    for sid in active:
        by_basin[segments[sid]["basin"]] += 1
        by_tier[plan[sid]["tier"]] += 1
        by_stream[segments[sid]["stream_class"]] += 1
        by_tier_stream[(plan[sid]["tier"], segments[sid]["stream_class"])] += 1
        by_overlap[segments[sid]["overlap"]] += 1
        by_bucket[_threshold_bucket(plan[sid]["threshold"])] += 1
    for basin, (lo, hi, _target) in policies.items():
        if not (lo <= by_basin[basin] <= hi):
            return False, f"basin-window:{basin}"
    for tier, (lo, hi) in TIER_RANGES.items():
        if not (lo <= by_tier[tier] <= hi):
            return False, f"tier-window:{tier}"
    for stream, (lo, hi) in STREAM_RANGES.items():
        if not (lo <= by_stream[stream] <= hi):
            return False, f"stream-window:{stream}"
    for tier in TIER_RANGES:
        for stream in STREAM_RANGES:
            if by_tier_stream[(tier, stream)] < TIER_STREAM_MIN:
                return False, f"tier-stream-window:{tier}:{stream}"
    for bucket, (lo, hi) in THRESHOLD_BUCKET_RANGES.items():
        if not (lo <= by_bucket[bucket] <= hi):
            return False, f"threshold-bucket:{bucket}"
    if any(count > 3 for count in by_overlap.values()):
        return False, "overlap-group-overfilled"

    leading = active[:18]
    if len({segments[sid]["basin"] for sid in leading}) < 7:
        return False, "leading-band-basin-diversity"
    if len({segments[sid]["stream_class"] for sid in leading}) < 4:
        return False, "leading-band-stream-diversity"
    leading_overlap = defaultdict(int)
    leading_tier = defaultdict(int)
    for sid in leading:
        leading_overlap[segments[sid]["overlap"]] += 1
        leading_tier[plan[sid]["tier"]] += 1
    if any(count > 2 for count in leading_overlap.values()):
        return False, "leading-band-overlap-cluster"
    if not (4 <= leading_tier["EDGE"] <= 8 and 4 <= leading_tier["BULK"] <= 8 and 3 <= leading_tier["DEFER"] <= 7):
        return False, "leading-band-tier-mix"
    for sid in active:
        if segments[sid]["risk"] >= 0.86 and (plan[sid]["tier"] != "DEFER" or plan[sid]["threshold"] < 1.66):
            return False, f"high-risk-not-quarantined:{sid}"
    if sum(1 for sid in active if plan[sid]["tier"] == segments[sid]["affinity"]) < AFFINITY_MATCH_MIN:
        return False, "affinity-match-floor"
    for band_no, start in enumerate(range(0, len(active), PRIORITY_BAND_SIZE), 1):
        band = active[start : start + PRIORITY_BAND_SIZE]
        band_tier = defaultdict(int)
        band_stream = defaultdict(int)
        band_overlap = defaultdict(int)
        for sid in band:
            band_tier[plan[sid]["tier"]] += 1
            band_stream[segments[sid]["stream_class"]] += 1
            band_overlap[segments[sid]["overlap"]] += 1
        for tier, (lo, hi) in PRIORITY_BAND_TIER_RANGES.items():
            if not (lo <= band_tier[tier] <= hi):
                return False, f"priority-band-tier:{band_no}:{tier}"
        stream_lo, stream_hi = PRIORITY_BAND_STREAM_RANGE
        for stream in STREAM_RANGES:
            if not (stream_lo <= band_stream[stream] <= stream_hi):
                return False, f"priority-band-stream:{band_no}:{stream}"
        if len({segments[sid]["basin"] for sid in band}) < PRIORITY_BAND_BASIN_MIN:
            return False, f"priority-band-basin-diversity:{band_no}"
        if any(count > PRIORITY_BAND_OVERLAP_MAX for count in band_overlap.values()):
            return False, f"priority-band-overlap:{band_no}"
    return True, None


def _raw_score(plan, order, segments, policies, replay_hist, scenario=None):
    scenario = scenario or {}
    active = [sid for sid in order if plan[sid]["enabled"]]
    by_group = defaultdict(list)
    for sid in active:
        by_group[segments[sid]["overlap"]].append(sid)
    om = {}
    fade = [1.0, 0.64, 0.39, 0.23, 0.13, 0.08]
    for group_rows in by_group.values():
        group_rows.sort(key=lambda x: plan[x]["priority"])
        for idx, sid in enumerate(group_rows):
            om[sid] = fade[idx] if idx < len(fade) else 0.05
    trep = {"EDGE": 1.13, "BULK": 0.98, "DEFER": 0.77}
    twrk = {"EDGE": 0.93, "BULK": 1.07, "DEFER": 0.84}
    trsk = {"EDGE": 1.24, "BULK": 0.94, "DEFER": 0.60}
    replay = 0.0
    work = 0.0
    exposure = 0.0
    noise = 0.0
    drift_bits = []
    for sid in active:
        s = segments[sid]
        row = plan[sid]
        threshold = row["threshold"]
        tier = row["tier"]
        rank = row["priority"]
        basin_m = scenario.get("basins", {}).get(s["basin"], 1.0)
        stream_m = scenario.get("streams", {}).get(s["stream_class"], 1.0)
        tier_m = scenario.get("tiers", {}).get(tier, 1.0)
        signal_m = basin_m * stream_m * tier_m
        det = max(
            0.30,
            1.17
            - 0.295 * threshold
            - 0.07 * s["risk"]
            + (0.035 if tier == "EDGE" else 0.0)
            - (0.025 if tier == "DEFER" else 0.0),
        )
        z = 1.0 + ((int(hashlib.sha256(f"{sid}|{tier}".encode()).hexdigest()[:8], 16) % 17) - 8) / 220.0
        pr = 1.045 - min(rank, 70) * 0.0018
        replay += s["replay"] * replay_hist[sid] * det * trep[tier] * om[sid] * pr * z * signal_m
        work += (
            (s["work"] * 0.72 + s["value"] * 0.34)
            * (0.62 + 0.38 * det)
            * twrk[tier]
            * om[sid]
            * z
            * (0.72 + 0.28 * signal_m)
        )
        exposure += (
            (s["risk"] ** 1.35)
            * (0.70 + s["value"] / 240.0)
            * trsk[tier]
            * (1.0 + max(0.0, 1.5 - threshold) * 2.8)
            * scenario.get("risk", 1.0)
            * (1.0 + max(0.0, signal_m - 1.0) * 0.28)
        )
        noise += s["noise"] * max(0.0, 1.5 - threshold) * (1.0 + 1.8 * s["risk"]) * (1.2 if tier == "EDGE" else 0.75)
        drift_bits.append(
            (1.0 - abs(threshold - (1.54 + s["threshold"] * 0.28)) / 0.55)
            * (1.09 if tier == s["affinity"] else 0.93)
            * (0.75 + s["drift"] / 220.0)
            * scenario.get("drift", 1.0)
            * (0.98 + 0.02 * min(1.12, signal_m))
        )
    by_basin = defaultdict(int)
    by_group_count = defaultdict(int)
    for sid in active:
        by_basin[segments[sid]["basin"]] += 1
        by_group_count[segments[sid]["overlap"]] += 1
    basin_score = sum(
        max(0.0, 1.0 - abs(by_basin[b] - target) / (hi - lo + 1.5))
        for b, (lo, hi, target) in policies.items()
    ) / len(policies)
    group_score = sum(max(0.0, 1.0 - max(0, n - 3) * 0.18) for n in by_group_count.values()) / 18.0
    drift = (sum(drift_bits) / len(drift_bits)) * 0.58 + basin_score * 0.27 + group_score * 0.15
    replay_score = min(1.0, replay / 3850.0)
    work_score = min(1.0, work / 3100.0)
    drift_score = max(0.0, min(1.0, drift))
    risk_score = max(0.0, min(1.0, 1.05 - exposure / 34.0 - noise * 7.5))
    return {
        "replay_score": replay_score,
        "work_score": work_score,
        "drift_score": drift_score,
        "risk_score": risk_score,
        "raw_replay": replay,
        "raw_work": work,
        "raw_exposure": exposure,
        "raw_noise": noise,
    }


def _balance_score(plan, order, segments, policies):
    active = _active_by_priority(plan)
    by_stream = defaultdict(int)
    by_tier_stream = defaultdict(int)
    by_bucket = defaultdict(int)
    by_basin = defaultdict(int)
    by_group = defaultdict(int)
    for sid in active:
        stream = segments[sid]["stream_class"]
        tier = plan[sid]["tier"]
        by_stream[stream] += 1
        by_tier_stream[(tier, stream)] += 1
        by_bucket[_threshold_bucket(plan[sid]["threshold"])] += 1
        by_basin[segments[sid]["basin"]] += 1
        by_group[segments[sid]["overlap"]] += 1

    stream_score = sum(max(0.0, 1.0 - abs(by_stream[s] - 11) / 3.0) for s in STREAM_RANGES) / len(STREAM_RANGES)
    tier_stream_score = 0.0
    for tier in TIER_RANGES:
        for stream in STREAM_RANGES:
            count = by_tier_stream[(tier, stream)]
            tier_stream_score += min(1.0, count / TIER_STREAM_MIN) * max(0.0, 1.0 - max(0, count - 6) * 0.05)
    tier_stream_score /= len(TIER_RANGES) * len(STREAM_RANGES)
    bucket_score = 0.0
    for bucket, (lo, hi) in THRESHOLD_BUCKET_RANGES.items():
        target = (lo + hi) / 2.0
        bucket_score += max(0.0, 1.0 - abs(by_bucket[bucket] - target) / (hi - lo + 1.0))
    bucket_score /= len(THRESHOLD_BUCKET_RANGES)

    basin_score = sum(
        max(0.0, 1.0 - abs(by_basin[b] - target) / (hi - lo + 1.5))
        for b, (lo, hi, target) in policies.items()
    ) / len(policies)
    group_score = sum(max(0.0, 1.0 - max(0, n - 2) * 0.16) for n in by_group.values()) / 18.0

    leading = active[:18]
    leading_streams = len({segments[sid]["stream_class"] for sid in leading}) / 4.0
    leading_basins = min(1.0, len({segments[sid]["basin"] for sid in leading}) / 8.0)
    leading_groups = len({segments[sid]["overlap"] for sid in leading}) / 18.0
    leading_score = leading_streams * 0.35 + leading_basins * 0.35 + leading_groups * 0.30
    band_scores = []
    for start in range(0, len(active), PRIORITY_BAND_SIZE):
        band = active[start : start + PRIORITY_BAND_SIZE]
        band_tier = defaultdict(int)
        band_stream = defaultdict(int)
        band_overlap = defaultdict(int)
        for sid in band:
            band_tier[plan[sid]["tier"]] += 1
            band_stream[segments[sid]["stream_class"]] += 1
            band_overlap[segments[sid]["overlap"]] += 1
        tier_score = sum(
            max(0.0, 1.0 - abs(band_tier[tier] - 11.0 / 3.0) / 3.0)
            for tier in TIER_RANGES
        ) / len(TIER_RANGES)
        stream_score_band = sum(
            max(0.0, 1.0 - abs(band_stream[stream] - 11.0 / 4.0) / 2.5)
            for stream in STREAM_RANGES
        ) / len(STREAM_RANGES)
        basin_score_band = min(1.0, len({segments[sid]["basin"] for sid in band}) / 7.0)
        overlap_score_band = 1.0 if not band_overlap else max(0.0, 1.0 - max(0, max(band_overlap.values()) - 1) * 0.20)
        band_scores.append(tier_score * 0.32 + stream_score_band * 0.32 + basin_score_band * 0.22 + overlap_score_band * 0.14)
    priority_band_score = sum(band_scores) / len(band_scores)

    return (
        stream_score * 0.18
        + tier_stream_score * 0.19
        + bucket_score * 0.15
        + basin_score * 0.10
        + group_score * 0.08
        + leading_score * 0.12
        + priority_band_score * 0.18
    )


def _stress_score(plan, order, segments, policies, replay_hist):
    scenario_scores = []
    for scenario in STRESS_SCENARIOS:
        result = _raw_score(plan, order, segments, policies, replay_hist, scenario)
        scenario_scores.append(
            result["replay_score"] * 0.28
            + result["work_score"] * 0.20
            + result["drift_score"] * 0.22
            + result["risk_score"] * 0.30
        )
    return min(scenario_scores)


def _score(plan, order, segments, policies, replay_hist):
    result = _raw_score(plan, order, segments, policies, replay_hist)
    result["balance_score"] = _balance_score(plan, order, segments, policies)
    result["stress_score"] = _stress_score(plan, order, segments, policies, replay_hist)
    result["total_score"] = (
        result["replay_score"] * 0.24
        + result["work_score"] * 0.17
        + result["drift_score"] * 0.16
        + result["risk_score"] * 0.16
        + result["balance_score"] * 0.13
        + result["stress_score"] * 0.14
    )
    return result


def evaluate(root="/", plan_path=None):
    root = str(root)
    if plan_path is None:
        plan_path = _p(root, "/var/lib/harborlane/out/plan.tsv")
    ok, bad = verify_manifest(root)
    if not ok:
        return {"error": "input-integrity", "path": bad, "hard_ok": False, "passes_gate": False, "total_score": 0.0}
    order, segments, policies, conflicts, held, replay_hist = _load(root)
    plan, error = _parse_plan(plan_path, order)
    if error:
        return {"error": error, "hard_ok": False, "passes_gate": False, "total_score": 0.0}
    hard_ok, hard_error = _hard(plan, segments, policies, conflicts, held)
    if not hard_ok:
        return {"error": hard_error, "hard_ok": False, "passes_gate": False, "total_score": 0.0}
    result = _score(plan, order, segments, policies, replay_hist)
    result["hard_ok"] = True
    result["gates"] = GATES
    result["passes_gate"] = all(result[k] >= v for k, v in GATES.items())
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/")
    ap.add_argument("--plan", default=None)
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()
    result = evaluate(ns.root, ns.plan)
    if ns.json:
        print(json.dumps(result, sort_keys=True, indent=2))
    else:
        for key in [
            "hard_ok",
            "passes_gate",
            "total_score",
            "replay_score",
            "work_score",
            "drift_score",
            "risk_score",
            "balance_score",
            "stress_score",
            "error",
        ]:
            if key in result:
                print(f"{key}={result[key]}")


if __name__ == "__main__":
    main()

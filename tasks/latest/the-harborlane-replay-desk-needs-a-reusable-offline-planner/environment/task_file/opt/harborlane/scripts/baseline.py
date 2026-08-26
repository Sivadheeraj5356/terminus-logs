#!/usr/bin/env python3
import argparse
import csv
from collections import Counter
from pathlib import Path

import model


ROOT = Path("/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/var/lib/harborlane/out/plan.tsv")
    ns = ap.parse_args()
    out_path = Path(ns.out)

    order, segments, policies, conflicts, held, replay_hist = model._load(ROOT)
    clear = [sid for sid in order if sid not in held and segments[sid]["lease"] == "clear"]

    def utility(sid):
        seg = segments[sid]
        return (
            seg["replay"] * replay_hist[sid] * 0.95
            + seg["work"] * 0.65
            + seg["drift"] * 0.35
            + seg["value"] * 0.30
            - 175.0 * (seg["risk"] ** 1.35)
        )

    def conflicts_with(selected, sid):
        return any(tuple(sorted((sid, x))) in conflicts for x in selected)

    def selection_penalty(selected):
        penalty = abs(len(selected) - model.N_ACTIVE) * 1000.0
        cpu = sum(segments[sid]["cpu"] for sid in selected)
        mem = sum(segments[sid]["mem"] for sid in selected)
        penalty += max(0, cpu - model.CPU_LIMIT) * 20.0
        penalty += max(0, mem - model.MEM_LIMIT) * 10.0
        for left, right in conflicts:
            if left in selected and right in selected:
                penalty += 3000.0
        by_basin = Counter(segments[sid]["basin"] for sid in selected)
        for basin, (lo, hi, target) in policies.items():
            penalty += max(0, lo - by_basin[basin], by_basin[basin] - hi) * 800.0
            penalty += abs(by_basin[basin] - target) * 4.0
        by_stream = Counter(segments[sid]["stream_class"] for sid in selected)
        for stream, (lo, hi) in model.STREAM_RANGES.items():
            penalty += max(0, lo - by_stream[stream], by_stream[stream] - hi) * 900.0
            penalty += abs(by_stream[stream] - 11) * 10.0
        by_overlap = Counter(segments[sid]["overlap"] for sid in selected)
        for count in by_overlap.values():
            penalty += max(0, count - 3) * 500.0
        return penalty

    def selection_score(selected):
        return sum(utility(sid) for sid in selected) - selection_penalty(selected) * 100.0

    selected = set()
    for basin, (_lo, _hi, target) in policies.items():
        for sid in sorted((sid for sid in clear if segments[sid]["basin"] == basin), key=lambda x: (-utility(x), x)):
            if sum(1 for x in selected if segments[x]["basin"] == basin) >= target:
                break
            if conflicts_with(selected, sid):
                continue
            proposal = selected | {sid}
            if sum(segments[x]["cpu"] for x in proposal) <= model.CPU_LIMIT and sum(segments[x]["mem"] for x in proposal) <= model.MEM_LIMIT:
                selected = proposal
    for sid in sorted(clear, key=lambda x: (-utility(x), x)):
        if len(selected) >= model.N_ACTIVE:
            break
        if sid in selected or conflicts_with(selected, sid):
            continue
        proposal = selected | {sid}
        by_basin = Counter(segments[x]["basin"] for x in proposal)
        if (
            by_basin[segments[sid]["basin"]] <= policies[segments[sid]["basin"]][1]
            and sum(segments[x]["cpu"] for x in proposal) <= model.CPU_LIMIT
            and sum(segments[x]["mem"] for x in proposal) <= model.MEM_LIMIT
        ):
            selected = proposal

    for _phase in range(3):
        for _pass in range(80):
            best = selection_score(selected)
            improved = None
            outs = sorted(selected, key=lambda sid: (utility(sid), sid))
            inns = sorted((sid for sid in clear if sid not in selected), key=lambda sid: (-utility(sid), sid))[:100]
            for out_sid in outs:
                base = selected - {out_sid}
                for in_sid in inns:
                    if conflicts_with(base, in_sid):
                        continue
                    proposal = base | {in_sid}
                    score = selection_score(proposal)
                    if score > best + 1e-9:
                        best = score
                        improved = proposal
            if improved is None:
                break
            selected = improved

    def tier_value(sid, tier):
        seg = segments[sid]
        value = seg["replay"] * replay_hist[sid] * {"EDGE": 1.13, "BULK": 0.98, "DEFER": 0.77}[tier] * 0.65
        value += (seg["work"] * 0.72 + seg["value"] * 0.34) * {"EDGE": 0.93, "BULK": 1.07, "DEFER": 0.84}[tier] * 0.45
        value -= (seg["risk"] ** 1.35) * (0.70 + seg["value"] / 240.0) * {"EDGE": 1.24, "BULK": 0.94, "DEFER": 0.60}[tier] * 90.0
        value += 35.0 if tier == seg["affinity"] else 0.0
        if seg["risk"] >= 0.86:
            value += 500.0 if tier == "DEFER" else -10000.0
        return value

    def assign_tiers():
        targets = {"EDGE": 15, "BULK": 15, "DEFER": 14}
        tiers = {sid: "DEFER" for sid in selected if segments[sid]["risk"] >= 0.86}
        for stream in model.STREAM_RANGES:
            stream_sids = [sid for sid in selected if segments[sid]["stream_class"] == stream]
            for tier in ("EDGE", "BULK", "DEFER"):
                while sum(1 for sid in stream_sids if tiers.get(sid) == tier) < model.TIER_STREAM_MIN:
                    candidates = [
                        sid
                        for sid in stream_sids
                        if sid not in tiers and not (segments[sid]["risk"] >= 0.86 and tier != "DEFER")
                    ]
                    if not candidates:
                        candidates = [
                            sid
                            for sid in stream_sids
                            if tiers.get(sid) != tier and not (segments[sid]["risk"] >= 0.86 and tier != "DEFER")
                        ]
                    sid = max(candidates, key=lambda x: (tier_value(x, tier), x))
                    tiers[sid] = tier
        for sid in sorted((sid for sid in selected if sid not in tiers), key=lambda x: (-max(tier_value(x, t) for t in targets), x)):
            counts = Counter(tiers.values())
            available = [tier for tier in targets if counts[tier] < targets[tier]]
            tiers[sid] = max(available, key=lambda tier: (tier_value(sid, tier), tier))
        return tiers

    tiers = assign_tiers()

    buckets = {}
    for sid in selected:
        if segments[sid]["risk"] >= 0.86:
            buckets[sid] = "quarantine"
    remaining = [sid for sid in selected if sid not in buckets]
    for sid in sorted(remaining, key=lambda x: (-(segments[x]["threshold"] + segments[x]["risk"] * 0.8), utility(x), x))[: max(0, 8 - len(buckets))]:
        buckets[sid] = "quarantine"
    remaining = [sid for sid in remaining if sid not in buckets]
    for sid in sorted(remaining, key=lambda x: (-(segments[x]["replay"] * replay_hist[x] - 65.0 * segments[x]["risk"]), x))[:20]:
        buckets[sid] = "track"
    for sid in remaining:
        buckets.setdefault(sid, "guard")

    thresholds = {}
    for sid, bucket in buckets.items():
        optimum = 1.54 + segments[sid]["threshold"] * 0.28
        if bucket == "track":
            threshold = 1.52 if tiers[sid] == "EDGE" else 1.54
        elif bucket == "guard":
            threshold = min(1.64, max(1.55, optimum))
        else:
            threshold = max(1.66, min(1.78, optimum))
        if segments[sid]["risk"] >= 0.86:
            threshold = max(threshold, 1.66)
        thresholds[sid] = round(threshold + 1e-9, 2)

    def priority_value(sid, used_group):
        seg = segments[sid]
        tier = tiers[sid]
        fade = [1.0, 0.64, 0.39, 0.23, 0.13, 0.08][min(used_group, 5)]
        return utility(sid) * fade + (25.0 if tier == seg["affinity"] else 0.0)

    ranked = []
    remaining = set(selected)
    group_count = Counter()
    used_tier = Counter()
    used_stream = Counter()
    total_tier = Counter(tiers[sid] for sid in selected)
    total_stream = Counter(segments[sid]["stream_class"] for sid in selected)
    leading_tier = Counter()
    leading_stream = Counter()
    leading_basin = set()
    leading_group = Counter()
    band_tier = Counter()
    band_stream = Counter()
    band_basin = set()
    band_overlap = Counter()
    for priority in range(1, model.N_ACTIVE + 1):
        if (priority - 1) % model.PRIORITY_BAND_SIZE == 0:
            band_tier = Counter()
            band_stream = Counter()
            band_basin = set()
            band_overlap = Counter()

        def band_feasible(sid):
            tier = tiers[sid]
            stream = segments[sid]["stream_class"]
            overlap = segments[sid]["overlap"]
            slots_left = model.PRIORITY_BAND_SIZE - ((priority - 1) % model.PRIORITY_BAND_SIZE) - 1
            future_bands = (model.N_ACTIVE - priority - slots_left) // model.PRIORITY_BAND_SIZE
            tier_after = band_tier.copy()
            stream_after = band_stream.copy()
            overlap_after = band_overlap.copy()
            used_tier_after = used_tier.copy()
            used_stream_after = used_stream.copy()
            tier_after[tier] += 1
            stream_after[stream] += 1
            overlap_after[overlap] += 1
            used_tier_after[tier] += 1
            used_stream_after[stream] += 1

            if tier_after[tier] > model.PRIORITY_BAND_TIER_RANGES[tier][1]:
                return False
            if stream_after[stream] > model.PRIORITY_BAND_STREAM_RANGE[1]:
                return False
            if overlap_after[overlap] > model.PRIORITY_BAND_OVERLAP_MAX:
                return False
            if len(band_basin | {segments[sid]["basin"]}) + slots_left < model.PRIORITY_BAND_BASIN_MIN:
                return False

            tier_deficit = {
                t: max(0, model.PRIORITY_BAND_TIER_RANGES[t][0] - tier_after[t])
                for t in model.TIER_RANGES
            }
            stream_deficit = {
                s: max(0, model.PRIORITY_BAND_STREAM_RANGE[0] - stream_after[s])
                for s in model.STREAM_RANGES
            }
            if sum(tier_deficit.values()) > slots_left or sum(stream_deficit.values()) > slots_left:
                return False
            for t, (lo, hi) in model.PRIORITY_BAND_TIER_RANGES.items():
                left = total_tier[t] - used_tier_after[t]
                if left < tier_deficit[t] + future_bands * lo or left > slots_left + future_bands * hi:
                    return False
            for s in model.STREAM_RANGES:
                left = total_stream[s] - used_stream_after[s]
                if left < stream_deficit[s] + future_bands * model.PRIORITY_BAND_STREAM_RANGE[0]:
                    return False
                if left > slots_left + future_bands * model.PRIORITY_BAND_STREAM_RANGE[1]:
                    return False
            return True

        best_sid = None
        best_value = -1e30
        candidates = [sid for sid in remaining if band_feasible(sid)]
        if not candidates:
            candidates = list(remaining)
        for sid in candidates:
            value = priority_value(sid, group_count[segments[sid]["overlap"]])
            if band_tier[tiers[sid]] < model.PRIORITY_BAND_TIER_RANGES[tiers[sid]][0]:
                value += 42000.0
            if band_stream[segments[sid]["stream_class"]] < model.PRIORITY_BAND_STREAM_RANGE[0]:
                value += 36000.0
            if segments[sid]["basin"] not in band_basin and len(band_basin) < model.PRIORITY_BAND_BASIN_MIN:
                value += 12000.0
            value += 900.0 if band_overlap[segments[sid]["overlap"]] == 0 else -350.0 * band_overlap[segments[sid]["overlap"]]
            if priority <= 18:
                if leading_group[segments[sid]["overlap"]] >= 2:
                    value -= 100000.0
                if leading_tier[tiers[sid]] >= {"EDGE": 8, "BULK": 8, "DEFER": 7}[tiers[sid]]:
                    value -= 100000.0
                if leading_tier[tiers[sid]] < {"EDGE": 4, "BULK": 4, "DEFER": 3}[tiers[sid]]:
                    value += 20000.0
                if leading_stream[segments[sid]["stream_class"]] == 0:
                    value += 15000.0
                if segments[sid]["basin"] not in leading_basin and len(leading_basin) < 7:
                    value += 9000.0
            if (value, sid) > (best_value, best_sid or ""):
                best_value = value
                best_sid = sid
        ranked.append(best_sid)
        remaining.remove(best_sid)
        group_count[segments[best_sid]["overlap"]] += 1
        used_tier[tiers[best_sid]] += 1
        used_stream[segments[best_sid]["stream_class"]] += 1
        band_tier[tiers[best_sid]] += 1
        band_stream[segments[best_sid]["stream_class"]] += 1
        band_basin.add(segments[best_sid]["basin"])
        band_overlap[segments[best_sid]["overlap"]] += 1
        if priority <= 18:
            leading_tier[tiers[best_sid]] += 1
            leading_stream[segments[best_sid]["stream_class"]] += 1
            leading_basin.add(segments[best_sid]["basin"])
            leading_group[segments[best_sid]["overlap"]] += 1

    plan = {sid: {"enabled": 0, "threshold": 0.0, "priority": 0, "tier": "OFF"} for sid in order}
    for priority, sid in enumerate(ranked, 1):
        plan[sid] = {"enabled": 1, "threshold": thresholds[sid], "priority": priority, "tier": tiers[sid]}

    hard_ok, hard_error = model._hard(plan, segments, policies, conflicts, held)
    if not hard_ok:
        raise SystemExit(f"baseline could not build hard-valid bait plan: {hard_error}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=model.PLAN_COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for sid in order:
            row = plan[sid]
            writer.writerow(
                {
                    "segment_id": sid,
                    "enabled": row["enabled"],
                    "threshold_param": f"{row['threshold']:.2f}",
                    "priority": row["priority"],
                    "routing_tier": row["tier"],
                }
            )


if __name__ == "__main__":
    main()

import csv
import itertools
import math
import random
import struct
from pathlib import Path


PREDICTIONS_HEADER = [
    "record_id",
    "segment",
    "horizon_days",
    "score",
    "label",
    "calibration_band",
]
TRACE_HEADER = [
    "record_id",
    "feature_id",
    "feature_name",
    "used_missing",
    "window_index",
    "normalized",
    "linear_contribution",
]
SUMMARY_HEADER = [
    "segment",
    "record_count",
    "avg_score",
    "max_score",
    "top_record_id",
    "low_count",
    "review_count",
    "high_count",
    "calibration_bands",
    "missing_feature_count",
    "unknown_observation_count",
    "duplicate_known_observation_count",
    "dominant_feature_id",
    "dominant_feature_abs_contribution",
    "signed_zero_trace_count",
]
DIAGNOSTICS_HEADER = [
    "record_id",
    "segment",
    "horizon_days",
    "input_order",
    "raw_logit",
    "temperature",
    "raw_probability",
    "score_delta",
    "interaction_count",
    "interaction_contribution_sum",
    "top_positive_feature_id",
    "top_positive_contribution",
    "top_negative_feature_id",
    "top_negative_contribution",
]
INTERACTION_HEADER = [
    "record_id",
    "interaction_index",
    "segment_scope",
    "feature_a",
    "feature_b",
    "normalized_a",
    "normalized_b",
    "weight",
    "contribution",
]
MONOTONIC_HEADER = [
    "record_id",
    "rule_id",
    "rank",
    "pool_start_rank",
    "pool_end_rank",
    "ordering_value",
    "calibrated_score",
    "fitted_score",
    "final_score",
]
HORIZON_STABILITY_HEADER = [
    "record_id",
    "base_horizon",
    "scenario",
    "scenario_horizon",
    "scenario_rank",
    "scenario_score",
    "scenario_label",
    "score_delta",
    "rank_delta",
    "rule_id",
    "pool_start_rank",
    "pool_end_rank",
]
FEATURE_ABLATION_HEADER = [
    "feature_id",
    "record_count",
    "avg_score_delta",
    "max_abs_delta",
    "top_record_id",
    "label_flip_count",
    "rank_displacement_sum",
    "dominant_segment",
]
POLICY_FRONTIER_HEADER = [
    "budget",
    "total_alerts",
    "total_score_capture",
    "threshold_plan",
    "alert_segments",
]
RANK_CORRIDOR_HEADER = [
    "record_id",
    "base_rank",
    "best_rank",
    "worst_rank",
    "rank_span",
    "label_set",
    "dominates_count",
    "dominated_by_count",
    "longest_dominance_chain",
    "chain_terminal_record",
]
RESILIENT_FRONTIER_HEADER = [
    "budget",
    "worst_alerts",
    "max_alerts",
    "worst_score_capture",
    "avg_score_capture",
    "alert_volatility",
    "binding_scenarios",
    "threshold_plan",
]
PAIRWISE_ABLATION_HEADER = [
    "feature_a",
    "feature_b",
    "record_count",
    "avg_synergy",
    "max_abs_synergy",
    "top_record_id",
    "interaction_label_flip_count",
    "rank_synergy_sum",
    "dominant_segment",
]
OUTPUT_NAMES = [
    "predictions.csv",
    "feature_trace.csv",
    "segment_summary.csv",
    "record_diagnostics.csv",
    "interaction_trace.csv",
    "monotonic_audit.csv",
    "horizon_stability.csv",
    "feature_ablation.csv",
    "policy_frontier.csv",
    "rank_corridor.csv",
    "resilient_frontier.csv",
    "pairwise_ablation.csv",
]


def read_csv_rows(root: Path, name: str):
    with (root / "model" / name).open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, header, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def write_requests(path: Path, records) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(b"SHRC")
    data += struct.pack("<BI", 1, len(records))
    for record in records:
        observations = record["observations"]
        data += struct.pack(
            "<IBHH",
            int(record["record_id"]),
            int(record["segment"]),
            int(record["horizon_days"]),
            len(observations),
        )
        for feature_id, value in observations:
            data += struct.pack("<Hd", int(feature_id), float(value))
    path.write_bytes(data)


def read_requests(path: Path):
    data = path.read_bytes()
    offset = 0

    def take(size: int) -> bytes:
        nonlocal offset
        if offset + size > len(data):
            raise ValueError("truncated request file")
        out = data[offset : offset + size]
        offset += size
        return out

    if take(4) != b"SHRC":
        raise ValueError("bad magic")
    version = struct.unpack("<B", take(1))[0]
    if version != 1:
        raise ValueError("bad version")
    count = struct.unpack("<I", take(4))[0]
    records = []
    for _ in range(count):
        record_id, segment, horizon_days, observation_count = struct.unpack("<IBHH", take(9))
        observations = []
        for _ in range(observation_count):
            feature_id, value = struct.unpack("<Hd", take(10))
            observations.append((feature_id, value))
        records.append(
            {
                "record_id": record_id,
                "segment": segment,
                "horizon_days": horizon_days,
                "observations": observations,
            }
        )
    if offset != len(data):
        raise ValueError("trailing bytes")
    return records


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def load_model(root: Path):
    features = []
    for row in read_csv_rows(root, "features.csv"):
        features.append(
            {
                "feature_id": int(row["feature_id"]),
                "name": row["name"],
                "mean": float(row["mean"]),
                "scale": float(row["scale"]),
                "weight": float(row["weight"]),
                "missing_value": float(row["missing_value"]),
                "clip_low": float(row["clip_low"]),
                "clip_high": float(row["clip_high"]),
                "group": row["group"],
            }
        )
    features.sort(key=lambda item: item["feature_id"])

    drifts = {}
    for row in read_csv_rows(root, "feature_drifts.csv"):
        drifts[(int(row["segment"]), int(row["feature_id"]))] = float(row["per_day_delta"])

    segments = {}
    for row in read_csv_rows(root, "segments.csv"):
        segments[int(row["segment"])] = {
            "bias": float(row["bias"]),
            "temperature": float(row["temperature"]),
            "prior_logit": float(row["prior_logit"]),
        }

    windows = []
    for index, row in enumerate(read_csv_rows(root, "horizon_windows.csv")):
        windows.append(
            {
                "index": index,
                "segment": int(row["segment"]),
                "feature_id": int(row["feature_id"]),
                "min_horizon": int(row["min_horizon"]),
                "max_horizon": int(row["max_horizon"]),
                "scale_multiplier": float(row["scale_multiplier"]),
                "weight_delta": float(row["weight_delta"]),
                "missing_override": row["missing_override"],
                "gate": int(row["gate"]),
            }
        )

    interactions = []
    for index, row in enumerate(read_csv_rows(root, "interactions.csv")):
        interactions.append(
            {
                "index": index,
                "segment": int(row["segment"]),
                "feature_a": int(row["feature_a"]),
                "feature_b": int(row["feature_b"]),
                "weight": float(row["weight"]),
            }
        )

    monotonic_rules = []
    for index, row in enumerate(read_csv_rows(root, "monotonic_rules.csv")):
        monotonic_rules.append(
            {
                "index": index,
                "rule_id": int(row["rule_id"]),
                "segment": int(row["segment"]),
                "feature_id": int(row["feature_id"]),
                "min_horizon": int(row["min_horizon"]),
                "max_horizon": int(row["max_horizon"]),
                "direction": row["direction"],
                "strength": float(row["strength"]),
            }
        )

    calibration = {}
    for row in read_csv_rows(root, "calibration.csv"):
        calibration.setdefault(int(row["segment"]), []).append(
            {
                "lower": float(row["lower"]),
                "upper": float(row["upper"]),
                "multiplier": float(row["multiplier"]),
                "addend": float(row["addend"]),
            }
        )

    thresholds = read_csv_rows(root, "thresholds.csv")[0]
    return {
        "features": features,
        "drifts": drifts,
        "segments": segments,
        "windows": windows,
        "interactions": interactions,
        "monotonic_rules": monotonic_rules,
        "calibration": calibration,
        "review_threshold": float(thresholds["review_threshold"]),
        "high_threshold": float(thresholds["high_threshold"]),
    }


def first_window(model, segment: int, feature_id: int, horizon_days: int):
    for window in model["windows"]:
        if (
            window["segment"] == segment
            and window["feature_id"] == feature_id
            and window["min_horizon"] <= horizon_days < window["max_horizon"]
        ):
            return window
    return None


def isotonic_pools(values: list[float]) -> tuple[list[float], list[tuple[int, int]]]:
    blocks = []
    for index, value in enumerate(values):
        blocks.append({"start": index, "end": index, "weight": 1, "sum": value, "mean": value})
        while len(blocks) >= 2 and blocks[-2]["mean"] > blocks[-1]["mean"]:
            right = blocks.pop()
            left = blocks.pop()
            total_weight = left["weight"] + right["weight"]
            total_sum = left["sum"] + right["sum"]
            blocks.append(
                {
                    "start": left["start"],
                    "end": right["end"],
                    "weight": total_weight,
                    "sum": total_sum,
                    "mean": total_sum / total_weight,
                }
            )
    fitted = [0.0] * len(values)
    spans = [(0, 0)] * len(values)
    for block in blocks:
        for rank in range(block["start"], block["end"] + 1):
            fitted[rank] = block["mean"]
            spans[rank] = (block["start"], block["end"])
    return fitted, spans


def apply_monotonic_rules(model, scored: list[dict]) -> None:
    for row in scored:
        calibrated = row["calibrated_score"]
        row["monotonic_rule_id"] = -1
        row["monotonic_rank"] = -1
        row["monotonic_pool_start_rank"] = -1
        row["monotonic_pool_end_rank"] = -1
        row["monotonic_ordering_value"] = 0.0
        row["monotonic_fitted_score"] = calibrated
        row["score"] = calibrated

    assignments: dict[int, list[dict]] = {rule["index"]: [] for rule in model["monotonic_rules"]}
    for row in scored:
        for rule in model["monotonic_rules"]:
            if (
                rule["segment"] == row["segment"]
                and rule["min_horizon"] <= row["horizon_days"] < rule["max_horizon"]
                and rule["feature_id"] in row["normalized_by_feature"]
            ):
                row["monotonic_rule_id"] = rule["rule_id"]
                row["monotonic_ordering_value"] = row["normalized_by_feature"][rule["feature_id"]]
                assignments[rule["index"]].append(row)
                break

    for rule in model["monotonic_rules"]:
        rows = assignments[rule["index"]]
        if not rows:
            continue
        if rule["direction"] == "desc":
            rows.sort(key=lambda row: (-row["monotonic_ordering_value"], row["record_id"], row["input_order"]))
        else:
            rows.sort(key=lambda row: (row["monotonic_ordering_value"], row["record_id"], row["input_order"]))
        values = [row["calibrated_score"] for row in rows]
        fitted, spans = isotonic_pools(values)
        for rank, row in enumerate(rows):
            pool_start, pool_end = spans[rank]
            final_score = clamp(
                row["calibrated_score"] * (1.0 - rule["strength"]) + fitted[rank] * rule["strength"],
                0.0,
                1.0,
            )
            row["monotonic_rank"] = rank
            row["monotonic_pool_start_rank"] = pool_start
            row["monotonic_pool_end_rank"] = pool_end
            row["monotonic_fitted_score"] = fitted[rank]
            row["score"] = final_score


def score_records(root: Path, records: list[dict] | None = None):
    model = load_model(root)
    known_features = {feature["feature_id"] for feature in model["features"]}
    if records is None:
        records = read_requests(root / "input" / "requests.bin")

    scored = []
    for record_index, record in enumerate(records):
        segment = record["segment"]
        segment_params = model["segments"].get(segment, {"bias": 0.0, "temperature": 1.0, "prior_logit": 0.0})
        last_values = {}
        known_observation_counts = {}
        unknown_observation_count = 0
        for feature_id, value in record["observations"]:
            if feature_id in known_features:
                known_observation_counts[feature_id] = known_observation_counts.get(feature_id, 0) + 1
                last_values[feature_id] = value
            else:
                unknown_observation_count += 1
        duplicate_known_observation_count = sum(count - 1 for count in known_observation_counts.values())

        normalized_by_feature = {}
        trace_rows = []
        logit = segment_params["bias"] + segment_params["prior_logit"]
        for feature in model["features"]:
            feature_id = feature["feature_id"]
            window = first_window(model, segment, feature_id, record["horizon_days"])
            scale_multiplier = 1.0 if window is None else window["scale_multiplier"]
            weight_delta = 0.0 if window is None else window["weight_delta"]
            gate = 1 if window is None else window["gate"]
            window_index = -1 if window is None else window["index"]
            used_missing = feature_id not in last_values
            if used_missing:
                if window is not None and window["missing_override"] != "":
                    raw_value = float(window["missing_override"])
                else:
                    raw_value = feature["missing_value"]
            else:
                raw_value = last_values[feature_id]

            center = feature["mean"] + record["horizon_days"] * model["drifts"].get((segment, feature_id), 0.0)
            effective_scale = feature["scale"] * scale_multiplier
            if effective_scale == 0.0:
                normalized = 0.0
            else:
                normalized = (raw_value - center) / effective_scale
            normalized = clamp(normalized, feature["clip_low"], feature["clip_high"])
            if gate == 0:
                normalized = math.copysign(0.0, normalized)
            contribution = normalized * (feature["weight"] + weight_delta)
            normalized_by_feature[feature_id] = normalized
            logit += contribution
            trace_rows.append(
                {
                    "record_id": record["record_id"],
                    "feature_id": feature_id,
                    "feature_name": feature["name"],
                    "used_missing": 1 if used_missing else 0,
                    "window_index": window_index,
                    "normalized": normalized,
                    "linear_contribution": contribution,
                }
            )

        interaction_rows = []
        interaction_sum = 0.0
        for interaction in model["interactions"]:
            if interaction["segment"] not in {-1, segment}:
                continue
            a = normalized_by_feature.get(interaction["feature_a"], 0.0)
            b = normalized_by_feature.get(interaction["feature_b"], 0.0)
            contribution = a * b * interaction["weight"]
            interaction_sum += contribution
            logit += contribution
            interaction_rows.append(
                {
                    "record_id": record["record_id"],
                    "interaction_index": interaction["index"],
                    "segment_scope": interaction["segment"],
                    "feature_a": interaction["feature_a"],
                    "feature_b": interaction["feature_b"],
                    "normalized_a": a,
                    "normalized_b": b,
                    "weight": interaction["weight"],
                    "contribution": contribution,
                }
            )

        temperature = segment_params["temperature"] if segment_params["temperature"] != 0.0 else 1.0
        raw_probability = sigmoid(logit / temperature)
        band_index = -1
        multiplier = 1.0
        addend = 0.0
        for index, band in enumerate(model["calibration"].get(segment, [])):
            upper_match = raw_probability < band["upper"] or band["upper"] == 1.0 and raw_probability <= 1.0
            if band["lower"] <= raw_probability and upper_match:
                band_index = index
                multiplier = band["multiplier"]
                addend = band["addend"]
                break
        score = clamp(raw_probability * multiplier + addend, 0.0, 1.0)

        trace_rows.sort(key=lambda row: (-abs(row["linear_contribution"]), row["feature_id"]))
        scored.append(
            {
                "input_order": record_index,
                "record_id": record["record_id"],
                "segment": segment,
                "horizon_days": record["horizon_days"],
                "raw_logit": logit,
                "temperature": temperature,
                "raw_probability": raw_probability,
                "calibrated_score": score,
                "score": score,
                "calibration_band": band_index,
                "interaction_rows": interaction_rows,
                "interaction_sum": interaction_sum,
                "unknown_observation_count": unknown_observation_count,
                "duplicate_known_observation_count": duplicate_known_observation_count,
                "trace_rows": trace_rows,
                "normalized_by_feature": normalized_by_feature,
            }
        )

    apply_monotonic_rules(model, scored)
    for row in scored:
        if row["score"] < model["review_threshold"]:
            label = "LOW"
        elif row["score"] < model["high_threshold"]:
            label = "REVIEW"
        else:
            label = "HIGH"
        row["label"] = label
        row["score_delta"] = row["score"] - row["raw_probability"]

    scored.sort(key=lambda row: (-row["score"], row["record_id"]))
    return scored


def segment_summary_rows(scored: list[dict]) -> list[list[str]]:
    rows = []
    segments = sorted({row["segment"] for row in scored})
    for segment in segments:
        segment_records = [row for row in scored if row["segment"] == segment]
        record_count = len(segment_records)
        score_sum = sum(row["score"] for row in segment_records)
        max_score = max(row["score"] for row in segment_records)
        top_record_id = min(segment_records, key=lambda row: (-row["score"], row["record_id"]))["record_id"]
        label_counts = {
            "LOW": sum(1 for row in segment_records if row["label"] == "LOW"),
            "REVIEW": sum(1 for row in segment_records if row["label"] == "REVIEW"),
            "HIGH": sum(1 for row in segment_records if row["label"] == "HIGH"),
        }
        band_counts = {}
        feature_abs = {}
        missing_feature_count = 0
        signed_zero_trace_count = 0
        for row in segment_records:
            band = row["calibration_band"]
            band_counts[band] = band_counts.get(band, 0) + 1
            for trace in row["trace_rows"]:
                if trace["used_missing"]:
                    missing_feature_count += 1
                feature_id = trace["feature_id"]
                feature_abs[feature_id] = feature_abs.get(feature_id, 0.0) + abs(trace["linear_contribution"])
                if (
                    trace["normalized"] == 0.0
                    and math.copysign(1.0, trace["normalized"]) < 0.0
                    or trace["linear_contribution"] == 0.0
                    and math.copysign(1.0, trace["linear_contribution"]) < 0.0
                ):
                    signed_zero_trace_count += 1
        dominant_feature_id, dominant_abs = min(
            feature_abs.items(),
            key=lambda item: (-item[1], item[0]),
        )
        rows.append(
            [
                str(segment),
                str(record_count),
                f"{score_sum / record_count:.6f}",
                f"{max_score:.6f}",
                str(top_record_id),
                str(label_counts["LOW"]),
                str(label_counts["REVIEW"]),
                str(label_counts["HIGH"]),
                ";".join(f"{band}:{band_counts[band]}" for band in sorted(band_counts)),
                str(missing_feature_count),
                str(sum(row["unknown_observation_count"] for row in segment_records)),
                str(sum(row["duplicate_known_observation_count"] for row in segment_records)),
                str(dominant_feature_id),
                f"{dominant_abs:.6f}",
                str(signed_zero_trace_count),
            ]
        )
    return rows


def diagnostic_row(row: dict) -> list[str]:
    positives = [trace for trace in row["trace_rows"] if trace["linear_contribution"] > 0.0]
    negatives = [trace for trace in row["trace_rows"] if trace["linear_contribution"] < 0.0]
    if positives:
        top_positive = min(positives, key=lambda trace: (-trace["linear_contribution"], trace["feature_id"]))
        positive_id = top_positive["feature_id"]
        positive_value = top_positive["linear_contribution"]
    else:
        positive_id = -1
        positive_value = 0.0
    if negatives:
        top_negative = min(negatives, key=lambda trace: (trace["linear_contribution"], trace["feature_id"]))
        negative_id = top_negative["feature_id"]
        negative_value = top_negative["linear_contribution"]
    else:
        negative_id = -1
        negative_value = 0.0
    return [
        str(row["record_id"]),
        str(row["segment"]),
        str(row["horizon_days"]),
        str(row["input_order"]),
        f"{row['raw_logit']:.6f}",
        f"{row['temperature']:.6f}",
        f"{row['raw_probability']:.6f}",
        f"{row['score_delta']:.6f}",
        str(len(row["interaction_rows"])),
        f"{row['interaction_sum']:.6f}",
        str(positive_id),
        f"{positive_value:.6f}",
        str(negative_id),
        f"{negative_value:.6f}",
    ]


def feature_removed_records(base_records: list[dict], removed_features: set[int]) -> list[dict]:
    return [
        {
            "record_id": record["record_id"],
            "segment": record["segment"],
            "horizon_days": record["horizon_days"],
            "observations": [
                (observed_id, value)
                for observed_id, value in record["observations"]
                if observed_id not in removed_features
            ],
        }
        for record in base_records
    ]


def horizon_stability_rows(root: Path, base_scored: list[dict]) -> list[list[str]]:
    base_records = read_requests(root / "input" / "requests.bin")
    base_rank = {row["record_id"]: rank for rank, row in enumerate(base_scored)}
    base_by_id = {row["record_id"]: row for row in base_scored}
    rows = []
    scenarios = [("minus_7", -7), ("plus_7", 7)]
    for scenario_name, delta in scenarios:
        scenario_records = [
            {
                "record_id": record["record_id"],
                "segment": record["segment"],
                "horizon_days": max(0, min(60, record["horizon_days"] + delta)),
                "observations": list(record["observations"]),
            }
            for record in base_records
        ]
        scenario_scored = score_records(root, scenario_records)
        scenario_by_id = {row["record_id"]: row for row in scenario_scored}
        scenario_rank = {row["record_id"]: rank for rank, row in enumerate(scenario_scored)}
        for base in base_scored:
            scenario = scenario_by_id[base["record_id"]]
            rows.append(
                [
                    str(base["record_id"]),
                    str(base["horizon_days"]),
                    scenario_name,
                    str(scenario["horizon_days"]),
                    str(scenario_rank[base["record_id"]]),
                    f"{scenario['score']:.6f}",
                    scenario["label"],
                    f"{scenario['score'] - base_by_id[base['record_id']]['score']:.6f}",
                    str(scenario_rank[base["record_id"]] - base_rank[base["record_id"]]),
                    str(scenario["monotonic_rule_id"]),
                    str(scenario["monotonic_pool_start_rank"]),
                    str(scenario["monotonic_pool_end_rank"]),
                ]
            )
    by_record_order = {row["record_id"]: index for index, row in enumerate(base_scored)}
    scenario_order = {"minus_7": 0, "plus_7": 1}
    rows.sort(key=lambda row: (by_record_order[int(row[0])], scenario_order[row[2]]))
    return rows


def feature_ablation_rows(root: Path, base_scored: list[dict]) -> list[list[str]]:
    model = load_model(root)
    base_records = read_requests(root / "input" / "requests.bin")
    base_rank = {row["record_id"]: rank for rank, row in enumerate(base_scored)}
    base_by_id = {row["record_id"]: row for row in base_scored}
    rows = []
    for feature in model["features"]:
        feature_id = feature["feature_id"]
        scenario_records = feature_removed_records(base_records, {feature_id})
        if not scenario_records:
            rows.append([str(feature_id), "0", "0.000000", "0.000000", "-1", "0", "0", "-1"])
            continue
        scenario_scored = score_records(root, scenario_records)
        scenario_by_id = {row["record_id"]: row for row in scenario_scored}
        scenario_rank = {row["record_id"]: rank for rank, row in enumerate(scenario_scored)}
        deltas = []
        segment_abs: dict[int, float] = {}
        label_flips = 0
        rank_displacement = 0
        for base in base_scored:
            scenario = scenario_by_id[base["record_id"]]
            delta = scenario["score"] - base_by_id[base["record_id"]]["score"]
            deltas.append((base["record_id"], base["segment"], delta))
            segment_abs[base["segment"]] = segment_abs.get(base["segment"], 0.0) + abs(delta)
            label_flips += 1 if scenario["label"] != base["label"] else 0
            rank_displacement += abs(scenario_rank[base["record_id"]] - base_rank[base["record_id"]])
        avg_delta = sum(delta for _record_id, _segment, delta in deltas) / len(deltas)
        top_record_id, _top_segment, top_delta = max(
            deltas,
            key=lambda item: (abs(item[2]), item[2], -item[0]),
        )
        dominant_segment = min(segment_abs.items(), key=lambda item: (-item[1], item[0]))[0]
        rows.append(
            [
                str(feature_id),
                str(len(deltas)),
                f"{avg_delta:.6f}",
                f"{abs(top_delta):.6f}",
                str(top_record_id),
                str(label_flips),
                str(rank_displacement),
                str(dominant_segment),
            ]
        )
    return rows


def pairwise_ablation_rows(root: Path, base_scored: list[dict]) -> list[list[str]]:
    model = load_model(root)
    feature_ids = [feature["feature_id"] for feature in model["features"]]
    base_records = read_requests(root / "input" / "requests.bin")
    if not base_scored:
        return [
            [str(feature_a), str(feature_b), "0", "0.000000", "0.000000", "-1", "0", "0", "-1"]
            for feature_a, feature_b in itertools.combinations(feature_ids, 2)
        ]

    base_by_id = {row["record_id"]: row for row in base_scored}
    base_rank = {row["record_id"]: rank for rank, row in enumerate(base_scored)}
    singles = {}
    for feature_id in feature_ids:
        scored = score_records(root, feature_removed_records(base_records, {feature_id}))
        singles[feature_id] = {
            "by_id": {row["record_id"]: row for row in scored},
            "rank": {row["record_id"]: rank for rank, row in enumerate(scored)},
        }

    rows = []
    for feature_a, feature_b in itertools.combinations(feature_ids, 2):
        pair_scored = score_records(root, feature_removed_records(base_records, {feature_a, feature_b}))
        pair_by_id = {row["record_id"]: row for row in pair_scored}
        pair_rank = {row["record_id"]: rank for rank, row in enumerate(pair_scored)}
        synergies = []
        segment_abs: dict[int, float] = {}
        interaction_label_flips = 0
        rank_synergy_sum = 0
        for base in base_scored:
            record_id = base["record_id"]
            base_score = base_by_id[record_id]["score"]
            delta_a = singles[feature_a]["by_id"][record_id]["score"] - base_score
            delta_b = singles[feature_b]["by_id"][record_id]["score"] - base_score
            pair_delta = pair_by_id[record_id]["score"] - base_score
            synergy = pair_delta - delta_a - delta_b
            synergies.append((record_id, base["segment"], synergy))
            segment_abs[base["segment"]] = segment_abs.get(base["segment"], 0.0) + abs(synergy)
            if (
                pair_by_id[record_id]["label"] != base_by_id[record_id]["label"]
                and singles[feature_a]["by_id"][record_id]["label"] == base_by_id[record_id]["label"]
                and singles[feature_b]["by_id"][record_id]["label"] == base_by_id[record_id]["label"]
            ):
                interaction_label_flips += 1
            rank_interaction = (
                pair_rank[record_id]
                - base_rank[record_id]
                - (singles[feature_a]["rank"][record_id] - base_rank[record_id])
                - (singles[feature_b]["rank"][record_id] - base_rank[record_id])
            )
            rank_synergy_sum += abs(rank_interaction)
        avg_synergy = sum(synergy for _record_id, _segment, synergy in synergies) / len(synergies)
        top_record_id, _top_segment, top_synergy = max(
            synergies,
            key=lambda item: (abs(item[2]), item[2], -item[0]),
        )
        dominant_segment = min(segment_abs.items(), key=lambda item: (-item[1], item[0]))[0]
        rows.append(
            [
                str(feature_a),
                str(feature_b),
                str(len(synergies)),
                f"{avg_synergy:.6f}",
                f"{abs(top_synergy):.6f}",
                str(top_record_id),
                str(interaction_label_flips),
                str(rank_synergy_sum),
                str(dominant_segment),
            ]
        )
    return rows


def policy_frontier_rows(scored: list[dict]) -> list[list[str]]:
    segments = sorted({row["segment"] for row in scored})
    if not scored:
        return []
    candidates_by_segment = {}
    for segment in segments:
        segment_rows = [row for row in scored if row["segment"] == segment]
        thresholds = sorted({row["score"] for row in segment_rows})
        thresholds.append(1.000001)
        candidates = []
        for threshold in thresholds:
            selected = [row for row in segment_rows if row["score"] >= threshold]
            candidates.append(
                {
                    "segment": segment,
                    "threshold": threshold,
                    "alerts": len(selected),
                    "capture": sum(row["score"] for row in selected),
                }
            )
        candidates_by_segment[segment] = candidates

    plans = [{"alerts": 0, "capture": 0.0, "thresholds": {}, "segment_alerts": {}}]
    for segment in segments:
        next_plans = []
        for plan in plans:
            for candidate in candidates_by_segment[segment]:
                thresholds = dict(plan["thresholds"])
                segment_alerts = dict(plan["segment_alerts"])
                thresholds[segment] = candidate["threshold"]
                segment_alerts[segment] = candidate["alerts"]
                next_plans.append(
                    {
                        "alerts": plan["alerts"] + candidate["alerts"],
                        "capture": plan["capture"] + candidate["capture"],
                        "thresholds": thresholds,
                        "segment_alerts": segment_alerts,
                    }
                )
        plans = next_plans

    def plan_string(plan: dict) -> str:
        return ";".join(f"{segment}:{plan['thresholds'][segment]:.6f}" for segment in segments)

    rows = []
    for budget in range(len(scored) + 1):
        feasible = [plan for plan in plans if plan["alerts"] <= budget]
        best = max(
            feasible,
            key=lambda plan: (plan["capture"], plan["alerts"], tuple(-ord(ch) for ch in plan_string(plan))),
        )
        alerts_text = ";".join(
            f"{segment}:{best['segment_alerts'][segment]}"
            for segment in segments
            if best["segment_alerts"][segment] > 0
        )
        rows.append(
            [
                str(budget),
                str(best["alerts"]),
                f"{best['capture']:.6f}",
                plan_string(best),
                alerts_text,
            ]
        )
    return rows


def scenario_scored_batches(root: Path, base_scored: list[dict]) -> list[tuple[str, list[dict]]]:
    model = load_model(root)
    base_records = read_requests(root / "input" / "requests.bin")
    batches = [("base", base_scored)]

    for scenario_name, delta in (("minus_7", -7), ("plus_7", 7)):
        scenario_records = [
            {
                "record_id": record["record_id"],
                "segment": record["segment"],
                "horizon_days": max(0, min(60, record["horizon_days"] + delta)),
                "observations": list(record["observations"]),
            }
            for record in base_records
        ]
        batches.append((scenario_name, score_records(root, scenario_records)))

    for feature in model["features"]:
        feature_id = feature["feature_id"]
        scenario_records = [
            {
                "record_id": record["record_id"],
                "segment": record["segment"],
                "horizon_days": record["horizon_days"],
                "observations": [
                    (observed_id, value)
                    for observed_id, value in record["observations"]
                    if observed_id != feature_id
                ],
            }
            for record in base_records
        ]
        batches.append((f"ablated_{feature_id}", score_records(root, scenario_records)))

    return batches


def rank_corridor_rows(root: Path, base_scored: list[dict]) -> list[list[str]]:
    if not base_scored:
        return []

    batches = scenario_scored_batches(root, base_scored)
    scenario_scored = [scored for _name, scored in batches]

    rank_maps = [
        {row["record_id"]: rank for rank, row in enumerate(scored)}
        for scored in scenario_scored
    ]
    label_sets: dict[int, set[str]] = {row["record_id"]: set() for row in base_scored}
    for scored in scenario_scored:
        for row in scored:
            label_sets[row["record_id"]].add(row["label"])

    record_ids = [row["record_id"] for row in base_scored]
    edges = {record_id: [] for record_id in record_ids}
    for source in record_ids:
        for target in record_ids:
            if source != target and all(ranks[source] < ranks[target] for ranks in rank_maps):
                edges[source].append(target)
        edges[source].sort()

    chain_cache: dict[int, list[int]] = {}

    def best_chain(record_id: int) -> list[int]:
        if record_id in chain_cache:
            return chain_cache[record_id]
        best = [record_id]
        for child in edges[record_id]:
            candidate = [record_id, *best_chain(child)]
            if len(candidate) > len(best) or len(candidate) == len(best) and candidate < best:
                best = candidate
        chain_cache[record_id] = best
        return best

    label_order = {"LOW": 0, "REVIEW": 1, "HIGH": 2}
    rows = []
    for base_rank, row in enumerate(base_scored):
        record_id = row["record_id"]
        ranks = [rank_map[record_id] for rank_map in rank_maps]
        chain = best_chain(record_id)
        rows.append(
            [
                str(record_id),
                str(base_rank),
                str(min(ranks)),
                str(max(ranks)),
                str(max(ranks) - min(ranks)),
                ";".join(sorted(label_sets[record_id], key=lambda label: label_order[label])),
                str(len(edges[record_id])),
                str(sum(1 for source in record_ids if record_id in edges[source])),
                str(len(chain)),
                str(chain[-1]),
            ]
        )
    return rows


def resilient_frontier_rows(root: Path, base_scored: list[dict]) -> list[list[str]]:
    if not base_scored:
        return []

    batches = scenario_scored_batches(root, base_scored)
    segments = sorted({row["segment"] for row in base_scored})
    candidates_by_segment = {}
    for segment in segments:
        thresholds = {
            row["score"]
            for _scenario_name, scored in batches
            for row in scored
            if row["segment"] == segment
        }
        thresholds.add(1.000001)
        candidates_by_segment[segment] = sorted(thresholds)

    candidate_plans = []
    for thresholds in itertools.product(*(candidates_by_segment[segment] for segment in segments)):
        threshold_by_segment = dict(zip(segments, thresholds, strict=True))
        scenario_alerts = []
        scenario_captures = []
        for _scenario_name, scored in batches:
            alerts = 0
            capture = 0.0
            for row in scored:
                if row["score"] >= threshold_by_segment[row["segment"]]:
                    alerts += 1
                    capture += row["score"]
            scenario_alerts.append(alerts)
            scenario_captures.append(capture)
        threshold_plan = ";".join(
            f"{segment}:{threshold_by_segment[segment]:.6f}"
            for segment in segments
        )
        worst_capture = min(scenario_captures)
        candidate_plans.append(
            {
                "threshold_plan": threshold_plan,
                "worst_alerts": min(scenario_alerts),
                "max_alerts": max(scenario_alerts),
                "worst_capture": worst_capture,
                "avg_capture": sum(scenario_captures) / len(scenario_captures),
                "alert_volatility": max(scenario_alerts) - min(scenario_alerts),
                "binding_scenarios": [
                    name
                    for (name, _scored), capture in zip(batches, scenario_captures, strict=True)
                    if abs(capture - worst_capture) <= 1e-12
                ],
            }
        )

    def is_better(candidate: dict, incumbent: dict | None) -> bool:
        if incumbent is None:
            return True
        for key in ("worst_capture", "avg_capture"):
            if abs(candidate[key] - incumbent[key]) > 1e-12:
                return candidate[key] > incumbent[key]
        if candidate["worst_alerts"] != incumbent["worst_alerts"]:
            return candidate["worst_alerts"] > incumbent["worst_alerts"]
        if candidate["alert_volatility"] != incumbent["alert_volatility"]:
            return candidate["alert_volatility"] < incumbent["alert_volatility"]
        return candidate["threshold_plan"] < incumbent["threshold_plan"]

    rows = []
    for budget in range(len(base_scored) + 1):
        best = None
        for plan in candidate_plans:
            if plan["max_alerts"] <= budget and is_better(plan, best):
                best = plan
        assert best is not None
        rows.append(
            [
                str(budget),
                str(best["worst_alerts"]),
                str(best["max_alerts"]),
                f"{best['worst_capture']:.6f}",
                f"{best['avg_capture']:.6f}",
                str(best["alert_volatility"]),
                ";".join(best["binding_scenarios"]),
                best["threshold_plan"],
            ]
        )
    return rows


def render_outputs(root: Path):
    scored = score_records(root)
    prediction_lines = [",".join(PREDICTIONS_HEADER)]
    trace_lines = [",".join(TRACE_HEADER)]
    summary_lines = [",".join(SUMMARY_HEADER)]
    diagnostic_lines = [",".join(DIAGNOSTICS_HEADER)]
    interaction_lines = [",".join(INTERACTION_HEADER)]
    monotonic_lines = [",".join(MONOTONIC_HEADER)]
    horizon_lines = [",".join(HORIZON_STABILITY_HEADER)]
    ablation_lines = [",".join(FEATURE_ABLATION_HEADER)]
    frontier_lines = [",".join(POLICY_FRONTIER_HEADER)]
    corridor_lines = [",".join(RANK_CORRIDOR_HEADER)]
    resilient_lines = [",".join(RESILIENT_FRONTIER_HEADER)]
    pairwise_lines = [",".join(PAIRWISE_ABLATION_HEADER)]
    for row in scored:
        prediction_lines.append(
            ",".join(
                [
                    str(row["record_id"]),
                    str(row["segment"]),
                    str(row["horizon_days"]),
                    f"{row['score']:.6f}",
                    row["label"],
                    str(row["calibration_band"]),
                ]
            )
        )
        diagnostic_lines.append(",".join(diagnostic_row(row)))
        for trace in row["trace_rows"]:
            trace_lines.append(
                ",".join(
                    [
                        str(trace["record_id"]),
                        str(trace["feature_id"]),
                        trace["feature_name"],
                        str(trace["used_missing"]),
                        str(trace["window_index"]),
                        f"{trace['normalized']:.6f}",
                        f"{trace['linear_contribution']:.6f}",
                    ]
                )
            )
        for interaction in row["interaction_rows"]:
            interaction_lines.append(
                ",".join(
                    [
                        str(interaction["record_id"]),
                        str(interaction["interaction_index"]),
                        str(interaction["segment_scope"]),
                        str(interaction["feature_a"]),
                        str(interaction["feature_b"]),
                        f"{interaction['normalized_a']:.6f}",
                        f"{interaction['normalized_b']:.6f}",
                        f"{interaction['weight']:.6f}",
                        f"{interaction['contribution']:.6f}",
                    ]
                )
            )
        monotonic_lines.append(
            ",".join(
                [
                    str(row["record_id"]),
                    str(row["monotonic_rule_id"]),
                    str(row["monotonic_rank"]),
                    str(row["monotonic_pool_start_rank"]),
                    str(row["monotonic_pool_end_rank"]),
                    f"{row['monotonic_ordering_value']:.6f}",
                    f"{row['calibrated_score']:.6f}",
                    f"{row['monotonic_fitted_score']:.6f}",
                    f"{row['score']:.6f}",
                ]
            )
        )
    summary_lines.extend(",".join(row) for row in segment_summary_rows(scored))
    horizon_lines.extend(",".join(row) for row in horizon_stability_rows(root, scored))
    ablation_lines.extend(",".join(row) for row in feature_ablation_rows(root, scored))
    frontier_lines.extend(",".join(row) for row in policy_frontier_rows(scored))
    corridor_lines.extend(",".join(row) for row in rank_corridor_rows(root, scored))
    resilient_lines.extend(",".join(row) for row in resilient_frontier_rows(root, scored))
    pairwise_lines.extend(",".join(row) for row in pairwise_ablation_rows(root, scored))
    return {
        "predictions.csv": ("\n".join(prediction_lines) + "\n").encode(),
        "feature_trace.csv": ("\n".join(trace_lines) + "\n").encode(),
        "segment_summary.csv": ("\n".join(summary_lines) + "\n").encode(),
        "record_diagnostics.csv": ("\n".join(diagnostic_lines) + "\n").encode(),
        "interaction_trace.csv": ("\n".join(interaction_lines) + "\n").encode(),
        "monotonic_audit.csv": ("\n".join(monotonic_lines) + "\n").encode(),
        "horizon_stability.csv": ("\n".join(horizon_lines) + "\n").encode(),
        "feature_ablation.csv": ("\n".join(ablation_lines) + "\n").encode(),
        "policy_frontier.csv": ("\n".join(frontier_lines) + "\n").encode(),
        "rank_corridor.csv": ("\n".join(corridor_lines) + "\n").encode(),
        "resilient_frontier.csv": ("\n".join(resilient_lines) + "\n").encode(),
        "pairwise_ablation.csv": ("\n".join(pairwise_lines) + "\n").encode(),
    }


def write_generated_case(root: Path, seed: int, hard: bool = False) -> None:
    rng = random.Random(seed)
    model_dir = root / "model"
    input_dir = root / "input"
    output_dir = root / "output"
    model_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    feature_count = 6 + (seed % 3)
    segment_count = 3
    features = []
    for feature_id in range(1, feature_count + 1):
        scale = 0.0 if hard and feature_id == feature_count else round(0.4 + rng.random() * 3.2, 3)
        weight = round(rng.uniform(-1.1, 1.2), 3)
        features.append(
            [
                feature_id,
                f"feature_{feature_id}",
                round(rng.uniform(-3.0, 8.0), 3),
                scale,
                weight,
                round(rng.uniform(-1.0, 6.0), 3),
                round(rng.uniform(-3.5, -1.0), 3),
                round(rng.uniform(1.0, 4.5), 3),
                f"group_{feature_id % 3}",
            ]
        )
    write_csv(
        model_dir / "features.csv",
        ["feature_id", "name", "mean", "scale", "weight", "missing_value", "clip_low", "clip_high", "group"],
        features,
    )

    drifts = []
    for segment in range(segment_count):
        for feature_id in range(1, feature_count + 1):
            if (feature_id + segment + seed) % 2 == 0:
                drifts.append([segment, feature_id, round(rng.uniform(-0.08, 0.11), 4)])
    write_csv(model_dir / "feature_drifts.csv", ["segment", "feature_id", "per_day_delta"], drifts)

    segments = []
    for segment in range(segment_count):
        temperature = 0.0 if hard and segment == 1 else round(rng.uniform(0.65, 1.55), 3)
        segments.append([segment, round(rng.uniform(-0.8, 0.8), 3), temperature, round(rng.uniform(-0.4, 0.45), 3)])
    write_csv(model_dir / "segments.csv", ["segment", "bias", "temperature", "prior_logit"], segments)

    windows = []
    for segment in range(segment_count):
        for feature_id in range(1, feature_count + 1):
            if (segment * 7 + feature_id + seed) % 3 != 0:
                min_horizon = 0 if feature_id % 2 else 5
                max_horizon = 18 + (feature_id * 3) % 20
                override = "" if feature_id % 2 else round(rng.uniform(-1.5, 7.0), 3)
                gate = 0 if hard and (feature_id + segment) % 5 == 0 else 1
                windows.append(
                    [
                        segment,
                        feature_id,
                        min_horizon,
                        max_horizon,
                        round(rng.uniform(0.45, 1.9), 3),
                        round(rng.uniform(-0.45, 0.5), 3),
                        override,
                        gate,
                    ]
                )
                if hard and feature_id == 1:
                    windows.append([segment, feature_id, min_horizon + 2, max_horizon + 8, 2.75, 0.9, "", 0])
    write_csv(
        model_dir / "horizon_windows.csv",
        ["segment", "feature_id", "min_horizon", "max_horizon", "scale_multiplier", "weight_delta", "missing_override", "gate"],
        windows,
    )

    interactions = []
    for feature_id in range(1, feature_count):
        if feature_id % 2 == 1:
            interactions.append([-1, feature_id, feature_id + 1, round(rng.uniform(-0.16, 0.18), 3)])
    for segment in range(segment_count):
        interactions.append([segment, 1, feature_count, round(rng.uniform(-0.12, 0.2), 3)])
    write_csv(model_dir / "interactions.csv", ["segment", "feature_a", "feature_b", "weight"], interactions)

    monotonic_rules = []
    for segment in range(segment_count):
        direction = "asc" if segment % 2 == 0 else "desc"
        feature_id = 1 + ((seed + segment) % feature_count)
        monotonic_rules.append([100 + segment, segment, feature_id, 0, 50, direction, round(rng.uniform(0.35, 0.85), 3)])
        if hard and segment == 2:
            monotonic_rules.append([200 + segment, segment, feature_count, 8, 45, "desc", 0.65])
    write_csv(
        model_dir / "monotonic_rules.csv",
        ["rule_id", "segment", "feature_id", "min_horizon", "max_horizon", "direction", "strength"],
        monotonic_rules,
    )

    calibration = []
    for segment in range(segment_count):
        calibration.extend(
            [
                [segment, 0.0, 0.34, round(rng.uniform(0.82, 1.18), 3), round(rng.uniform(-0.04, 0.04), 3)],
                [segment, 0.34, 0.71, round(rng.uniform(0.88, 1.12), 3), round(rng.uniform(-0.03, 0.03), 3)],
                [segment, 0.71, 1.0, round(rng.uniform(0.80, 1.05), 3), round(rng.uniform(0.00, 0.08), 3)],
            ]
        )
    write_csv(model_dir / "calibration.csv", ["segment", "lower", "upper", "multiplier", "addend"], calibration)
    write_csv(model_dir / "thresholds.csv", ["review_threshold", "high_threshold"], [[0.38, 0.74]])

    records = []
    for index in range(8 + seed % 5):
        observations = []
        for feature_id in range(1, feature_count + 1):
            if rng.random() < (0.68 if hard else 0.55):
                value = round(rng.uniform(-2.0, 11.0), 4)
                observations.append((feature_id, value))
                if hard and rng.random() < 0.25:
                    observations.append((feature_id, round(value + rng.uniform(-1.2, 1.4), 4)))
        if hard or index % 3 == 0:
            observations.append((900 + index, round(rng.uniform(0.0, 5.0), 4)))
        rng.shuffle(observations)
        records.append(
            {
                "record_id": 1000 + seed * 10 + index,
                "segment": index % segment_count,
                "horizon_days": rng.randint(0, 42),
                "observations": observations,
            }
        )
    write_requests(input_dir / "requests.bin", records)


def write_outputs(root: Path) -> None:
    outputs = render_outputs(root)
    output_dir = root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, contents in outputs.items():
        (output_dir / name).write_bytes(contents)


def main() -> int:
    import sys

    if len(sys.argv) != 2:
        print("usage: calibrator.py <task_root>", file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    try:
        write_outputs(root)
    except Exception as exc:  # noqa: BLE001
        for output_name in OUTPUT_NAMES:
            (root / "output" / output_name).unlink(missing_ok=True)
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

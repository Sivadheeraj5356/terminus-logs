from __future__ import annotations

import csv
import json
import math
import subprocess
from pathlib import Path


DAYPART_ORDER = ["night", "morning", "midday", "evening"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def config(data_dir: Path) -> dict[str, object]:
    rows = {row["key"]: row["value"] for row in read_csv(data_dir / "learner_config.csv")}
    rows["alpha"] = float(rows["alpha"])
    rows["prior_strength"] = float(rows["prior_strength"])
    rows["page_hinkley_delta"] = float(rows["page_hinkley_delta"])
    rows["page_hinkley_lambda"] = float(rows["page_hinkley_lambda"])
    rows["reset_cooldown"] = int(rows["reset_cooldown"])
    rows["gap_decay"] = float(rows["gap_decay"])
    rows["probability_epsilon"] = float(rows["probability_epsilon"])
    rows["dayparts"] = rows["dayparts"].split("|")
    return rows


def initial_state(dayparts: list[str]) -> dict[str, dict[str, float]]:
    return {
        name: {
            "pos": 0.0,
            "weight": 0.0,
            "ph": 0.0,
            "resid_mean": 0.0,
            "seen": 0.0,
            "cooldown": 0.0,
        }
        for name in dayparts
    }


def probability(state: dict[str, float], cfg: dict[str, object]) -> float:
    prior = float(cfg["prior_strength"])
    return (state["pos"] + 0.5 * prior) / (state["weight"] + prior)


def process_labels(arrival_event_id, labels, pending_by_source, states, resets, windows, cfg, counters):
    if not labels:
        return
    labels = sorted(labels, key=lambda item: (int(item["source_event_id"]), int(item["arrival_event_id"])))
    eps = float(cfg["probability_epsilon"])
    alpha = float(cfg["alpha"])
    for label in labels:
        source_event_id = int(label["source_event_id"])
        pending_items = pending_by_source.pop(source_event_id, [])
        for pending in pending_items:
            sub3 = float(label["sub_metering_3_wh"])
            y = 1.0 if sub3 / pending["known_wh"] >= pending["threshold"] else 0.0
            p = pending["probability"]
            counters["labels"] += 1
            clipped = min(1.0 - eps, max(eps, p))
            brier = (p - y) ** 2
            log_loss = -(y * math.log(clipped) + (1.0 - y) * math.log(1.0 - clipped))
            for window in windows:
                if window["start"] <= source_event_id <= window["end"]:
                    window["n"] += 1
                    window["brier"] += brier
                    window["log_loss"] += log_loss

            state = states[pending["daypart"]]
            state["pos"] = (1.0 - alpha) * state["pos"] + alpha * y
            state["weight"] = (1.0 - alpha) * state["weight"] + alpha
            residual = y - p
            state["seen"] += 1.0
            state["resid_mean"] += (residual - state["resid_mean"]) / state["seen"]
            state["ph"] = max(0.0, state["ph"] + residual - state["resid_mean"] - float(cfg["page_hinkley_delta"]))
            if state["cooldown"] > 0:
                state["cooldown"] -= 1.0
            if state["ph"] > float(cfg["page_hinkley_lambda"]) and state["cooldown"] == 0:
                resets.append({"event_id": arrival_event_id, "daypart_id": pending["daypart"]})
                state["pos"] = 0.0
                state["weight"] = 0.0
                state["ph"] = 0.0
                state["resid_mean"] = 0.0
                state["seen"] = 0.0
                state["cooldown"] = float(cfg["reset_cooldown"])


def expected(data_dir: Path) -> dict[str, object]:
    cfg = config(data_dir)
    readings = read_csv(data_dir / "readings.csv")
    states = initial_state(list(cfg["dayparts"]))
    requests_by_event = {}
    for row in read_csv(data_dir / "prediction_requests.csv"):
        requests_by_event.setdefault(int(row["event_id"]), []).append(row)
    for rows in requests_by_event.values():
        rows.sort(key=lambda row: row["request_id"])
    labels_by_arrival = {}
    for row in read_csv(data_dir / "label_arrivals.csv"):
        labels_by_arrival.setdefault(int(row["arrival_event_id"]), []).append(row)
    windows = [
        {
            "window_id": row["window_id"],
            "start": int(row["start_event_id"]),
            "end": int(row["end_event_id"]),
            "n": 0,
            "brier": 0.0,
            "log_loss": 0.0,
        }
        for row in read_csv(data_dir / "score_windows.csv")
    ]
    predictions = []
    resets = []
    pending_by_source = {}
    counters = {"labels": 0}
    missing_events = 0

    for row in readings:
        event_id = int(row["event_id"])
        if row["missing_flag"] == "1":
            missing_events += 1
            for state in states.values():
                state["pos"] *= float(cfg["gap_decay"])
                state["weight"] *= float(cfg["gap_decay"])
        else:
            daypart = row["daypart_id"]
            state = states[daypart]
            known_wh = float(row["global_active_power_kw"]) * 1000.0 / 60.0
            for request in requests_by_event.get(event_id, []):
                p = probability(state, cfg)
                predictions.append({
                    "request_id": request["request_id"],
                    "event_id": event_id,
                    "probability": p,
                })
                pending_by_source.setdefault(event_id, []).append({
                    "request_id": request["request_id"],
                    "source_event_id": event_id,
                    "daypart": daypart,
                    "known_wh": known_wh,
                    "threshold": float(request["threshold_share"]),
                    "probability": p,
                })
        process_labels(event_id, labels_by_arrival.pop(event_id, []), pending_by_source, states, resets, windows, cfg, counters)

    for arrival_event_id in sorted(labels_by_arrival):
        process_labels(arrival_event_id, labels_by_arrival[arrival_event_id], pending_by_source, states, resets, windows, cfg, counters)

    return {
        "n_events": len(readings),
        "n_predictions": len(predictions),
        "n_labels": counters["labels"],
        "n_missing_events": missing_events,
        "predictions": predictions,
        "resets": resets,
        "windows": [
            {
                "window_id": window["window_id"],
                "n_scored": window["n"],
                "brier": None if window["n"] == 0 else window["brier"] / window["n"],
                "log_loss": None if window["n"] == 0 else window["log_loss"] / window["n"],
            }
            for window in windows
        ],
        "final_state": {
            "gap_events": missing_events,
            "labels_applied": counters["labels"],
            "dayparts": [
                {
                    "daypart_id": daypart,
                    "pos": states[daypart]["pos"],
                    "weight": states[daypart]["weight"],
                    "ph": states[daypart]["ph"],
                    "resid_mean": states[daypart]["resid_mean"],
                    "seen": states[daypart]["seen"],
                    "cooldown": states[daypart]["cooldown"],
                }
                for daypart in cfg["dayparts"]
            ],
        },
    }


def compile_solver() -> None:
    subprocess.run(["javac", "/app/environment/src/Solver.java"], cwd="/app/environment", check=True)


def run_solver(data_dir: Path) -> dict[str, object]:
    completed = subprocess.run(
        ["java", "-cp", "/app/environment/src", "Solver", str(data_dir)],
        cwd="/app/environment",
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"solver did not emit valid JSON: {completed.stdout!r} stderr={completed.stderr!r}") from exc

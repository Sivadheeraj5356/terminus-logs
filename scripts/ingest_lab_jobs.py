"""Ingest Harbor jobs into lab/ for frozen batches 01–05.

Never invent scores. Tasks outside the frozen tens stay rollouts=not_run
even if stray jobs exist. Timeout/infra do not count toward stump.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lab_common import (  # noqa: E402
    JOBS_DIR,
    MEASURED_BATCH_MAX,
    PLANNED_ATTEMPTS,
    build_analysis,
    collect_spend,
    collect_trials,
    coverage_matrix,
    load_all_batches,
    load_jsonl,
    model_is_oracle,
    summarize_trials,
)
from build_lab_corpus import (  # noqa: E402
    CORPUS_JS,
    CORPUS_JSON,
    JSONL as MVP_JSONL,
    enrich_overview_stats,
    hamilton_quotas,
    load_catalog,
    write_corpus,
)

RESULTS_PATH = ROOT / "docs" / "lab_measured_results.json"
LEGACY_RESULTS_PATH = ROOT / "docs" / "lab_batch_01_results.json"


def attach_rollouts(task: dict, summary: dict | None) -> dict:
    if not summary or summary.get("n_trials", 0) == 0:
        task["rollouts"] = {
            "status": "not_run",
            "label": "not run",
            "trials": [],
            "note": "No private Harbor agent trials are recorded for this package.",
        }
        task["stump_pct"] = None
        task["measured"] = False
        task["analysis"] = None
        return task
    n = summary["n_trials"]
    solved = summary["solved"]
    task["rollouts"] = {
        "status": "measured",
        "label": f"{solved}/{n} solved",
        "n_trials": n,
        "solved": solved,
        "valid_fail": summary["valid_fail"],
        "timeout": summary["timeout"],
        "infra_error": summary["infra_error"],
        "unknown": summary["unknown"],
        "completed_trials": summary["completed_trials"],
        "by_model": summary["by_model"],
        "trials": summary["traces"],
        "note": (
            f"Harbor trials: {n} — {solved} solved, {summary['valid_fail']} valid fail, "
            f"{summary['timeout']} timeout, {summary['infra_error']} infra. "
            "Timeouts and infra are excluded from stump. Denominator is recorded "
            f"trials, never padded to {PLANNED_ATTEMPTS}."
        ),
    }
    task["stump_pct"] = summary["stump_pct"]
    task["measured"] = True
    task["analysis"] = build_analysis(summary)
    return task


def classify_batch(batch: list[dict], trials: dict[str, list], jobs_dir: Path) -> list[dict]:
    reports = []
    for row in batch:
        slug = row["slug"]
        uuid = (row.get("uuid") or "").lower()
        rows = trials.get(slug) or trials.get(uuid) or []
        summary = summarize_trials(rows) if rows else None
        oracle = None
        agent_models = []
        if summary:
            for model_row in summary["by_model"]:
                name = model_row.get("model") or ""
                if model_is_oracle(name):
                    oracle = model_row
                else:
                    agent_models.append(model_row)
        reports.append(
            {
                "slug": slug,
                "uuid": row.get("uuid"),
                "batch": int(row.get("batch") or 0) or None,
                "category": row.get("category"),
                "primary_language": row.get("primary_language"),
                "has_jobs": bool(rows),
                "oracle": oracle,
                "local": summary,
                "agent_models": agent_models,
                "analysis": build_analysis(summary) if summary else None,
            }
        )
    return reports


def load_stops() -> dict[str, dict]:
    """Credit/quota stop files written by run_lab_batch. Never invent scores."""
    stops: dict[str, dict] = {}
    for n in range(1, MEASURED_BATCH_MAX + 1):
        path = ROOT / "docs" / f"lab_batch_{n:02d}_stop.json"
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            stops[str(n)] = payload
    return stops


def apply_to_corpus(corpus: dict, batch: list[dict], reports: list[dict]) -> dict:
    slug_to_batch = {r["slug"]: int(r.get("batch") or 0) or None for r in batch}
    batch_slugs = {slug for slug, n in slug_to_batch.items() if n}
    report_by_slug = {r["slug"]: r for r in reports}
    measured_slugs = {r["slug"] for r in reports if r.get("has_jobs")}
    by_batch: dict[int, list[str]] = {}
    for row in batch:
        n = int(row.get("batch") or 0)
        if n:
            by_batch.setdefault(n, []).append(row["slug"])
    for task in corpus["tasks"]:
        slug = task["slug"]
        task["batch"] = slug_to_batch.get(slug)
        if slug in batch_slugs:
            attach_rollouts(task, (report_by_slug[slug].get("local") if slug in measured_slugs else None))
        else:
            attach_rollouts(task, None)
            task["batch"] = None
    lab = corpus["lab"]
    lab["name"] = "Applied Work Worlds Lab"
    lab["measured_size"] = len(measured_slugs)
    lab["measured_target"] = MEASURED_BATCH_MAX * 10
    lab["batch_01_size"] = len(by_batch.get(1) or [])
    lab["batch_01_slugs"] = by_batch.get(1) or []
    lab["batches"] = {
        str(n): {"size": len(slugs), "slugs": slugs}
        for n, slugs in sorted(by_batch.items())
    }
    lab["measured_slugs"] = sorted(measured_slugs)
    lab["rollouts_status"] = "measured" if measured_slugs else "not_run"
    lab["runtime"] = "private Harbor 0.22 + terminus-2 / oracle"
    lab["coverage"] = coverage_matrix(corpus["tasks"], batch_slugs, measured_slugs)
    lab["protocol"] = {
        "planned_attempts": PLANNED_ATTEMPTS,
        "cheap_arms": ["anthropic/claude-haiku-4-5", "openai/gpt-4o-mini"],
        "second_arm_fallback": "anthropic/claude-sonnet-4-5",
        "frontier_archived": True,
        "note": (
            "Going-forward measure is 5 independent terminus-2 trials per cheap "
            "arm. Existing Opus 5 / gpt-5.6-sol 8-run groups stay as history and "
            "are not padded or copied from another lab."
        ),
    }
    spend_rows = collect_spend()
    stops = load_stops()
    lab["stops"] = stops
    spend_note = "Harbor stats.cost_usd from job rollups. Missing cost stays omitted, not invented."
    if stops:
        bits = []
        for key, stop in sorted(stops.items()):
            reason = stop.get("reason") or "stopped"
            bits.append(f"Batch {key.zfill(2)} stopped: {reason}")
        spend_note = " ".join(bits) + " " + spend_note
    lab["spend"] = {
        "jobs": spend_rows,
        "cost_usd_sum": round(
            sum(row["cost_usd"] for row in spend_rows if row.get("cost_usd") is not None),
            4,
        ),
        "note": spend_note,
        "stopped": bool(stops),
    }
    lab["honesty"] = {
        "stump_pct": any(t.get("stump_pct") is not None for t in corpus["tasks"]),
        "model_scores": bool(measured_slugs),
        "copied_caudal_scores": False,
        "note": (
            "Measured chips and stump % appear only for frozen batch slugs that have "
            "Harbor jobs. Other gallery rows stay not run. Timeouts and infra "
            "are excluded from stump. Caudal scores are not copied. Chips use "
            f"solved/recorded, never padded to {PLANNED_ATTEMPTS}."
        ),
    }
    if measured_slugs:
        frozen_n = len(batch_slugs)
        lab["honesty"]["note"] = (
            f"{len(measured_slugs)} of {frozen_n} frozen packages have Harbor jobs. "
            "The other gallery rows stay not run."
        )
        if stops:
            lab["honesty"]["stopped"] = True
            lab["honesty"]["note"] += (
                " Harbor stopped on credit/quota; unrun cheap fills are not scored."
            )
    harness = lab.setdefault("harness", {})
    harness.update(
        {
            "agent": "terminus-2",
            "oracle": "oracle",
            "empty": "nop",
            "harbor": "0.22",
            "planned_attempts": PLANNED_ATTEMPTS,
            "n_trials": "n_attempts × n_tasks × n_agents; CLI -k is n_attempts (independent trials)",
            "estimated_not_measured": ["claude-code", "codex", "mini-swe-agent"],
        }
    )
    enrich_overview_stats(corpus)
    return corpus


def write_corpus_files(corpus: dict) -> None:
    payload = json.dumps(corpus, ensure_ascii=False, indent=2)
    CORPUS_JSON.write_text(payload + "\n", encoding="utf-8")
    CORPUS_JS.write_text("window.AW_CORPUS = " + payload + ";\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, default=JOBS_DIR, help="Harbor jobs directory")
    parser.add_argument(
        "--batch",
        type=Path,
        default=None,
        help="optional single jsonl; default is the union of docs/lab_batch_01..05.jsonl",
    )
    args = parser.parse_args()

    if args.batch:
        batch = load_jsonl(args.batch)
        if not batch:
            raise SystemExit(f"{args.batch} is empty")
        for row in batch:
            row["batch"] = int(row.get("batch") or 1)
    else:
        batch = load_all_batches()
        if not batch:
            raise SystemExit("no docs/lab_batch_0N.jsonl files found")

    slugs = [r["slug"] for r in batch]
    uuids = [r["uuid"] for r in batch]
    if len(set(slugs)) != len(slugs) or len(set(uuids)) != len(uuids):
        raise SystemExit("frozen batches are not unique on slug or uuid")

    catalog_rows = load_catalog()
    catalog_by_slug = {r["id"]: r for r in catalog_rows}
    selected = load_jsonl(MVP_JSONL)
    inventory_counts = Counter(r.get("category") or "unknown" for r in catalog_rows)
    meta = {
        "inventory_category_counts": dict(inventory_counts),
        "quotas": hamilton_quotas(inventory_counts, 100),
        "dropped_near_duplicates": [],
    }
    corpus = write_corpus(selected, catalog_by_slug, meta)

    trials = collect_trials(args.jobs)
    reports = classify_batch(batch, trials, args.jobs)
    corpus = apply_to_corpus(corpus, batch, reports)
    write_corpus_files(corpus)

    n_jobs = sum(1 for r in reports if r["has_jobs"])
    results = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "jobs_dir": str(args.jobs),
        "frozen_n": len(batch),
        "measured_target": MEASURED_BATCH_MAX * 10,
        "planned_attempts": PLANNED_ATTEMPTS,
        "tasks": reports,
        "measured": n_jobs,
        "spend": corpus["lab"].get("spend"),
        "note": (
            "Classification only. Timeouts and infra_error are not stumps. "
            "No scores were invented for tasks without jobs."
        ),
    }
    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    batch01 = [r for r in reports if r.get("batch") == 1]
    if batch01:
        LEGACY_RESULTS_PATH.write_text(
            json.dumps(
                {
                    "generated_utc": results["generated_utc"],
                    "jobs_dir": str(args.jobs),
                    "tasks": batch01,
                    "measured": sum(1 for r in batch01 if r["has_jobs"]),
                    "note": results["note"],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    print(f"ingested jobs for {n_jobs}/{len(batch)} frozen tasks")
    print(f"wrote {CORPUS_JSON.relative_to(ROOT)}")
    print(f"wrote {RESULTS_PATH.relative_to(ROOT)}")
    for row in reports:
        local = row.get("local") or {}
        print(
            f"  b{int(row.get('batch') or 0):02d} {row['slug'][:44]:44} jobs={int(row['has_jobs'])} "
            f"n={local.get('n_trials', 0)} solved={local.get('solved', 0)} "
            f"valid_fail={local.get('valid_fail', 0)} timeout={local.get('timeout', 0)} "
            f"infra={local.get('infra_error', 0)} stump={local.get('stump_pct')}"
        )


if __name__ == "__main__":
    main()

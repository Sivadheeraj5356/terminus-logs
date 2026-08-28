"""Ingest Harbor jobs into lab/ for the frozen batch only.

Never invent scores. Tasks outside docs/lab_batch_01.jsonl stay rollouts=not_run
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
    BATCH_01_JSONL,
    JOBS_DIR,
    collect_trials,
    coverage_matrix,
    load_jsonl,
    summarize_trials,
)
from build_lab_corpus import (  # noqa: E402
    CORPUS_JS,
    CORPUS_JSON,
    JSONL as MVP_JSONL,
    hamilton_quotas,
    load_catalog,
    write_corpus,
)

RESULTS_PATH = ROOT / "docs" / "lab_batch_01_results.json"


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
            "Timeouts and infra are excluded from stump."
        ),
    }
    task["stump_pct"] = summary["stump_pct"]
    task["measured"] = True
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
                name = (model_row["model"] or "").lower()
                if "oracle" in name or model_row["model"] == "oracle":
                    oracle = model_row
                else:
                    agent_models.append(model_row)
        reports.append(
            {
                "slug": slug,
                "uuid": row.get("uuid"),
                "category": row.get("category"),
                "primary_language": row.get("primary_language"),
                "has_jobs": bool(rows),
                "oracle": oracle,
                "local": summary,
                "agent_models": agent_models,
            }
        )
    return reports


def apply_to_corpus(corpus: dict, batch: list[dict], reports: list[dict]) -> dict:
    batch_slugs = {r["slug"] for r in batch}
    report_by_slug = {r["slug"]: r for r in reports}
    measured_slugs = {r["slug"] for r in reports if r.get("has_jobs")}
    for task in corpus["tasks"]:
        slug = task["slug"]
        task["batch"] = 1 if slug in batch_slugs else None
        if slug in batch_slugs:
            attach_rollouts(task, (report_by_slug[slug].get("local") if slug in measured_slugs else None))
        else:
            # Never copy stray jobs onto the other 90.
            attach_rollouts(task, None)
            task["batch"] = None
    lab = corpus["lab"]
    lab["name"] = "Applied Work Worlds Lab"
    lab["measured_size"] = len(measured_slugs)
    lab["batch_01_size"] = len(batch_slugs)
    lab["batch_01_slugs"] = [r["slug"] for r in batch]
    lab["measured_slugs"] = sorted(measured_slugs)
    lab["rollouts_status"] = "measured" if measured_slugs else "not_run"
    lab["runtime"] = "private Harbor 0.22 + terminus-2 / oracle"
    lab["coverage"] = coverage_matrix(corpus["tasks"], batch_slugs, measured_slugs)
    lab["honesty"] = {
        "stump_pct": any(t.get("stump_pct") is not None for t in corpus["tasks"]),
        "model_scores": bool(measured_slugs),
        "copied_caudal_scores": False,
        "note": (
            "Measured chips and stump % appear only for batch-01 slugs that have "
            "Harbor jobs. The other 90 packages stay not run. Timeouts and infra "
            "are excluded from stump. Caudal scores are not copied."
        ),
    }
    if measured_slugs:
        lab["honesty"]["note"] = (
            f"{len(measured_slugs)} of 10 batch-01 packages have Harbor jobs. "
            "The other gallery rows stay not run."
        )
    return corpus


def write_corpus_files(corpus: dict) -> None:
    payload = json.dumps(corpus, ensure_ascii=False, indent=2)
    CORPUS_JSON.write_text(payload + "\n", encoding="utf-8")
    CORPUS_JS.write_text("window.AW_CORPUS = " + payload + ";\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, default=JOBS_DIR, help="Harbor jobs directory")
    parser.add_argument("--batch", type=Path, default=BATCH_01_JSONL)
    args = parser.parse_args()

    batch = load_jsonl(args.batch)
    if len(batch) != 10:
        raise SystemExit(f"{args.batch} has {len(batch)} rows, expected 10")
    slugs = [r["slug"] for r in batch]
    uuids = [r["uuid"] for r in batch]
    if len(set(slugs)) != 10 or len(set(uuids)) != 10:
        raise SystemExit("batch is not unique on slug or uuid")

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
        "tasks": reports,
        "measured": n_jobs,
        "note": (
            "Classification only. Timeouts and infra_error are not stumps. "
            "No scores were invented for tasks without jobs."
        ),
    }
    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ingested jobs for {n_jobs}/10 batch-01 tasks")
    print(f"wrote {CORPUS_JSON.relative_to(ROOT)}")
    print(f"wrote {RESULTS_PATH.relative_to(ROOT)}")
    for row in reports:
        local = row.get("local") or {}
        print(
            f"  {row['slug'][:48]:48} jobs={int(row['has_jobs'])} "
            f"n={local.get('n_trials', 0)} solved={local.get('solved', 0)} "
            f"valid_fail={local.get('valid_fail', 0)} timeout={local.get('timeout', 0)} "
            f"infra={local.get('infra_error', 0)} stump={local.get('stump_pct')}"
        )


if __name__ == "__main__":
    main()

"""Merge Harbor job results into Dropbox catalog cards."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = ROOT / "jobs"
CATALOG_DIR = ROOT / "catalog"
CARDS_DIR = CATALOG_DIR / "tasks"
JSONL_PATH = CATALOG_DIR / "tasks.jsonl"
TIMEOUT_RE = re.compile(r"timeout|timed out|AgentTimeout|VerifierTimeout", re.I)
INFRA_RE = re.compile(
    r"RuntimeError|DaytonaError|EnvironmentStart|AgentSetup|BadRequest|"
    r"RewardFileNotFound|AddTestsDir|DownloadVerifier|InfraBootstrap|InternalServer",
    re.I,
)


def classify(result: dict) -> str:
    exception = result.get("exception_info") or {}
    exc_type = str(exception.get("exception_type") or "")
    blob = f"{exc_type} {exception.get('exception_message') or ''}"
    reward = None
    rewards = ((result.get("verifier_result") or {}).get("rewards") or {})
    if "reward" in rewards:
        try:
            reward = float(rewards["reward"])
        except (TypeError, ValueError):
            reward = None
    if reward == 1.0:
        return "solved"
    if TIMEOUT_RE.search(blob) or exc_type.endswith("TimeoutError"):
        return "timeout"
    if INFRA_RE.search(blob) or exc_type:
        return "infra_error"
    if reward == 0.0:
        return "valid_fail"
    return "unknown"


def trajectory_summary(trial_dir: Path) -> str:
    candidates = [
        trial_dir / "agent" / "trajectory.json",
        trial_dir / "trajectory.json",
        trial_dir / "summary.md",
    ]
    for path in candidates:
        if path.exists() and path.suffix == ".md":
            return path.read_text(encoding="utf-8", errors="replace")[:2000]
    traj_path = next((p for p in candidates if p.name == "trajectory.json" and p.exists()), None)
    if not traj_path:
        log = trial_dir / "trial.log"
        if log.exists():
            text = log.read_text(encoding="utf-8", errors="replace")
            return collapse(text[-1500:])
        return "No trajectory.json was written for this trial."
    try:
        data = json.loads(traj_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "trajectory.json was present but not valid JSON."
    steps = []
    messages = data if isinstance(data, list) else data.get("messages") or data.get("steps") or []
    if isinstance(messages, dict):
        messages = messages.get("items") or []
    for item in messages[:12]:
        if not isinstance(item, dict):
            continue
        role = item.get("role") or item.get("type") or "step"
        content = item.get("content") or item.get("text") or item.get("message") or ""
        if isinstance(content, list):
            bits = []
            for part in content:
                if isinstance(part, dict):
                    bits.append(str(part.get("text") or part.get("content") or "")[:200])
                else:
                    bits.append(str(part)[:200])
            content = " ".join(x for x in bits if x)
        content = collapse(str(content))
        if content:
            steps.append(f"{role}: {content[:240]}")
    if not steps:
        return f"Trajectory recorded ({traj_path.name}) but no readable steps were found."
    return " | ".join(steps[:8])


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def collect_trials() -> dict[str, list[dict]]:
    by_sid: dict[str, list[dict]] = defaultdict(list)
    if not JOBS_DIR.exists():
        return by_sid
    for result_path in JOBS_DIR.rglob("result.json"):
        if result_path.parent == JOBS_DIR or result_path.name != "result.json":
            continue
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if "task_name" not in data and "trial_name" not in data:
            continue
        if result_path.parent.parent == JOBS_DIR and "n_total_trials" in data:
            continue
        task_name = str(data.get("task_name") or "")
        sid = task_name.split("/")[-1] if task_name else result_path.parent.name.split("__")[0]
        if len(sid) > 36:
            sid = sid[:36]
        agent = ((data.get("agent_info") or {}) or {}).get("name") or ""
        model = ((data.get("config") or {}).get("agent") or {}).get("model_name") or ""
        by_sid[sid].append(
            {
                "sid": sid,
                "task_name": task_name,
                "agent": agent,
                "model": model,
                "classification": classify(data),
                "exception_type": ((data.get("exception_info") or {}) or {}).get("exception_type"),
                "trial_dir": str(result_path.parent),
                "agent_summary": trajectory_summary(result_path.parent),
            }
        )
    return by_sid


def band_for(stump_pct: float | None) -> str:
    if stump_pct is None:
        return "no_logs"
    if stump_pct >= 60:
        return "stumps"
    if stump_pct >= 40:
        return "borderline"
    return "too_easy"


def main() -> None:
    if not JSONL_PATH.exists():
        raise SystemExit("catalog/tasks.jsonl missing; run build_dropbox_catalog.py first")
    trials = collect_trials()
    records = []
    with JSONL_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                records.append(json.loads(line))

    updated = 0
    for rec in records:
        sid = rec.get("sid")
        rows = trials.get(sid) or trials.get((sid or "")[:32]) or []
        if not rows:
            continue
        counts = defaultdict(int)
        by_model = defaultdict(lambda: defaultdict(int))
        summaries = []
        for row in rows:
            counts[row["classification"]] += 1
            key = row["model"] or row["agent"] or "unknown"
            by_model[key][row["classification"]] += 1
            summaries.append(row["agent_summary"])
        completed = counts["solved"] + counts["valid_fail"]
        stump = round(100.0 * counts["valid_fail"] / completed, 1) if completed else None
        rec["local"] = {
            "n_trials": len(rows),
            "solved": counts["solved"],
            "valid_fail": counts["valid_fail"],
            "timeout": counts["timeout"],
            "infra_error": counts["infra_error"],
            "unknown": counts["unknown"],
            "stump_pct": stump,
            "by_model": [
                {
                    "model": model,
                    "n": sum(c.values()),
                    "solved": c["solved"],
                    "valid_fail": c["valid_fail"],
                    "timeout": c["timeout"],
                    "infra_error": c["infra_error"],
                    "stump_pct": (
                        round(100.0 * c["valid_fail"] / (c["solved"] + c["valid_fail"]), 1)
                        if (c["solved"] + c["valid_fail"])
                        else None
                    ),
                }
                for model, c in sorted(by_model.items())
            ],
        }
        rec["stump_pct"] = stump
        rec["band"] = band_for(stump)
        rec["log_summary"] = (
            f"Harbor trials: {len(rows)} — {counts['solved']} solved, "
            f"{counts['valid_fail']} valid fail, {counts['timeout']} timeout, "
            f"{counts['infra_error']} infra."
        )
        rec["agent_summary"] = summaries[0]
        rec["stump_section"] = "\n".join(
            (
                [
                    (
                        f"- {row['model']}: {row['valid_fail']}/"
                        f"{(row['solved'] + row['valid_fail'])} valid fail "
                        f"({row['stump_pct']}%)"
                        if row["stump_pct"] is not None
                        else f"- {row['model']}: no completed trials"
                    )
                    for row in rec["local"]["by_model"]
                ]
                + [f"- Timeouts excluded: {counts['timeout']}; infra excluded: {counts['infra_error']}"]
                + [f"- Band: `{rec['band']}`"]
            )
        )
        card = CARDS_DIR / f"{rec['id']}.md"
        if card.exists():
            text = card.read_text(encoding="utf-8")
            text = re.sub(
                r"## Log summary\n\n.*?\n\n## Agent summary\n\n.*?\n\n## Stump the models\?\n\n.*\Z",
                f"## Log summary\n\n{rec['log_summary']}\n\n## Agent summary\n\n{rec['agent_summary']}\n\n## Stump the models?\n\n{rec['stump_section']}\n",
                text,
                flags=re.S,
            )
            card.write_text(text, encoding="utf-8")
        updated += 1

    with JSONL_PATH.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    n_with = sum(1 for r in records if r.get("local"))
    n_stump = sum(1 for r in records if r.get("stump_pct") is not None)
    print(
        f"updated {updated} cards from Harbor jobs; "
        f"{n_with} tasks have trials; {n_stump} have stump %"
    )
    (CATALOG_DIR / "runs.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "tasks_with_trials": n_with,
                "tasks_with_stump": n_stump,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

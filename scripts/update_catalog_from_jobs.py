"""Merge Harbor job results into catalog cards."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from lab_common import band_for, collect_trials, summarize_trials

ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = ROOT / "jobs"
CATALOG_DIR = ROOT / "catalog"
CARDS_DIR = CATALOG_DIR / "tasks"
JSONL_PATH = CATALOG_DIR / "tasks.jsonl"


def main() -> None:
    if not JSONL_PATH.exists():
        raise SystemExit("catalog/tasks.jsonl missing; run build_catalog.py first")
    trials = collect_trials(JOBS_DIR)
    records = []
    with JSONL_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                records.append(json.loads(line))

    updated = 0
    for rec in records:
        sid = rec.get("sid")
        slug = rec.get("id")
        uuid = (rec.get("uuid") or sid or "").lower()
        rows = trials.get(slug) or trials.get(sid) or trials.get(uuid) or []
        if not rows:
            continue
        summary = summarize_trials(rows)
        rec["local"] = {
            "n_trials": summary["n_trials"],
            "solved": summary["solved"],
            "valid_fail": summary["valid_fail"],
            "timeout": summary["timeout"],
            "infra_error": summary["infra_error"],
            "unknown": summary["unknown"],
            "stump_pct": summary["stump_pct"],
            "by_model": summary["by_model"],
        }
        rec["stump_pct"] = summary["stump_pct"]
        rec["band"] = band_for(summary["stump_pct"])
        rec["log_summary"] = (
            f"Harbor trials: {summary['n_trials']} — {summary['solved']} solved, "
            f"{summary['valid_fail']} valid fail, {summary['timeout']} timeout, "
            f"{summary['infra_error']} infra."
        )
        rec["agent_summary"] = (
            summary["traces"][0]["summary"] if summary["traces"] else "No trajectory summary."
        )
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
                + [
                    f"- Timeouts excluded: {summary['timeout']}; "
                    f"infra excluded: {summary['infra_error']}"
                ]
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

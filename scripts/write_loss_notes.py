"""Write per-batch cheap-protocol notes from ingested Harbor analysis.

Does not invent scores. Uses failing tests and themes already classified
by scripts/ingest_lab_jobs.py.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs" / "lab_measured_results.json"


def main() -> None:
    if not RESULTS.is_file():
        raise SystemExit(f"missing {RESULTS}; run python scripts/ingest_lab_jobs.py first")
    data = json.loads(RESULTS.read_text(encoding="utf-8"))
    by_batch: dict[int, list[dict]] = {}
    for row in data.get("tasks") or []:
        n = int(row.get("batch") or 0)
        if n:
            by_batch.setdefault(n, []).append(row)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for batch, rows in sorted(by_batch.items()):
        path = ROOT / "docs" / f"lab_batch_{batch:02d}_cheap_notes.md"
        lines = [
            f"# Batch {batch:02d} — cheap-protocol notes",
            "",
            f"**Updated:** {generated}",
            "**Protocol:** terminus-2, `-k 5`, Haiku + second cheap arm. Frontier 8-run history is separate.",
            "**Stump:** `valid_fail / (solved + valid_fail)`. Infra and timeout excluded.",
            "",
            "| Task | Oracle | Agent n | Solved | Valid fail | Infra | Timeout | Stump |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in rows:
            local = row.get("local") or {}
            oracle = row.get("oracle") or {}
            oracle_ok = "yes" if oracle.get("solved") else ("jobs" if row.get("has_jobs") else "no")
            n = local.get("n_trials") or 0
            stump = local.get("stump_pct")
            lines.append(
                f"| `{row['slug']}` | {oracle_ok} | {n} | {local.get('solved', 0)} | "
                f"{local.get('valid_fail', 0)} | {local.get('infra_error', 0)} | "
                f"{local.get('timeout', 0)} | {stump if stump is not None else '—'} |"
            )
        lines.append("")
        lines.append("## Themes (from traces + CTRF)")
        lines.append("")
        for row in rows:
            analysis = row.get("analysis") or {}
            themes = analysis.get("themes") or []
            tests = analysis.get("failing_tests") or []
            lines.append(f"### `{row['slug']}`")
            lines.append("")
            if not themes and not tests:
                lines.append("No agent analysis yet (oracle-only or not run).")
                lines.append("")
                continue
            for theme in themes[:8]:
                lines.append(f"- {theme}")
            if tests:
                lines.append("- Failing tests: " + ", ".join(f"`{t}`" for t in tests[:8]))
            lines.append("")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

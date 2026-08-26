"""Independent verifier reference math for flaky-repro CLI outputs."""

from __future__ import annotations

import json
import os
import sqlite3
from collections import defaultdict

DB_PATH = "/app/db/history.db"
LOGS_DIR = "/app/logs"
SESSION_ID = "plan-sess-alpha"


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def prepare_valid_history_rows() -> None:
    """Remove invalid sessions from test_runs so downstream milestones can grade in isolation."""
    conn = _connect()
    conn.execute(
        "DELETE FROM test_runs WHERE deleted = 1 OR parent_session_id IS NOT NULL"
    )
    conn.commit()
    conn.close()


def flaky_rows() -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        """
        SELECT
          spec_file,
          browser,
          SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS fail_count,
          SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) AS pass_count,
          COUNT(*) AS total_runs
        FROM test_runs
        WHERE deleted = 0 AND parent_session_id IS NULL
        GROUP BY spec_file, browser
        ORDER BY fail_count DESC, spec_file ASC
        """
    ).fetchall()
    conn.close()

    out = []
    for spec_file, browser, fail_count, pass_count, total_runs in rows:
        if fail_count > 0 and pass_count > 0:
            out.append(
                {
                    "spec_file": spec_file,
                    "browser": browser,
                    "fail_count": fail_count,
                    "pass_count": pass_count,
                    "total_runs": total_runs,
                }
            )
    return out


def expected_report() -> dict:
    prioritized = flaky_rows()
    by_browser: dict[str, list[dict]] = defaultdict(list)
    for row in prioritized:
        by_browser[row["browser"]].append(
            {
                "spec_file": row["spec_file"],
                "fail_count": row["fail_count"],
                "total_runs": row["total_runs"],
            }
        )

    return {
        "total_flaky_combos": len(prioritized),
        "top_flaky": [
            {
                "spec_file": row["spec_file"],
                "browser": row["browser"],
                "fail_count": row["fail_count"],
                "total_runs": row["total_runs"],
            }
            for row in prioritized
        ],
        "by_browser": dict(by_browser),
    }


def browser_projects() -> dict[str, dict]:
    conn = _connect()
    rows = conn.execute(
        """
        SELECT b.browser, b.project_name, b.worker_count, b.shard_count, b.retry_on_failure
        FROM browser_projects b
        INNER JOIN (
          SELECT browser, MAX(id) AS picked_id FROM browser_projects GROUP BY browser
        ) sel ON b.id = sel.picked_id
        """
    ).fetchall()
    conn.close()

    return {
        browser: {
            "project_name": name,
            "worker_count": workers,
            "shard_count": shards,
            "retry_on_failure": retries,
        }
        for browser, name, workers, shards, retries in rows
    }


def expected_plan(session_id: str = SESSION_ID) -> dict:
    flaky = flaky_rows()
    configs = browser_projects()
    specs_by_browser: dict[str, list[str]] = defaultdict(list)
    for entry in flaky:
        if entry["spec_file"] not in specs_by_browser[entry["browser"]]:
            specs_by_browser[entry["browser"]].append(entry["spec_file"])

    projects = []
    for browser in sorted(specs_by_browser):
        cfg = configs[browser]
        projects.append(
            {
                "name": cfg["project_name"],
                "browser": browser,
                "retries": cfg["retry_on_failure"],
                "workers": cfg["worker_count"],
                "shards": cfg["shard_count"],
                "testMatch": sorted(specs_by_browser[browser]),
            }
        )

    return {
        "session_id": session_id,
        "total_specs": len(flaky),
        "projects": projects,
    }


def pair_should_fail(spec_file: str, browser: str) -> bool:
    conn = _connect()
    rows = conn.execute(
        """
        SELECT status FROM test_runs
        WHERE spec_file = ? AND browser = ?
          AND deleted = 0 AND parent_session_id IS NULL
        """,
        (spec_file, browser),
    ).fetchall()
    conn.close()

    fail_count = sum(1 for (status,) in rows if status == "failed")
    pass_count = sum(1 for (status,) in rows if status == "passed")
    return fail_count > pass_count


def expected_execution(plan: dict | None = None) -> dict:
    if plan is None:
        plan = expected_plan()

    failures = []
    passed_count = 0
    failed_count = 0
    spec_outcomes: dict[str, dict[str, int]] = defaultdict(lambda: {"pass": 0, "fail": 0})

    for project in plan["projects"]:
        browser = project["browser"]
        retries = project["retries"]
        for spec in project["testMatch"]:
            if pair_should_fail(spec, browser):
                failed_count += 1
                spec_outcomes[spec]["fail"] += 1
                failures.append(
                    {
                        "spec_file": spec,
                        "browser": browser,
                        "retry_count": retries,
                        "status": "failed",
                    }
                )
            else:
                passed_count += 1
                spec_outcomes[spec]["pass"] += 1

    flaky_count = sum(
        1 for outcomes in spec_outcomes.values() if outcomes["pass"] > 0 and outcomes["fail"] > 0
    )

    return {
        "passed_count": passed_count,
        "failed_count": failed_count,
        "flaky_count": flaky_count,
        "failure_specs": {f["spec_file"] for f in failures},
        "failure_browsers": {f["browser"] for f in failures},
    }


def write_reference_plan(path: str | None = None) -> str:
    os.makedirs(LOGS_DIR, exist_ok=True)
    plan_path = path or os.path.join(LOGS_DIR, "plan.json")
    with open(plan_path, "w", encoding="utf-8") as handle:
        json.dump(expected_plan(), handle, indent=2)
    return plan_path


def scan_submitted_code_for_verifier_reads() -> list[str]:
    roots = ["/app/lib", "/app/cli.js"]
    forbidden = ("/tests", "/opt/verifier-reference", "test_m1.py", "test_m2.py", "test_m3.py", "reference_flaky")
    hits: list[str] = []

    for root in roots:
        paths = [root]
        if os.path.isfile(root):
            paths = [root]
        else:
            paths = []
            for dirpath, _, filenames in os.walk(root):
                for name in filenames:
                    if name.endswith(".js"):
                        paths.append(os.path.join(dirpath, name))

        for path in paths:
            with open(path, encoding="utf-8", errors="ignore") as handle:
                content = handle.read()
            for token in forbidden:
                if token in content:
                    hits.append(f"{path} contains {token}")
    return hits

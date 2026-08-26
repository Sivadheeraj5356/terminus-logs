"""Merge per-bundle CTRF reports into /logs/verifier/ctrf.json.

Usage: merge_ctrf.py <output.json> <input1.json> [<input2.json> ...]
Later phases must not overwrite earlier results; this merges all test entries.
"""

import json
import sys


def main():
    out_path, in_paths = sys.argv[1], sys.argv[2:]
    tests, tools = [], set()
    summary = {
        "tests": 0,
        "passed": 0,
        "failed": 0,
        "pending": 0,
        "skipped": 0,
        "other": 0,
        "start": 0,
        "stop": 0,
    }
    for p in in_paths:
        try:
            with open(p) as f:
                doc = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        res = doc.get("results", {})
        tools.add(res.get("tool", {}).get("name", "pytest"))
        tests.extend(res.get("tests", []))
        s = res.get("summary", {})
        for key in ("tests", "passed", "failed", "pending", "skipped", "other"):
            summary[key] += int(s.get(key, 0))
        summary["start"] = min(
            filter(None, [summary["start"], s.get("start", 0)]), default=0
        )
        summary["stop"] = max(summary["stop"], int(s.get("stop", 0)))
    merged = {
        "results": {
            "tool": {"name": ",".join(sorted(tools)) or "pytest"},
            "summary": summary,
            "tests": tests,
        }
    }
    with open(out_path, "w") as f:
        json.dump(merged, f)
    print(
        f"merged {len(in_paths)} CTRF files: {summary['tests']} tests, "
        f"{summary['passed']} passed, {summary['failed']} failed"
    )


if __name__ == "__main__":
    main()

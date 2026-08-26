from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Params:
    wave_count: int
    max_actions_per_wave: int
    max_total_review_minutes: int
    min_distinct_owners: int
    min_preserved_evidence_points: int


def parse_case(path: str | Path) -> dict:
    path = Path(path)
    params = {}
    rows: dict[str, list[list[str]]] = {
        "SCENARIO": [],
        "APPROVAL": [],
        "HOST": [],
        "IDENTITY": [],
        "FOOTHOLD": [],
        "EDGE": [],
        "CROWN": [],
        "WORKFLOW": [],
        "EVIDENCE": [],
    }
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "PARAM":
            params[parts[1]] = int(parts[2]) if parts[1] != "file_version" else parts[2]
        else:
            rows[parts[0]].append(parts[1:])
    rows["PARAM"] = [params]
    return rows


def load_schedule(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    base = Path("/app/task_file")
    case = parse_case(base / "scan_input" / "incident_case.txt")
    schedule = load_schedule(base / "output" / "containment_schedule.json")
    print(
        json.dumps(
            {
                "case_rows": {k: len(v) for k, v in case.items() if k != "PARAM"},
                "top_level_keys": sorted(schedule),
            },
            indent=2,
        )
    )

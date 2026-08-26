#!/usr/bin/env python3
"""Compare independent recompute vs gen_fixtures walk for practice."""
import json
import sys
from pathlib import Path

ENV = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENV / "ci"))
from gen_fixtures import walk  # noqa: E402

allow = {
    line.strip()
    for line in (ENV / "data" / "region_codes.txt").read_text().splitlines()
    if line.strip()
}
practice = ENV / "fixtures" / "practice"
print(json.dumps(walk(practice, 7, region_allow=allow), indent=2))

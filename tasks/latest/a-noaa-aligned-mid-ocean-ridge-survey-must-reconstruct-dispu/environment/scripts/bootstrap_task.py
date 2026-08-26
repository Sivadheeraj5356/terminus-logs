#!/usr/bin/env python3
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dive_fixture_encode import (
    build_alpha_reports, build_alpha_observations,
    build_beta_reports, build_beta_observations, write_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
dives = ROOT / "data" / "dives"
dives.mkdir(parents=True, exist_ok=True)
write_bundle(dives / "alpha.dive.json", "expedition-alpha",
             build_alpha_reports(), build_alpha_observations())
write_bundle(dives / "beta.dive.json", "expedition-beta",
             build_beta_reports(), build_beta_observations())
corpus = ROOT / "data" / "corpus"
corpus.mkdir(parents=True, exist_ok=True)
(corpus / "manifest.json").write_text(
    json.dumps({"bundles": ["alpha.dive.json", "beta.dive.json"]}) + "\n")
print("bootstrap ok")

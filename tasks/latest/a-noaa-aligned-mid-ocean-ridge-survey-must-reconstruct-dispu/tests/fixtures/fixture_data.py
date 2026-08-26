"""Shared paths for expeditctl verifier tests."""
from pathlib import Path

BINARY = Path("/app/target/release/expeditctl")
ALPHA = Path("/app/data/dives/alpha.dive.json")
BETA = Path("/app/data/dives/beta.dive.json")
POLICY_DEFAULT = Path("/app/data/policies/default.json")
HIDDEN_SIGMA = Path("/opt/verifier-fixtures/dives/sigma.dive.json")
HIDDEN_SIGMA_BOM = Path("/opt/verifier-fixtures/dives/sigma_bom.dive.json")
HIDDEN_OMEGA = Path("/opt/verifier-fixtures/dives/omega.dive.json")
HIDDEN_TIE = Path("/opt/verifier-fixtures/dives/tie.dive.json")
HIDDEN_KAPPA = Path("/opt/verifier-fixtures/dives/kappa.dive.json")

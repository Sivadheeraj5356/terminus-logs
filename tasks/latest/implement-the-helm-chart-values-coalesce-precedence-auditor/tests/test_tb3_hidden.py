"""TB3 hidden traps — bundled /opt/verifier-fixtures only."""

import json
import subprocess
from pathlib import Path

BIN = Path("/app/bin/helmvals")
FIXTURES = Path("/opt/verifier-fixtures")


def run_fixture(case_name, tmp_path, set_args=()):
    root = FIXTURES / "charts" / case_name
    out = tmp_path / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(BIN), "resolve", "--chart", str(root), "--out", str(out)]
    for s in set_args:
        cmd.extend(["--set", s])
    subprocess.run(cmd, check=True)
    return json.loads(out.read_text())


def test_TB3_ALIAS_GLOBAL_merges_global_into_cache():
    """TB3_ALIAS_GLOBAL must propagate parent global into aliased cache chart."""
    result = run_fixture("TB3_ALIAS_GLOBAL", Path("/tmp/tb3-alias"))
    assert "cache" in result["active_charts"]
    assert result["values"]["cache"]["global"]["tier"] == "prod"
    assert result["values"]["cache"]["global"]["region"] == "local"


def test_TB3_FALSE_CONDITION_excludes_metrics():
    """TB3_FALSE_CONDITION must exclude metrics when metrics.enabled is false."""
    result = run_fixture("TB3_FALSE_CONDITION", Path("/tmp/tb3-false"))
    assert result["active_charts"] == ["stack"]
    assert "metrics" not in result["values"]


def test_TB3_SET_ESCAPE_literal_dot_key(tmp_path):
    """TB3_SET_ESCAPE must honor escaped dotted --set keys on root chart."""
    result = run_fixture("TB3_SET_ESCAPE", tmp_path, set_args=[r"outer\.inner=9"])
    assert result["values"]["edge"]["outer.inner"] == 9

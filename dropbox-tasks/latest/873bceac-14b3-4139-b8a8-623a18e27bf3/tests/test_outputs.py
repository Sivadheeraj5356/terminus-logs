"""RelicMaze resolver verification.

The Node/npm verifier compiles the agent's Java library and resolves every
scenario against the live PostgreSQL database in a single batch, capturing each
canonical narration and action list. This module asserts those captures match
the golden files byte-for-byte.

Two families of scenarios are checked. The curated scenarios each target a
specific rule interaction and are asserted individually. The randomized battery
(scenario ids beginning with ``g``) is a large, deterministically generated set
of capsules and transcripts covering the full input space; it is asserted in
batches so that a resolver correct only on the common cases is not enough.
"""
import glob
import json
import os
import subprocess

import pytest

FIXTURE_DIR = "/tests/fixtures"
RESULTS_PATH = "/tmp/relicmaze_results.json"
BATCH_SIZE = 5

_ALL = sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(FIXTURE_DIR, "*.json")))
CURATED = [n for n in _ALL if not n.startswith("g")]
RANDOM = [n for n in _ALL if n.startswith("g")]
BATCHES = [RANDOM[i:i + BATCH_SIZE] for i in range(0, len(RANDOM), BATCH_SIZE)]


@pytest.fixture(scope="session")
def results():
    """Run the batch verifier once and return its per-scenario report."""
    subprocess.run(["node", "/tests/verifier/run.js"], check=False)
    assert os.path.exists(RESULTS_PATH), "verifier did not produce a results file"
    with open(RESULTS_PATH) as fh:
        return json.load(fh)


def _detail(name, record):
    return (
        f"scenario '{name}' did not match its golden output.\n"
        f"--- error ---\n{record.get('error')}\n"
        f"--- expected ---\n{record.get('expected')}\n"
        f"--- actual ---\n{record.get('actual')}\n"
    )


@pytest.mark.parametrize("name", CURATED)
def test_curated_scenario(results, name):
    """A curated scenario matches its golden narration, route, and actions exactly."""
    assert name in results, f"verifier produced no result for scenario '{name}'"
    if not results[name]["pass"]:
        pytest.fail(_detail(name, results[name]))


@pytest.mark.parametrize("batch", range(len(BATCHES)), ids=[f"batch{i:02d}" for i in range(len(BATCHES))])
def test_random_battery(results, batch):
    """Every scenario in this randomized batch matches its golden output exactly."""
    failures = [n for n in BATCHES[batch] if not results.get(n, {}).get("pass")]
    if failures:
        first = failures[0]
        pytest.fail(
            f"{len(failures)} randomized scenario(s) failed: {failures}\n"
            + _detail(first, results.get(first, {}))
        )

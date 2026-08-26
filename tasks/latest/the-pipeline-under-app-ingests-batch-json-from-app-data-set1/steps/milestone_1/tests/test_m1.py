import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

APP = "/app"
PIPELINE_BIN = f"{APP}/target/release/pipeline"
CANONICAL_KEY = "set1_set2_set3"
CANONICAL_HISTORY = ["set1", "set2", "set3"]
PROBE_VECTORS = {1: [1.0, 2.0, 3.0], 2: [1.5, 2.5, 3.5]}


def _cargo_env():
    env = os.environ.copy()
    env["PATH"] = "/usr/local/cargo/bin:" + env.get("PATH", "")
    env.setdefault("CARGO_HOME", "/usr/local/cargo")
    env.setdefault("RUSTUP_HOME", "/usr/local/rustup")
    return env


@pytest.fixture(scope="module")
def built_pipeline():
    res = subprocess.run(
        ["cargo", "build", "--release", "--bin", "pipeline"],
        cwd=APP,
        capture_output=True,
        text=True,
        env=_cargo_env(),
    )
    if res.returncode != 0:
        raise AssertionError(f"cargo build --release failed:\n{res.stderr}")
    return PIPELINE_BIN


def run_pipeline(built_pipeline, states="data/", output="artifacts/"):
    res = subprocess.run(
        [built_pipeline, "--states", states, "--output", output],
        cwd=APP,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise AssertionError(f"Pipeline failed: {res.stderr}")
    return res


def _load_provenance():
    with open("artifacts/provenance.json") as f:
        return json.load(f)


def _chain(prov, group_id):
    return next(c for c in prov["chains"] if c["group_id"] == group_id)


class TestMilestone1:
    def test_accumulation_retains_prior_sources(self, built_pipeline):
        """History accumulates every batch source and key is the sorted join."""
        run_pipeline(built_pipeline)
        prov = _load_provenance()

        group_ids = sorted(chain["group_id"] for chain in prov["chains"])
        assert group_ids == ["G1", "G2"]

        for chain in prov["chains"]:
            hist = chain["history"]
            assert len(hist) == 3
            assert set(hist) == {"set1", "set2", "set3"}
            assert chain["key"] == CANONICAL_KEY

    def test_prediction_schema(self, built_pipeline):
        """Each state block has two probes; set1 uses single-source scale."""
        run_pipeline(built_pipeline)
        assert os.path.exists("artifacts/predictions.json")

        with open("artifacts/predictions.json") as f:
            pred = json.load(f)

        assert sorted(pred.keys()) == ["set1", "set2", "set3"]
        for state_name in ["set1", "set2", "set3"]:
            assert len(pred[state_name]) == 2
            assert sorted(r["probe_id"] for r in pred[state_name]) == [1, 2]

        for record in pred["set1"]:
            assert record["key"] == "set1"
            want = sum(PROBE_VECTORS[record["probe_id"]]) * 1.0
            assert record["value"] == pytest.approx(want)

    def test_g1_history_sorted_emission(self, built_pipeline):
        """G1 provenance history is emitted in sorted tag order."""
        run_pipeline(built_pipeline)
        assert _chain(_load_provenance(), "G1")["history"] == CANONICAL_HISTORY

    def test_g2_history_sorted_emission(self, built_pipeline):
        """G2 provenance history is emitted in sorted tag order."""
        run_pipeline(built_pipeline)
        assert _chain(_load_provenance(), "G2")["history"] == CANONICAL_HISTORY

    def test_provenance_lists_state_order(self, built_pipeline):
        """Provenance states list reflects batch processing order."""
        run_pipeline(built_pipeline)
        assert _load_provenance()["states"] == ["set1", "set2", "set3"]

    def test_g1_key_matches_sorted_join(self, built_pipeline):
        """G1 key equals underscore-join of sorted history tags."""
        run_pipeline(built_pipeline)
        chain = _chain(_load_provenance(), "G1")
        assert chain["key"] == "_".join(sorted(chain["history"]))

    def test_g2_key_matches_sorted_join(self, built_pipeline):
        """G2 key equals underscore-join of sorted history tags."""
        run_pipeline(built_pipeline)
        chain = _chain(_load_provenance(), "G2")
        assert chain["key"] == "_".join(sorted(chain["history"]))

    def test_set1_probe1_value_six(self, built_pipeline):
        """set1 probe 1 uses scale 1.0 yielding value 6.0."""
        run_pipeline(built_pipeline)
        with open("artifacts/predictions.json") as f:
            pred = json.load(f)
        rec = next(r for r in pred["set1"] if r["probe_id"] == 1)
        assert rec["value"] == pytest.approx(6.0)

    def test_set1_probe2_value_seven_half(self, built_pipeline):
        """set1 probe 2 uses scale 1.0 yielding value 7.5."""
        run_pipeline(built_pipeline)
        with open("artifacts/predictions.json") as f:
            pred = json.load(f)
        rec = next(r for r in pred["set1"] if r["probe_id"] == 2)
        assert rec["value"] == pytest.approx(7.5)

    def test_single_batch_set1_isolated(self, built_pipeline):
        """Single-batch run keeps history and key at set1 only."""
        with tempfile.TemporaryDirectory() as td:
            states = Path(td) / "states"
            out = Path(td) / "out"
            states.mkdir()
            out.mkdir()
            shutil.copy("data/set1.json", states / "set1.json")
            shutil.copy("data/vals1.csv", states / "vals1.csv")
            run_pipeline(built_pipeline, states=str(states) + "/", output=str(out) + "/")
            with open(out / "provenance.json") as f:
                prov = json.load(f)
            for chain in prov["chains"]:
                assert chain["history"] == ["set1"]
                assert chain["key"] == "set1"

    def test_chain_history_has_no_duplicate_tags(self, built_pipeline):
        """Accumulated history contains no duplicate source tags."""
        run_pipeline(built_pipeline)
        for chain in _load_provenance()["chains"]:
            assert len(chain["history"]) == len(set(chain["history"]))

    def test_both_groups_emit_canonical_key(self, built_pipeline):
        """Both probe groups emit the fully accumulated canonical key."""
        run_pipeline(built_pipeline)
        keys = {c["group_id"]: c["key"] for c in _load_provenance()["chains"]}
        assert keys["G1"] == CANONICAL_KEY
        assert keys["G2"] == CANONICAL_KEY

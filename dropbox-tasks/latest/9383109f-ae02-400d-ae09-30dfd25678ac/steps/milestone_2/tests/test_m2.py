import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

APP = "/app"
PIPELINE_BIN = f"{APP}/target/release/pipeline"
CANONICAL_KEY = "set1_set2_set3"
CANONICAL_HISTORY = ["set1", "set2", "set3"]
PROBE_VECTORS = {1: [1.0, 2.0, 3.0], 2: [1.5, 2.5, 3.5]}
DEPTH_SCALES = {"set1": 1.0, "set2": 2.0, "set3": 4.0}
DEPTH_KEYS = {"set1": "set1", "set2": "set1_set2", "set3": CANONICAL_KEY}
EXTRA_PERMUTATIONS = [
    ["set3", "set1", "set2"],
    ["set2", "set3", "set1"],
    ["set1", "set3", "set2"],
]


def _cargo_env():
    env = os.environ.copy()
    env["PATH"] = "/usr/local/cargo/bin:" + env.get("PATH", "")
    env.setdefault("CARGO_HOME", "/usr/local/cargo")
    env.setdefault("RUSTUP_HOME", "/usr/local/rustup")
    return env


def _expected_value(probe_id: int, scale: float) -> float:
    return sum(PROBE_VECTORS[probe_id]) * scale


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


def _write_permuted_states(dest: Path, order: list[str]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for slot, source in zip(["set1", "set2", "set3"], order):
        src_idx = source[-1]
        shutil.copy(f"data/{source}.json", dest / f"{slot}.json")
        shutil.copy(f"data/vals{src_idx}.csv", dest / f"vals{src_idx}.csv")


def _run_permutation(built_pipeline, order: list[str]) -> dict:
    td, to = Path("_tmpd"), Path("_tmpo")
    for d in [td, to]:
        if d.exists():
            shutil.rmtree(d)
    _write_permuted_states(td, order)
    to.mkdir(parents=True, exist_ok=True)
    run_pipeline(built_pipeline, states=str(td) + "/", output=str(to) + "/")
    with open(to / "provenance.json") as f:
        data = json.load(f)
    shutil.rmtree(td)
    shutil.rmtree(to)
    return data


class TestMilestone2:
    def test_full_history(self, built_pipeline):
        """Each group history lists all three source tags after full ingestion."""
        if os.path.exists("artifacts"):
            shutil.rmtree("artifacts")
        os.makedirs("artifacts", exist_ok=True)
        run_pipeline(built_pipeline)
        with open("artifacts/provenance.json") as f:
            data = json.load(f)
        for chain in data["chains"]:
            if chain["group_id"] in ["G1", "G2"]:
                assert chain["history"] == CANONICAL_HISTORY

    def test_conflict_resolution(self, built_pipeline):
        """Canonical key resolves identically for every probe group."""
        run_pipeline(built_pipeline)
        with open("artifacts/provenance.json") as f:
            data = json.load(f)
        for chain in data["chains"]:
            if chain["group_id"] in ["G1", "G2"]:
                assert chain["key"] == CANONICAL_KEY

    def test_predictions_schema(self, built_pipeline):
        """Per-block keys and scaled values follow depth-aware ancestry."""
        run_pipeline(built_pipeline)
        with open("artifacts/predictions.json") as f:
            pred = json.load(f)
        for state, want_key in DEPTH_KEYS.items():
            assert len(pred[state]) == 2
            scale = DEPTH_SCALES[state]
            for rec in pred[state]:
                assert rec["key"] == want_key
                assert rec["value"] == pytest.approx(_expected_value(rec["probe_id"], scale))

    def test_merge_commutativity(self, built_pipeline):
        """Provenance is invariant under batch-file source permutations."""
        td1, to1 = Path("_tc1d"), Path("_tc1o")
        td2, to2 = Path("_tc2d"), Path("_tc2o")
        td3, to3 = Path("_tc3d"), Path("_tc3o")
        for d in [td1, to1, td2, to2, td3, to3]:
            if d.exists():
                shutil.rmtree(d)
        _write_permuted_states(td1, ["set1", "set2", "set3"])
        _write_permuted_states(td2, ["set3", "set2", "set1"])
        _write_permuted_states(td3, ["set2", "set1", "set3"])
        try:
            outputs = []
            for td, to in [(td1, to1), (td2, to2), (td3, to3)]:
                to.mkdir(parents=True, exist_ok=True)
                res = subprocess.run(
                    [built_pipeline, "--states", str(td) + "/", "--output", str(to) + "/"],
                    cwd=APP,
                    capture_output=True,
                    text=True,
                )
                if res.returncode != 0:
                    raise AssertionError(f"Pipeline failed: {res.stderr}")
                with open(to / "provenance.json") as f:
                    outputs.append(json.load(f))
            ref = sorted(outputs[0]["chains"], key=lambda x: x["group_id"])
            for other in outputs[1:]:
                chains = sorted(other["chains"], key=lambda x: x["group_id"])
                for a, b in zip(ref, chains):
                    assert a["history"] == b["history"] == CANONICAL_HISTORY
                    assert a["key"] == b["key"] == CANONICAL_KEY
        finally:
            for d in [td1, to1, td2, to2, td3, to3]:
                if d.exists():
                    shutil.rmtree(d)

    @pytest.mark.parametrize("order", EXTRA_PERMUTATIONS)
    def test_commute_extra_permutation(self, built_pipeline, order):
        """Additional file-order permutations yield identical provenance."""
        data = _run_permutation(built_pipeline, order)
        for chain in data["chains"]:
            if chain["group_id"] in ("G1", "G2"):
                assert chain["history"] == CANONICAL_HISTORY
                assert chain["key"] == CANONICAL_KEY

    def test_g1_history_sorted_in_json(self, built_pipeline):
        """G1 history in provenance.json is sorted, not insertion order."""
        run_pipeline(built_pipeline)
        with open("artifacts/provenance.json") as f:
            prov = json.load(f)
        g1 = next(c for c in prov["chains"] if c["group_id"] == "G1")
        assert g1["history"] == CANONICAL_HISTORY

    def test_g2_history_sorted_in_json(self, built_pipeline):
        """G2 history in provenance.json is sorted, not insertion order."""
        run_pipeline(built_pipeline)
        with open("artifacts/provenance.json") as f:
            prov = json.load(f)
        g2 = next(c for c in prov["chains"] if c["group_id"] == "G2")
        assert g2["history"] == CANONICAL_HISTORY

    def test_set2_probe1_value_twelve(self, built_pipeline):
        """set2 probe 1 uses partial key scale 2.0 yielding 12.0."""
        run_pipeline(built_pipeline)
        with open("artifacts/predictions.json") as f:
            pred = json.load(f)
        rec = next(r for r in pred["set2"] if r["probe_id"] == 1)
        assert rec["value"] == pytest.approx(12.0)

    def test_set2_probe2_value_fifteen(self, built_pipeline):
        """set2 probe 2 uses partial key scale 2.0 yielding 15.0."""
        run_pipeline(built_pipeline)
        with open("artifacts/predictions.json") as f:
            pred = json.load(f)
        rec = next(r for r in pred["set2"] if r["probe_id"] == 2)
        assert rec["value"] == pytest.approx(15.0)

    def test_set3_probe1_value_twentyfour(self, built_pipeline):
        """set3 probe 1 uses full key scale 4.0 yielding 24.0."""
        run_pipeline(built_pipeline)
        with open("artifacts/predictions.json") as f:
            pred = json.load(f)
        rec = next(r for r in pred["set3"] if r["probe_id"] == 1)
        assert rec["value"] == pytest.approx(24.0)

    def test_set3_probe2_value_thirty(self, built_pipeline):
        """set3 probe 2 uses full key scale 4.0 yielding 30.0."""
        run_pipeline(built_pipeline)
        with open("artifacts/predictions.json") as f:
            pred = json.load(f)
        rec = next(r for r in pred["set3"] if r["probe_id"] == 2)
        assert rec["value"] == pytest.approx(30.0)

    def test_streaming_keys_differ_by_depth(self, built_pipeline):
        """Depth-aware blocks emit distinct ancestry keys per batch."""
        run_pipeline(built_pipeline)
        with open("artifacts/predictions.json") as f:
            pred = json.load(f)
        keys = {state: pred[state][0]["key"] for state in DEPTH_KEYS}
        assert keys["set1"] != keys["set2"] != keys["set3"]

    def test_set2_block_uses_partial_key(self, built_pipeline):
        """set2 predictions reference the two-source ancestry key."""
        run_pipeline(built_pipeline)
        with open("artifacts/predictions.json") as f:
            pred = json.load(f)
        for rec in pred["set2"]:
            assert rec["key"] == "set1_set2"

    def test_set3_block_uses_full_key(self, built_pipeline):
        """set3 predictions reference the three-source ancestry key."""
        run_pipeline(built_pipeline)
        with open("artifacts/predictions.json") as f:
            pred = json.load(f)
        for rec in pred["set3"]:
            assert rec["key"] == CANONICAL_KEY

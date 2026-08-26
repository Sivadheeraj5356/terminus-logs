import json
import os
import subprocess

import pytest

APP = "/app"
PIPELINE_BIN = f"{APP}/target/release/pipeline"
CANONICAL_KEY = "set1_set2_set3"
CANONICAL_HISTORY = ["set1", "set2", "set3"]
PROBE_VECTORS = {1: [1.0, 2.0, 3.0], 2: [1.5, 2.5, 3.5]}
FULL_SCALE = 4.0


def _cargo_env():
    env = os.environ.copy()
    env["PATH"] = "/usr/local/cargo/bin:" + env.get("PATH", "")
    env.setdefault("CARGO_HOME", "/usr/local/cargo")
    env.setdefault("RUSTUP_HOME", "/usr/local/rustup")
    return env


def _expected_value(probe_id: int) -> float:
    return sum(PROBE_VECTORS[probe_id]) * FULL_SCALE


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


def _load_artifacts():
    with open("artifacts/provenance.json") as f:
        prov = json.load(f)
    with open("artifacts/predictions.json") as f:
        pred = json.load(f)
    return prov, pred


class TestMilestone3:
    def test_output_determinism(self, built_pipeline):
        """All blocks share identical fully-resolved prediction values."""
        run_pipeline(built_pipeline)
        with open("artifacts/predictions.json") as f:
            data = json.load(f)

        for state in ["set1", "set2", "set3"]:
            assert state in data

        for probe_id in (1, 2):
            want = _expected_value(probe_id)
            vals = [
                next(item["value"] for item in data[state] if item["probe_id"] == probe_id)
                for state in ["set1", "set2", "set3"]
            ]
            assert vals[0] == vals[1] == vals[2]
            assert vals[0] == pytest.approx(want)

    def test_canonical_provenance_keys(self, built_pipeline):
        """Provenance chains expose sorted history and canonical key."""
        run_pipeline(built_pipeline)
        with open("artifacts/provenance.json") as f:
            prov_data = json.load(f)

        for chain in prov_data["chains"]:
            assert chain["history"] == CANONICAL_HISTORY
            assert chain["key"] == CANONICAL_KEY

    def test_artifact_coupling(self, built_pipeline):
        """Every prediction key appears in provenance metadata."""
        run_pipeline(built_pipeline)
        prov_data, pred_data = _load_artifacts()
        prov_keys = {chain["key"] for chain in prov_data["chains"]}

        for state in ["set1", "set2", "set3"]:
            for item in pred_data[state]:
                assert item["key"] in prov_keys

    def test_cross_artifact_invariant(self, built_pipeline):
        """Prediction keys match canonical provenance key per group."""
        run_pipeline(built_pipeline)
        prov_data, pred_data = _load_artifacts()
        group_keys = {chain["group_id"]: chain["key"] for chain in prov_data["chains"]}

        for state in ["set1", "set2", "set3"]:
            for item in pred_data[state]:
                group_id = f"G{item['probe_id']}"
                assert item["key"] == group_keys[group_id]

    def test_validation_rejects_stale_keys(self, built_pipeline):
        """Audit accepts valid artifacts and rejects tampered keys."""
        run_pipeline(built_pipeline)

        ok = subprocess.run(
            [built_pipeline, "--check", "--output", "artifacts/"],
            cwd=APP,
            capture_output=True,
            text=True,
        )
        assert ok.returncode == 0

        with open("artifacts/predictions.json") as f:
            preds = json.load(f)

        preds["set1"][0]["key"] = "stale_wrong_key"
        with open("artifacts/predictions.json", "w") as f:
            json.dump(preds, f)

        res = subprocess.run(
            [built_pipeline, "--check", "--output", "artifacts/"],
            cwd=APP,
            capture_output=True,
            text=True,
        )
        assert res.returncode != 0

        run_pipeline(built_pipeline)
        with open("artifacts/predictions.json") as f:
            preds = json.load(f)
        preds["set2"][0]["key"] = "stale"
        with open("artifacts/predictions.json", "w") as f:
            json.dump(preds, f)

        res = subprocess.run(
            [built_pipeline, "--check", "--output", "artifacts/"],
            cwd=APP,
            capture_output=True,
            text=True,
        )
        assert res.returncode != 0

    def test_set1_probe1_full_scale_twentyfour(self, built_pipeline):
        """set1 probe 1 uses fully resolved key and scale 4.0."""
        run_pipeline(built_pipeline)
        _, pred = _load_artifacts()
        rec = next(r for r in pred["set1"] if r["probe_id"] == 1)
        assert rec["value"] == pytest.approx(24.0)
        assert rec["key"] == CANONICAL_KEY

    def test_set1_probe2_full_scale_thirty(self, built_pipeline):
        """set1 probe 2 uses fully resolved key and scale 4.0."""
        run_pipeline(built_pipeline)
        _, pred = _load_artifacts()
        rec = next(r for r in pred["set1"] if r["probe_id"] == 2)
        assert rec["value"] == pytest.approx(30.0)
        assert rec["key"] == CANONICAL_KEY

    def test_set2_uses_canonical_key_not_partial(self, built_pipeline):
        """set2 block no longer uses partial streaming ancestry key."""
        run_pipeline(built_pipeline)
        _, pred = _load_artifacts()
        for rec in pred["set2"]:
            assert rec["key"] == CANONICAL_KEY
            assert rec["key"] != "set1_set2"

    def test_set3_uses_canonical_key(self, built_pipeline):
        """set3 block uses the fully resolved canonical key."""
        run_pipeline(built_pipeline)
        _, pred = _load_artifacts()
        for rec in pred["set3"]:
            assert rec["key"] == CANONICAL_KEY

    def test_all_blocks_share_same_probe_values(self, built_pipeline):
        """Each probe value is identical across all state blocks."""
        run_pipeline(built_pipeline)
        _, pred = _load_artifacts()
        for probe_id in (1, 2):
            vals = [
                next(r["value"] for r in pred[state] if r["probe_id"] == probe_id)
                for state in ("set1", "set2", "set3")
            ]
            assert vals[0] == vals[1] == vals[2]

    def test_g1_history_sorted_in_provenance(self, built_pipeline):
        """G1 provenance history remains sorted after full resolution."""
        run_pipeline(built_pipeline)
        prov, _ = _load_artifacts()
        g1 = next(c for c in prov["chains"] if c["group_id"] == "G1")
        assert g1["history"] == CANONICAL_HISTORY

    def test_g2_history_sorted_in_provenance(self, built_pipeline):
        """G2 provenance history remains sorted after full resolution."""
        run_pipeline(built_pipeline)
        prov, _ = _load_artifacts()
        g2 = next(c for c in prov["chains"] if c["group_id"] == "G2")
        assert g2["history"] == CANONICAL_HISTORY

    def test_check_accepts_fresh_pipeline_output(self, built_pipeline):
        """pipeline --check exits 0 on freshly generated consistent artifacts."""
        run_pipeline(built_pipeline)
        res = subprocess.run(
            [built_pipeline, "--check", "--output", "artifacts/"],
            cwd=APP,
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, res.stderr

    def test_predictions_count_six_total(self, built_pipeline):
        """Predictions contain exactly two probes per state block."""
        run_pipeline(built_pipeline)
        _, pred = _load_artifacts()
        total = sum(len(pred[s]) for s in ("set1", "set2", "set3"))
        assert total == 6

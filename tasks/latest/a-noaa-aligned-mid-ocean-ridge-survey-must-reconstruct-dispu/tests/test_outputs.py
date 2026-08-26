"""Verifier tests for /app/target/release/expeditctl — ocean expedition reconstruction."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures import fixture_data as fx
from fixtures import reference_expeditctl as ref

BINARY = fx.BINARY
ALPHA = fx.ALPHA
BETA = fx.BETA
POLICY_DEFAULT = fx.POLICY_DEFAULT
HIDDEN_SIGMA = fx.HIDDEN_SIGMA
HIDDEN_SIGMA_BOM = fx.HIDDEN_SIGMA_BOM
HIDDEN_OMEGA = fx.HIDDEN_OMEGA
HIDDEN_TIE = fx.HIDDEN_TIE
HIDDEN_KAPPA = fx.HIDDEN_KAPPA


def run(*args: str, timeout: int = 90, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        [str(BINARY), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        env=run_env,
    )


def ingest(bundle: Path, staging: Path, policy: Path = POLICY_DEFAULT) -> None:
    proc = run(
        "ingest-dive-log",
        "--bundle",
        str(bundle),
        "--policy",
        str(policy),
        "--staging",
        str(staging),
    )
    assert proc.returncode == 0, proc.stderr


def pipeline(bundle: Path, tmp: Path, stem: str, policy: Path = POLICY_DEFAULT) -> dict[str, Path]:
    staging = tmp / f"{stem}-staging.json"
    resolved = tmp / f"{stem}-resolved.json"
    reconciled = tmp / f"{stem}-reconciled.json"
    atlas = tmp / f"{stem}-atlas.json"
    proc = run(
        "ingest-dive-log",
        "--bundle",
        str(bundle),
        "--policy",
        str(policy),
        "--staging",
        str(staging),
    )
    assert proc.returncode == 0, proc.stderr
    proc = run("resolve-precedence", "--staging", str(staging), "--output", str(resolved))
    assert proc.returncode == 0, proc.stderr
    proc = run("reconcile-observations", "--resolved", str(resolved), "--output", str(reconciled))
    assert proc.returncode == 0, proc.stderr
    proc = run(
        "export-atlas",
        "--observations",
        str(reconciled),
        "--policy",
        str(policy),
        "--atlas",
        str(atlas),
    )
    assert proc.returncode == 0, proc.stderr
    return {
        "staging": staging,
        "resolved": resolved,
        "reconciled": reconciled,
        "atlas": atlas,
    }


@pytest.fixture(scope="module")
def require_binary():
    assert BINARY.is_file(), "expeditctl missing after cargo build"
    assert os.access(BINARY, os.X_OK)


class TestBundledExpeditionData:
    def test_oel_rov_z46_dive_bundle_directory(self, require_binary):
        """Bundled dive bundles live under /app/data/dives/."""
        dives_dir = Path("/app/data/dives")
        assert dives_dir.is_dir()
        assert ALPHA.is_file()
        assert BETA.is_file()
        assert str(ALPHA).startswith("/app/data/dives")
        assert str(BETA).startswith("/app/data/dives")

    def test_oel_rov_z47_corpus_manifest(self, require_binary):
        """Corpus manifest at /app/data/corpus/manifest.json lists bundled dives."""
        manifest = Path("/app/data/corpus/manifest.json")
        assert manifest.is_file()
        data = json.loads(manifest.read_text())
        assert "bundles" in data
        assert "alpha.dive.json" in data["bundles"]
        assert "beta.dive.json" in data["bundles"]


class TestBuildAndCLI:
    def test_oel_rov_z00_release_binary(self, require_binary):
        """Release binary exists under target/release after rebuild."""
        assert BINARY.is_file()

    def test_oel_rov_z01_cli_requires_verb(self, require_binary):
        """Missing subcommand exits non-zero."""
        proc = run()
        assert proc.returncode != 0


class TestIngestDiveLog:
    def test_oel_rov_z02_dive_bundle_load(self, require_binary, tmp_path: Path):
        """ingest-dive-log on alpha bundle succeeds."""
        staging = tmp_path / "alpha-staging.json"
        proc = run(
            "ingest-dive-log",
            "--bundle",
            str(ALPHA),
            "--policy",
            str(POLICY_DEFAULT),
            "--staging",
            str(staging),
        )
        assert proc.returncode == 0, proc.stderr
        assert staging.is_file()

    def test_oel_rov_z03_expedition_id_preserved(self, require_binary, tmp_path: Path):
        """Staging preserves expedition_id from fixture."""
        staging = tmp_path / "alpha-staging.json"
        ingest(ALPHA, staging)
        bundle = ref.load_json(ALPHA)
        assert json.loads(staging.read_text())["expedition_id"] == bundle["expedition_id"]

    def test_oel_rov_z04_sonar_report_tally(self, require_binary, tmp_path: Path):
        """Staging records five reports from alpha bundle."""
        staging = tmp_path / "alpha-staging.json"
        ingest(ALPHA, staging)
        data = json.loads(staging.read_text())
        assert data["report_count"] == 5
        assert len(data["reports"]) == 5

    def test_oel_rov_z05_rov_observation_tally(self, require_binary, tmp_path: Path):
        """Staging records five observations from alpha bundle."""
        staging = tmp_path / "alpha-staging.json"
        ingest(ALPHA, staging)
        data = json.loads(staging.read_text())
        assert data["observation_count"] == 5
        assert len(data["observations"]) == 5

    def test_oel_rov_z06_dive_snapshot_mirror(self, require_binary, tmp_path: Path):
        """Ingest mirrors staging to /app/state/{expedition_id}-dives.json."""
        staging = tmp_path / "alpha-staging.json"
        ingest(ALPHA, staging)
        data = json.loads(staging.read_text())
        snap = Path(f"/app/state/{data['expedition_id']}-dives.json")
        assert snap.is_file()
        assert json.loads(snap.read_text())["report_count"] == data["report_count"]

    def test_oel_rov_z07_malformed_oel_quarantine(self, require_binary, tmp_path: Path):
        """Invalid bundle JSON emits DIVE_FORMAT_ERROR."""
        bad = tmp_path / "bad.dive.json"
        bad.write_text("{not json")
        staging = tmp_path / "out.json"
        proc = run(
            "ingest-dive-log",
            "--bundle",
            str(bad),
            "--policy",
            str(POLICY_DEFAULT),
            "--staging",
            str(staging),
        )
        assert proc.returncode == 1
        assert "DIVE_FORMAT_ERROR" in proc.stderr

    def test_oel_rov_z50_oel_schema_missing_expedition(self, require_binary, tmp_path: Path):
        """Valid JSON missing expedition_id emits DIVE_FORMAT_ERROR per OEL_FORMAT.md."""
        bad = tmp_path / "schema.dive.json"
        bad.write_text(json.dumps({"reports": [], "observations": []}))
        staging = tmp_path / "schema-staging.json"
        proc = run(
            "ingest-dive-log",
            "--bundle",
            str(bad),
            "--policy",
            str(POLICY_DEFAULT),
            "--staging",
            str(staging),
        )
        assert proc.returncode == 1
        assert "DIVE_FORMAT_ERROR" in proc.stderr

    def test_oel_rov_z51_verifier_rebuild_doc(self, require_binary):
        """VERIFIER_REBUILD.md documents cargo rebuild before pytest."""
        text = Path("/app/docs/VERIFIER_REBUILD.md").read_text()
        assert "rebuild-expeditctl" in text
        assert "/app/src" in text

    def test_oel_rov_z48_bare_default_dives_lookup(self, require_binary, tmp_path: Path):
        """Bare bundle filename resolves under /app/data/dives when TB3_DIVE_DIR is unset."""
        staging = tmp_path / "alpha-staging.json"
        proc = run(
            "ingest-dive-log",
            "--bundle",
            "alpha.dive.json",
            "--policy",
            str(POLICY_DEFAULT),
            "--staging",
            str(staging),
        )
        assert proc.returncode == 0, proc.stderr
        bundle = ref.load_json(ALPHA)
        assert json.loads(staging.read_text())["expedition_id"] == bundle["expedition_id"]

    def test_oel_rov_z49_relative_bundle_from_cwd(self, require_binary, tmp_path: Path):
        """Relative bundle paths with directory components resolve from the process cwd."""
        staging = tmp_path / "alpha-staging.json"
        proc = run(
            "ingest-dive-log",
            "--bundle",
            "data/dives/alpha.dive.json",
            "--policy",
            str(POLICY_DEFAULT),
            "--staging",
            str(staging),
        )
        assert proc.returncode == 0, proc.stderr
        bundle = ref.load_json(ALPHA)
        assert json.loads(staging.read_text())["expedition_id"] == bundle["expedition_id"]

    def test_oel_rov_z08_tb3_bare_alpha(self, require_binary, tmp_path: Path):
        """Bare bundle filename resolves under TB3_DIVE_DIR when set."""
        tb3_dir = tmp_path / "tb3_dives"
        tb3_dir.mkdir()
        (tb3_dir / "alpha.dive.json").write_bytes(ALPHA.read_bytes())
        staging = tmp_path / "alpha-staging.json"
        proc = run(
            "ingest-dive-log",
            "--bundle",
            "alpha.dive.json",
            "--policy",
            str(POLICY_DEFAULT),
            "--staging",
            str(staging),
            env={"TB3_DIVE_DIR": str(tb3_dir)},
        )
        assert proc.returncode == 0, proc.stderr
        bundle = ref.load_json(ALPHA)
        assert json.loads(staging.read_text())["expedition_id"] == bundle["expedition_id"]

    def test_oel_rov_z09_tb3_bare_sigma(self, require_binary, tmp_path: Path):
        """TB3_DIVE_DIR can load verifier-only sigma.dive.json by bare name."""
        tb3_dir = tmp_path / "tb3_hidden"
        tb3_dir.mkdir()
        (tb3_dir / "sigma.dive.json").write_bytes(HIDDEN_SIGMA.read_bytes())
        staging = tmp_path / "sigma-staging.json"
        proc = run(
            "ingest-dive-log",
            "--bundle",
            "sigma.dive.json",
            "--policy",
            str(POLICY_DEFAULT),
            "--staging",
            str(staging),
            env={"TB3_DIVE_DIR": str(tb3_dir)},
        )
        assert proc.returncode == 0, proc.stderr
        expected_id = ref.load_json(HIDDEN_SIGMA)["expedition_id"]
        assert json.loads(staging.read_text())["expedition_id"] == expected_id

    def test_oel_rov_z10_sigma_absolute_oel(self, require_binary, tmp_path: Path):
        """Hidden sigma bundle ingests via absolute path."""
        staging = tmp_path / "sigma-staging.json"
        ingest(HIDDEN_SIGMA, staging)
        expected_id = ref.load_json(HIDDEN_SIGMA)["expedition_id"]
        assert json.loads(staging.read_text())["expedition_id"] == expected_id


class TestResolvePrecedence:
    def test_oel_rov_z11_superseded_sonar_drop(self, require_binary, tmp_path: Path):
        """nt-001 dropped when nt-002 supersedes it."""
        staging = tmp_path / "alpha-staging.json"
        resolved = tmp_path / "alpha-resolved.json"
        ingest(ALPHA, staging)
        run("resolve-precedence", "--staging", str(staging), "--output", str(resolved))
        ids = {r["report_id"] for r in json.loads(resolved.read_text())["reports"]}
        assert "nt-001" not in ids
        assert "nt-003" in ids

    def test_oel_rov_z12_north_trench_arbitration(self, require_binary, tmp_path: Path):
        """north_trench keeps nt-003 over nt-002 by higher revision at same rank."""
        staging = tmp_path / "alpha-staging.json"
        resolved = tmp_path / "alpha-resolved.json"
        ingest(ALPHA, staging)
        run("resolve-precedence", "--staging", str(staging), "--output", str(resolved))
        reports = json.loads(resolved.read_text())["reports"]
        north = [r for r in reports if r["dive_lane"] == "north_trench"]
        assert len(north) == 1
        assert north[0]["report_id"] == "nt-003"

    def test_oel_rov_z13_south_ridge_arbitration(self, require_binary, tmp_path: Path):
        """south_ridge keeps sr-001 with lowest confidence_rank."""
        staging = tmp_path / "alpha-staging.json"
        resolved = tmp_path / "alpha-resolved.json"
        ingest(ALPHA, staging)
        run("resolve-precedence", "--staging", str(staging), "--output", str(resolved))
        reports = json.loads(resolved.read_text())["reports"]
        south = [r for r in reports if r["dive_lane"] == "south_ridge"]
        assert len(south) == 1
        assert south[0]["report_id"] == "sr-001"

    def test_oel_rov_z14_lane_winner_cardinality(self, require_binary, tmp_path: Path):
        """Alpha resolves to two winning reports."""
        staging = tmp_path / "alpha-staging.json"
        resolved = tmp_path / "alpha-resolved.json"
        ingest(ALPHA, staging)
        run("resolve-precedence", "--staging", str(staging), "--output", str(resolved))
        bundle = ref.load_json(ALPHA)
        expected = ref.resolve_precedence(bundle["reports"])
        assert len(json.loads(resolved.read_text())["reports"]) == len(expected)

    def test_oel_rov_z15_lane_winner_mirror(self, require_binary, tmp_path: Path):
        """resolve-precedence mirrors to /app/state/{expedition_id}-resolved.json."""
        staging = tmp_path / "alpha-staging.json"
        resolved = tmp_path / "alpha-resolved.json"
        ingest(ALPHA, staging)
        run("resolve-precedence", "--staging", str(staging), "--output", str(resolved))
        expedition_id = json.loads(staging.read_text())["expedition_id"]
        snap = Path(f"/app/state/{expedition_id}-resolved.json")
        assert snap.is_file()


class TestReconcileObservations:
    def test_oel_rov_z16_calibration_quarantine(self, require_binary, tmp_path: Path):
        """South ridge observations excluded when lane winner calibration_valid is false."""
        paths = pipeline(ALPHA, tmp_path, "a")
        reconciled = json.loads(paths["reconciled"].read_text())
        obs_ids = {o["obs_id"] for o in reconciled["observations"]}
        assert "obs-002" not in obs_ids
        assert "obs-004" not in obs_ids
        assert "obs-001" in obs_ids

    def test_oel_rov_z17_hydrothermal_anchor(self, require_binary, tmp_path: Path):
        """anchor_obs_id is earliest HYDROTHERMAL_VENT by timestamp."""
        paths = pipeline(ALPHA, tmp_path, "a")
        reconciled = json.loads(paths["reconciled"].read_text())
        assert reconciled["anchor_obs_id"] == "obs-003"

    def test_oel_rov_z18_feature_chain_links(self, require_binary, tmp_path: Path):
        """Feature links prefer previous observation in same dive_lane."""
        paths = pipeline(ALPHA, tmp_path, "a")
        bundle = ref.load_json(ALPHA)
        expected = ref.pipeline_from_bundle(bundle)["reconciled"]
        links = json.loads(paths["reconciled"].read_text())["feature_links"]
        assert links == expected["feature_links"]

    def test_oel_rov_z19_rov_survivor_count(self, require_binary, tmp_path: Path):
        """Alpha reconcile keeps three north_trench observations."""
        paths = pipeline(ALPHA, tmp_path, "a")
        reconciled = json.loads(paths["reconciled"].read_text())
        assert reconciled["observation_count"] == 3

    def test_oel_rov_z20_beta_revision_arbitration(self, require_binary, tmp_path: Path):
        """Beta lane keeps bd-002 with higher revision at same confidence_rank."""
        paths = pipeline(BETA, tmp_path, "beta")
        resolved = json.loads(paths["resolved"].read_text())["reports"]
        assert len(resolved) == 1
        assert resolved[0]["report_id"] == "bd-002"


class TestExportAtlas:
    def test_oel_rov_z21_atlas_payload_shape(self, require_binary, tmp_path: Path):
        """Atlas export includes observation_count and atlas_witness."""
        paths = pipeline(ALPHA, tmp_path, "a")
        atlas = json.loads(paths["atlas"].read_text())
        assert atlas["observation_count"] == 3
        assert atlas["atlas_witness"]

    def test_oel_rov_z22_atlas_digest_idempotent(self, require_binary, tmp_path: Path):
        """Re-export yields identical atlas_witness."""
        p1 = pipeline(ALPHA, tmp_path / "r1", "a")
        p2 = pipeline(ALPHA, tmp_path / "r2", "a")
        w1 = json.loads(p1["atlas"].read_text())["atlas_witness"]
        w2 = json.loads(p2["atlas"].read_text())["atlas_witness"]
        assert w1 == w2

    def test_oel_rov_z23_atlas_digest_reference(self, require_binary, tmp_path: Path):
        """atlas_witness matches independent reference CRC."""
        paths = pipeline(ALPHA, tmp_path, "a")
        atlas = json.loads(paths["atlas"].read_text())
        witness = atlas.pop("atlas_witness")
        assert witness == ref.atlas_witness(atlas)

    def test_oel_rov_z24_sigma_digest_reference(self, require_binary, tmp_path: Path):
        """Hidden sigma atlas witness uses canonical sorted-key JSON."""
        paths = pipeline(HIDDEN_SIGMA, tmp_path, "sigma")
        atlas = json.loads(paths["atlas"].read_text())
        witness = atlas.pop("atlas_witness")
        assert witness == ref.atlas_witness(atlas)

    def test_oel_rov_z25_sigma_hydrothermal_anchor(self, require_binary, tmp_path: Path):
        """Hidden sigma anchor_obs_id matches independent reference pipeline."""
        paths = pipeline(HIDDEN_SIGMA, tmp_path, "sigma")
        expected = ref.pipeline_from_bundle(ref.load_json(HIDDEN_SIGMA))["reconciled"]["anchor_obs_id"]
        atlas = json.loads(paths["atlas"].read_text())
        assert atlas["anchor_obs_id"] == expected

    def test_oel_rov_z26_obs_id_lex_order(self, require_binary, tmp_path: Path):
        """Exported observations sorted by obs_id ascending."""
        paths = pipeline(ALPHA, tmp_path, "a")
        obs_ids = [o["obs_id"] for o in json.loads(paths["atlas"].read_text())["observations"]]
        assert obs_ids == sorted(obs_ids)

    def test_oel_rov_z27_dive_lane_lex_order(self, require_binary, tmp_path: Path):
        """Atlas dive_lanes sorted by dive_lane ascending."""
        paths = pipeline(ALPHA, tmp_path, "a")
        lanes = [r["dive_lane"] for r in json.loads(paths["atlas"].read_text())["dive_lanes"]]
        assert lanes == sorted(lanes)

    def test_oel_rov_z29_export_ignores_staging_poison(self, require_binary, tmp_path: Path):
        """export-atlas uses on-disk resolved state even if dive staging is tampered afterward."""
        staging = tmp_path / "alpha-staging.json"
        resolved = tmp_path / "alpha-resolved.json"
        reconciled = tmp_path / "alpha-reconciled.json"
        atlas = tmp_path / "alpha-atlas.json"
        ingest(ALPHA, staging)
        run("resolve-precedence", "--staging", str(staging), "--output", str(resolved))
        run("reconcile-observations", "--resolved", str(resolved), "--output", str(reconciled))
        expedition_id = json.loads(staging.read_text())["expedition_id"]
        resolved_snap = Path(f"/app/state/{expedition_id}-resolved.json")
        expected_ids = {r["report_id"] for r in json.loads(resolved_snap.read_text())["reports"]}
        dives_snap = Path(f"/app/state/{expedition_id}-dives.json")
        poisoned = json.loads(dives_snap.read_text())
        poisoned["reports"].append(
            {
                "report_id": "poison-001",
                "dive_lane": "south_ridge",
                "confidence_rank": 0,
                "revision": 99,
                "supersedes": None,
                "calibration_valid": True,
            }
        )
        dives_snap.write_text(json.dumps(poisoned))
        proc = run(
            "export-atlas",
            "--observations",
            str(reconciled),
            "--policy",
            str(POLICY_DEFAULT),
            "--atlas",
            str(atlas),
        )
        assert proc.returncode == 0, proc.stderr
        lane_ids = {r["report_id"] for r in json.loads(atlas.read_text())["dive_lanes"]}
        assert lane_ids == expected_ids

    def test_oel_rov_z30_resolved_state_missing(self, require_binary, tmp_path: Path):
        """export-atlas fails with RESOLVED_STATE_MISSING when resolved snapshot absent."""
        paths = pipeline(ALPHA, tmp_path, "a")
        expedition_id = json.loads(paths["staging"].read_text())["expedition_id"]
        resolved_snap = Path(f"/app/state/{expedition_id}-resolved.json")
        if resolved_snap.is_file():
            resolved_snap.unlink()
        atlas = tmp_path / "missing-atlas.json"
        proc = run(
            "export-atlas",
            "--observations",
            str(paths["reconciled"]),
            "--policy",
            str(POLICY_DEFAULT),
            "--atlas",
            str(atlas),
        )
        assert proc.returncode == 1
        assert "RESOLVED_STATE_MISSING" in proc.stderr


class TestIngestBom:
    def test_oel_rov_z31_sigma_bom_ingest(self, require_binary, tmp_path: Path):
        """UTF-8 BOM prefixed sigma bundle ingests like the plain hidden fixture."""
        bom_path = fx.HIDDEN_SIGMA_BOM
        staging = tmp_path / "sigma-bom-staging.json"
        proc = run(
            "ingest-dive-log",
            "--bundle",
            str(bom_path),
            "--policy",
            str(POLICY_DEFAULT),
            "--staging",
            str(staging),
        )
        assert proc.returncode == 0, proc.stderr
        expected_id = ref.load_json(HIDDEN_SIGMA)["expedition_id"]
        assert json.loads(staging.read_text())["expedition_id"] == expected_id


class TestReplaySealLayer:
    def test_oel_rov_z32_staging_bind_reference(self, require_binary, tmp_path: Path):
        """staging_bind matches canonical CRC over expedition_id and sorted report_ids."""
        staging = tmp_path / "alpha-staging.json"
        ingest(ALPHA, staging)
        bundle = ref.load_json(ALPHA)
        expected = ref.pipeline_from_bundle(bundle)["staging"]["staging_bind"]
        assert json.loads(staging.read_text())["staging_bind"] == expected

    def test_oel_rov_z32b_bind_crc_zero_padding(self, require_binary, tmp_path: Path):
        """staging_bind is eight lowercase hex digits per BIND_CRC.md."""
        staging = tmp_path / "tie-staging.json"
        ingest(fx.HIDDEN_TIE, staging)
        bind = json.loads(staging.read_text())["staging_bind"]
        assert len(bind) == 8
        assert bind == bind.lower()
        assert all(c in "0123456789abcdef" for c in bind)
        bundle = ref.load_json(fx.HIDDEN_TIE)
        assert bind == ref.pipeline_from_bundle(bundle)["staging"]["staging_bind"]
        """Resolved artifact carries replay_seq 1 and lane_bind digest."""
        staging = tmp_path / "alpha-staging.json"
        resolved = tmp_path / "alpha-resolved.json"
        ingest(ALPHA, staging)
        run("resolve-precedence", "--staging", str(staging), "--output", str(resolved))
        bundle = ref.load_json(ALPHA)
        expected = ref.pipeline_from_bundle(bundle)["resolved"]
        data = json.loads(resolved.read_text())
        assert data["replay_seq"] == 1
        assert data["lane_bind"] == expected["lane_bind"]

    def test_oel_rov_z34_reconcile_state_persisted(self, require_binary, tmp_path: Path):
        """reconcile-observations mirrors reconcile_bind to /app/state reconciled snapshot."""
        paths = pipeline(ALPHA, tmp_path, "a")
        expedition_id = json.loads(paths["staging"].read_text())["expedition_id"]
        snap = Path(f"/app/state/{expedition_id}-reconciled.json")
        assert snap.is_file()
        bundle = ref.load_json(ALPHA)
        expected = ref.pipeline_from_bundle(bundle)["reconciled"]
        state = json.loads(snap.read_text())
        assert state["replay_seq"] == 2
        assert state["reconcile_bind"] == expected["reconcile_bind"]
        assert json.loads(paths["reconciled"].read_text())["reconcile_bind"] == expected["reconcile_bind"]

    def test_oel_rov_z35_expedition_seal_reference_alpha(self, require_binary, tmp_path: Path):
        """expedition_seal matches witness pipe reconcile_bind from persisted state."""
        paths = pipeline(ALPHA, tmp_path, "a")
        bundle = ref.load_json(ALPHA)
        expected = ref.pipeline_from_bundle(bundle)["atlas"]["expedition_seal"]
        assert json.loads(paths["atlas"].read_text())["expedition_seal"] == expected

    def test_oel_rov_z36_tb3_bare_omega(self, require_binary, tmp_path: Path):
        """TB3_DIVE_DIR loads hidden omega bundle by bare filename."""
        tb3_dir = tmp_path / "tb3_omega"
        tb3_dir.mkdir()
        (tb3_dir / "omega.dive.json").write_bytes(HIDDEN_OMEGA.read_bytes())
        staging = tmp_path / "omega-staging.json"
        proc = run(
            "ingest-dive-log",
            "--bundle",
            "omega.dive.json",
            "--policy",
            str(POLICY_DEFAULT),
            "--staging",
            str(staging),
            env={"TB3_DIVE_DIR": str(tb3_dir)},
        )
        assert proc.returncode == 0, proc.stderr
        expected_id = ref.load_json(HIDDEN_OMEGA)["expedition_id"]
        assert json.loads(staging.read_text())["expedition_id"] == expected_id

    def test_oel_rov_z37_omega_feature_links_reference(self, require_binary, tmp_path: Path):
        """Hidden omega cross-lane feature links match independent reference timeline."""
        paths = pipeline(HIDDEN_OMEGA, tmp_path, "omega")
        expected = ref.pipeline_from_bundle(ref.load_json(HIDDEN_OMEGA))["reconciled"]["feature_links"]
        links = json.loads(paths["reconciled"].read_text())["feature_links"]
        assert links == expected

    def test_oel_rov_z38_export_seal_uses_state_not_tampered(self, require_binary, tmp_path: Path):
        """export-atlas expedition_seal uses on-disk reconciled bind not tampered output file."""
        paths = pipeline(ALPHA, tmp_path, "a")
        expedition_id = json.loads(paths["staging"].read_text())["expedition_id"]
        state_snap = Path(f"/app/state/{expedition_id}-reconciled.json")
        expected_bind = json.loads(state_snap.read_text())["reconcile_bind"]
        tampered = json.loads(paths["reconciled"].read_text())
        tampered["reconcile_bind"] = "deadbeef"
        paths["reconciled"].write_text(json.dumps(tampered))
        atlas = tmp_path / "alpha-seal-atlas.json"
        proc = run(
            "export-atlas",
            "--observations",
            str(paths["reconciled"]),
            "--policy",
            str(POLICY_DEFAULT),
            "--atlas",
            str(atlas),
        )
        assert proc.returncode == 0, proc.stderr
        atlas_body = json.loads(atlas.read_text())
        witness = atlas_body.pop("atlas_witness")
        expected_seal = ref.expedition_seal(witness, expected_bind)
        assert atlas_body["expedition_seal"] == expected_seal

    def test_oel_rov_z39_replay_mismatch_blocks_reconcile(self, require_binary, tmp_path: Path):
        """reconcile-observations rejects resolved replay_seq other than 1."""
        staging = tmp_path / "alpha-staging.json"
        resolved = tmp_path / "alpha-resolved.json"
        reconciled = tmp_path / "alpha-reconciled.json"
        ingest(ALPHA, staging)
        run("resolve-precedence", "--staging", str(staging), "--output", str(resolved))
        bad = json.loads(resolved.read_text())
        bad["replay_seq"] = 2
        resolved.write_text(json.dumps(bad))
        proc = run(
            "reconcile-observations",
            "--resolved",
            str(resolved),
            "--output",
            str(reconciled),
        )
        assert proc.returncode == 1
        assert "REPLAY_MISMATCH" in proc.stderr


class TestErrorTokens:
    def test_oel_rov_z40_dive_read_error(self, require_binary, tmp_path: Path):
        """ingest-dive-log emits DIVE_READ_ERROR when the bundle path is unreadable."""
        missing = tmp_path / "absent.dive.json"
        staging = tmp_path / "out.json"
        proc = run(
            "ingest-dive-log",
            "--bundle",
            str(missing),
            "--policy",
            str(POLICY_DEFAULT),
            "--staging",
            str(staging),
        )
        assert proc.returncode == 1
        assert "DIVE_READ_ERROR" in proc.stderr

    def test_oel_rov_z41_policy_read_error(self, require_binary, tmp_path: Path):
        """ingest-dive-log emits POLICY_READ_ERROR when the policy path is unreadable."""
        missing_policy = tmp_path / "absent-policy.json"
        staging = tmp_path / "out.json"
        proc = run(
            "ingest-dive-log",
            "--bundle",
            str(ALPHA),
            "--policy",
            str(missing_policy),
            "--staging",
            str(staging),
        )
        assert proc.returncode == 1
        assert "POLICY_READ_ERROR" in proc.stderr

    def test_oel_rov_z42_staging_parse_error(self, require_binary, tmp_path: Path):
        """resolve-precedence emits STAGING_PARSE_ERROR on invalid staging JSON."""
        bad_staging = tmp_path / "bad-staging.json"
        bad_staging.write_text("{not valid json")
        resolved = tmp_path / "resolved.json"
        proc = run("resolve-precedence", "--staging", str(bad_staging), "--output", str(resolved))
        assert proc.returncode == 1
        assert "STAGING_PARSE_ERROR" in proc.stderr

    def test_oel_rov_z43_resolved_parse_error(self, require_binary, tmp_path: Path):
        """reconcile-observations emits RESOLVED_PARSE_ERROR on invalid resolved JSON."""
        bad_resolved = tmp_path / "bad-resolved.json"
        bad_resolved.write_text("{not valid json")
        reconciled = tmp_path / "reconciled.json"
        proc = run(
            "reconcile-observations",
            "--resolved",
            str(bad_resolved),
            "--output",
            str(reconciled),
        )
        assert proc.returncode == 1
        assert "RESOLVED_PARSE_ERROR" in proc.stderr

    def test_oel_rov_z44_reconcile_parse_error(self, require_binary, tmp_path: Path):
        """export-atlas emits RECONCILE_PARSE_ERROR on invalid observations JSON."""
        bad_obs = tmp_path / "bad-reconciled.json"
        bad_obs.write_text("{not valid json")
        atlas = tmp_path / "atlas.json"
        proc = run(
            "export-atlas",
            "--observations",
            str(bad_obs),
            "--policy",
            str(POLICY_DEFAULT),
            "--atlas",
            str(atlas),
        )
        assert proc.returncode == 1
        assert "RECONCILE_PARSE_ERROR" in proc.stderr

    def test_oel_rov_z45_reconciled_state_missing(self, require_binary, tmp_path: Path):
        """export-atlas emits RECONCILED_STATE_MISSING when the reconciled snapshot is absent."""
        paths = pipeline(ALPHA, tmp_path, "a")
        expedition_id = json.loads(paths["staging"].read_text())["expedition_id"]
        reconciled_snap = Path(f"/app/state/{expedition_id}-reconciled.json")
        if reconciled_snap.is_file():
            reconciled_snap.unlink()
        resolved_snap = Path(f"/app/state/{expedition_id}-resolved.json")
        assert resolved_snap.is_file(), "resolved snapshot should remain for this failure path"
        atlas = tmp_path / "no-state-atlas.json"
        proc = run(
            "export-atlas",
            "--observations",
            str(paths["reconciled"]),
            "--policy",
            str(POLICY_DEFAULT),
            "--atlas",
            str(atlas),
        )
        assert proc.returncode == 1
        assert "RECONCILED_STATE_MISSING" in proc.stderr


class TestHiddenAdversarial:
    def test_oel_rov_z52_tb3_precedence_report_id_tiebreak(self, require_binary, tmp_path: Path):
        """Hidden tie bundle picks report_id ascending when rank and revision match."""
        staging = tmp_path / "tie-staging.json"
        resolved = tmp_path / "tie-resolved.json"
        ingest(HIDDEN_TIE, staging)
        run("resolve-precedence", "--staging", str(staging), "--output", str(resolved))
        reports = json.loads(resolved.read_text())["reports"]
        assert len(reports) == 1
        assert reports[0]["report_id"] == "tie-001"

    def test_oel_rov_z53_tb3_multi_hydrothermal_anchor(self, require_binary, tmp_path: Path):
        """Hidden kappa bundle picks earliest HYDROTHERMAL_VENT timestamp as anchor."""
        paths = pipeline(HIDDEN_KAPPA, tmp_path, "kappa")
        expected = ref.pipeline_from_bundle(ref.load_json(HIDDEN_KAPPA))["reconciled"]["anchor_obs_id"]
        assert json.loads(paths["reconciled"].read_text())["anchor_obs_id"] == expected
        assert expected == "obs-k2"

    def test_oel_rov_z54_tb3_missing_lane_quarantine(self, require_binary, tmp_path: Path):
        """Hidden kappa excludes observations whose dive_lane has no winning report."""
        paths = pipeline(HIDDEN_KAPPA, tmp_path, "kappa2")
        obs_ids = {o["obs_id"] for o in json.loads(paths["reconciled"].read_text())["observations"]}
        assert "obs-k3" not in obs_ids
        assert "obs-k1" in obs_ids
        assert "obs-k2" in obs_ids

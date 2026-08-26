"""Verifier tests for /app/columnarctl compaction planner.

Verifier-only CLFC catalogs are written under /opt/verifier-fixtures at test
runtime (see tests/seed_hidden_catalogs.py); they are not bundled in the image.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures.fixture_data import (
    ALPHA_EXPECT,
    ALPHA_FRAGMENTS,
    BETA_EXPECT,
    CASE_COLUMN_EXPECT,
    HIDDEN_CATALOGS,
    REPLICA_EDGE_EXPECT,
    REPLICA_STRICT_POLICY,
    fingerprint_hex,
    plan_expected,
    plan_signature,
    reference_plan_expected,
    staging_snapshot_reference,
)

BINARY = Path("/app/columnarctl")
CONTRACT = Path("/app/docs/COMPACTION_CONTRACT.md")
STAGING_DOC = Path("/app/docs/STAGING_SNAPSHOT.md")
SNAPSHOT_PATH = Path("/app/state/compaction-snapshot.json")
POLICY_DEFAULT = Path("/app/data/policies/default.json")
POLICY_STRICT = Path("/app/data/policies/strict.json")
POLICY_REPLICA_STRICT = Path("/app/data/policies/replica_strict.json")
CATALOG_ALPHA = Path("/app/data/catalogs/alpha.clfc")
CATALOG_BETA = Path("/app/data/catalogs/beta.clfc")
CATALOG_CASE = Path("/app/data/catalogs/case_column.clfc")
CATALOG_REPLICA = Path("/app/data/catalogs/replica_edge.clfc")
VERIFIER_FIXTURES = Path("/opt/verifier-fixtures")
HIDDEN_CATALOG_DIR = VERIFIER_FIXTURES / "catalogs"


def run_cmd(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [str(BINARY), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=[str(BINARY), *args],
            returncode=-1,
            stdout="",
            stderr="timeout",
        )


def parse_json(stdout: str) -> dict:
    return json.loads(stdout)


def write_plan(path: Path, plan: dict) -> None:
    path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def require_binary():
    assert BINARY.is_file(), "columnarctl missing; run make -C /app"
    assert CONTRACT.is_file()


class TestBuildAndCLI:
    def test_binary_exists(self, require_binary):
        """columnarctl binary exists and is executable after rebuild."""
        assert os.access(BINARY, os.X_OK)

    def test_usage_without_args(self, require_binary):
        """Invoking columnarctl with no arguments prints USAGE and exits 2."""
        proc = run_cmd()
        assert proc.returncode == 2
        assert proc.stderr.strip() == "USAGE"

    def test_unknown_subcommand(self, require_binary):
        """Unknown subcommands print USAGE and exit 2."""
        proc = run_cmd("nope")
        assert proc.returncode == 2
        assert proc.stderr.strip() == "USAGE"


class TestCatalogErrors:
    def test_bad_magic(self, require_binary, tmp_path):
        """Catalogs with invalid magic bytes fail plan with CATALOG_ERROR."""
        bad = tmp_path / "bad.clfc"
        bad.write_bytes(b"XXXX" + b"\x00" * 8)
        out = tmp_path / "out.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(bad),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc.returncode == 1
        assert proc.stderr.strip() == "CATALOG_ERROR"
        assert not out.exists()

    def test_truncated_header(self, require_binary, tmp_path):
        """Truncated catalog headers fail plan with CATALOG_ERROR."""
        bad = tmp_path / "short.clfc"
        bad.write_bytes(b"CLFC\x01")
        proc = run_cmd(
            "plan",
            "--catalog",
            str(bad),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(tmp_path / "out.json"),
        )
        assert proc.returncode == 1
        assert proc.stderr.strip() == "CATALOG_ERROR"


class TestPlanPublic:
    def test_alpha_plan(self, require_binary, tmp_path):
        """plan on alpha.clfc yields contract-correct merge plan JSON."""
        out = tmp_path / "alpha.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(CATALOG_ALPHA),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        body = parse_json(proc.stdout)
        assert body["fragment_ids"] == ALPHA_EXPECT["fragment_ids"]
        assert body["row_overlap_lengths"] == ALPHA_EXPECT["row_overlap_lengths"]
        assert body["total_rows"] == ALPHA_EXPECT["total_rows"]
        assert body["scan_cost_units"] == ALPHA_EXPECT["scan_cost_units"]
        assert body["fragmentation_index"] == ALPHA_EXPECT["fragmentation_index"]
        assert body["replica_consistent"] == ALPHA_EXPECT["replica_consistent"]
        assert body["fingerprint"] == ALPHA_EXPECT["fingerprint"]
        assert out.is_file()

    def test_beta_plan(self, require_binary, tmp_path):
        """plan on beta.clfc yields expected row totals and fingerprint."""
        out = tmp_path / "beta.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(CATALOG_BETA),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        body = parse_json(proc.stdout)
        assert body["total_rows"] == BETA_EXPECT["total_rows"]
        assert body["fingerprint"] == BETA_EXPECT["fingerprint"]

    def test_case_fold_column(self, require_binary, tmp_path):
        """Mixed-case column names chain after ASCII case folding."""
        out = tmp_path / "case.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(CATALOG_CASE),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        body = parse_json(proc.stdout)
        assert body["fragment_ids"] == CASE_COLUMN_EXPECT["fragment_ids"]
        assert body["total_rows"] == CASE_COLUMN_EXPECT["total_rows"]

    def test_replica_inconsistent_flag(self, require_binary, tmp_path):
        """Catalogs with missing replica bits set replica_consistent false."""
        out = tmp_path / "rep.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(CATALOG_REPLICA),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        body = parse_json(proc.stdout)
        assert body["replica_consistent"] is False
        assert body["fingerprint"] == REPLICA_EDGE_EXPECT["fingerprint"]


@pytest.mark.parametrize("name", sorted(HIDDEN_CATALOGS.keys()))
class TestHiddenPlan:
    def test_hidden_catalog_plan(self, require_binary, tmp_path, name):
        """Verifier-only catalogs (materialized at test run) plan to reference expectations."""
        cat = HIDDEN_CATALOG_DIR / f"{name}.clfc"
        assert cat.is_file(), f"missing verifier-only catalog {cat}"
        expected = reference_plan_expected(HIDDEN_CATALOGS[name])
        out = tmp_path / "out.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(cat),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        body = parse_json(proc.stdout)
        assert body["fragment_ids"] == expected["fragment_ids"]
        assert body["row_overlap_lengths"] == expected["row_overlap_lengths"]
        assert body["total_rows"] == expected["total_rows"]
        assert body["fingerprint"] == expected["fingerprint"]


class TestValidate:
    def test_validate_good_plan(self, require_binary, tmp_path):
        """validate accepts a freshly planned merge plan."""
        plan_path = tmp_path / "good.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(CATALOG_ALPHA),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(plan_path),
        )
        assert proc.returncode == 0, proc.stderr
        vproc = run_cmd(
            "validate",
            "--plan",
            str(plan_path),
            "--catalog",
            str(CATALOG_ALPHA),
            "--policy",
            str(POLICY_DEFAULT),
        )
        assert vproc.returncode == 0, vproc.stderr
        body = parse_json(vproc.stdout)
        assert body["ok"] is True
        assert body["primary_error"] == ""
        assert body["errors"] == []

    def test_validate_order_violation(self, require_binary, tmp_path):
        """validate reports ORDER_VIOLATION when fragment seq decreases."""
        bad = dict(ALPHA_EXPECT)
        bad["fragment_ids"] = list(reversed(ALPHA_EXPECT["fragment_ids"]))
        bad["row_overlap_lengths"] = list(reversed(ALPHA_EXPECT["row_overlap_lengths"]))
        bad["fingerprint"] = fingerprint_hex(plan_signature(bad))
        plan_path = tmp_path / "bad.json"
        write_plan(plan_path, bad)
        proc = run_cmd(
            "validate",
            "--plan",
            str(plan_path),
            "--catalog",
            str(CATALOG_ALPHA),
        )
        assert proc.returncode == 1
        assert proc.stderr.strip() == "ORDER_VIOLATION"

    def test_validate_overlap_conflict(self, require_binary, tmp_path):
        """validate reports OVERLAP_CONFLICT when junction overlap is below peak."""
        bad = dict(ALPHA_EXPECT)
        if bad["row_overlap_lengths"]:
            bad["row_overlap_lengths"] = [1] + bad["row_overlap_lengths"][1:]
            bad["fingerprint"] = fingerprint_hex(plan_signature(bad))
        plan_path = tmp_path / "conflict.json"
        write_plan(plan_path, bad)
        proc = run_cmd(
            "validate",
            "--plan",
            str(plan_path),
            "--catalog",
            str(CATALOG_ALPHA),
        )
        assert proc.returncode == 1
        assert proc.stderr.strip() == "OVERLAP_CONFLICT"

    def test_validate_fingerprint_mismatch(self, require_binary, tmp_path):
        """validate reports FINGERPRINT when fingerprint field is wrong."""
        bad = dict(ALPHA_EXPECT)
        bad["fingerprint"] = "0" * 16
        plan_path = tmp_path / "fp.json"
        write_plan(plan_path, bad)
        proc = run_cmd(
            "validate",
            "--plan",
            str(plan_path),
            "--catalog",
            str(CATALOG_ALPHA),
        )
        assert proc.returncode == 1
        assert proc.stderr.strip() == "FINGERPRINT"

    def test_validate_replica_mismatch(self, require_binary, tmp_path):
        """validate reports REPLICA_MISMATCH when replica flag is wrong."""
        bad = dict(REPLICA_EDGE_EXPECT)
        bad["replica_consistent"] = True
        bad["fingerprint"] = fingerprint_hex(plan_signature(bad))
        plan_path = tmp_path / "repbad.json"
        write_plan(plan_path, bad)
        proc = run_cmd(
            "validate",
            "--plan",
            str(plan_path),
            "--catalog",
            str(CATALOG_REPLICA),
        )
        assert proc.returncode == 1
        assert proc.stderr.strip() == "REPLICA_MISMATCH"


class TestRepair:
    def test_repair_broken_plan(self, require_binary, tmp_path):
        """repair rebuilds an invalid plan and writes corrected JSON."""
        broken = dict(ALPHA_EXPECT)
        broken["fragment_ids"] = [2, 1, 3]
        broken["row_overlap_lengths"] = [1, 1]
        broken["total_rows"] = 1
        broken["fingerprint"] = "deadbeefdeadbeef"
        plan_path = tmp_path / "broken.json"
        out_path = tmp_path / "fixed.json"
        write_plan(plan_path, broken)
        proc = run_cmd(
            "repair",
            "--plan",
            str(plan_path),
            "--catalog",
            str(CATALOG_ALPHA),
            "--out",
            str(out_path),
        )
        assert proc.returncode == 0, proc.stderr
        body = parse_json(proc.stdout)
        assert body["ok"] is True
        assert body["swaps"] >= 1
        fixed = json.loads(out_path.read_text(encoding="utf-8"))
        assert fixed["fragment_ids"] == ALPHA_EXPECT["fragment_ids"]
        assert fixed["fingerprint"] == ALPHA_EXPECT["fingerprint"]

    def test_repair_idempotent(self, require_binary, tmp_path):
        """repair on a valid plan performs zero swaps."""
        plan_path = tmp_path / "good.json"
        out_path = tmp_path / "same.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(CATALOG_ALPHA),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(plan_path),
        )
        assert proc.returncode == 0
        rproc = run_cmd(
            "repair",
            "--plan",
            str(plan_path),
            "--catalog",
            str(CATALOG_ALPHA),
            "--out",
            str(out_path),
        )
        assert rproc.returncode == 0, rproc.stderr
        body = parse_json(rproc.stdout)
        assert body["ok"] is True
        assert body["swaps"] == 0


class TestMetrics:
    def test_scan_cost_alpha(self, require_binary, tmp_path):
        """scan_cost_units sums byte sizes with policy multiplier."""
        out = tmp_path / "cost.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(CATALOG_ALPHA),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        body = parse_json(proc.stdout)
        assert body["scan_cost_units"] == 350

    def test_strict_policy_scan_cost(self, require_binary, tmp_path):
        """strict policy doubles scan_cost_per_byte in scan_cost_units."""
        out = tmp_path / "strict.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(CATALOG_ALPHA),
            "--policy",
            str(POLICY_STRICT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        body = parse_json(proc.stdout)
        expected = plan_expected(
            ALPHA_FRAGMENTS,
            {
                "min_row_overlap": 5,
                "case_fold_ascii": True,
                "required_replica_mask": 0x0007,
                "scan_cost_per_byte": 2,
                "scan_penalty_per_gap": 20,
            },
        )
        assert body["scan_cost_units"] == expected["scan_cost_units"]

    def test_fragmentation_zero_on_alpha(self, require_binary, tmp_path):
        """tight row overlaps yield fragmentation_index zero on alpha."""
        out = tmp_path / "frag.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(CATALOG_ALPHA),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        body = parse_json(proc.stdout)
        assert body["fragmentation_index"] == 0

    def test_total_rows_alpha(self, require_binary, tmp_path):
        """total_rows subtracts junction overlaps across the chain."""
        out = tmp_path / "rows.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(CATALOG_ALPHA),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        body = parse_json(proc.stdout)
        assert body["total_rows"] == 30


class TestTieBreak:
    def test_hidden_tie_break_seq(self, require_binary, tmp_path):
        """equal overlap successors pick lowest seq then lowest id on verifier fixture."""
        cat = HIDDEN_CATALOG_DIR / "tie_break.clfc"
        frags = HIDDEN_CATALOGS["tie_break"]
        expected = plan_expected(frags)
        out = tmp_path / "tie.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(cat),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        body = parse_json(proc.stdout)
        assert body["fragment_ids"][1] == 6
        assert body["fragment_ids"] == expected["fragment_ids"]
        assert body["total_rows"] == expected["total_rows"]


class TestExportShadowIngest:
    def test_hidden_ingest_export_shadow_snapshot(self, require_binary, tmp_path):
        """Hidden export_shadow ingest snapshot matches reference chain and digest fields."""
        cat = HIDDEN_CATALOG_DIR / "export_shadow.clfc"
        frags = HIDDEN_CATALOGS["export_shadow"]
        snap = tmp_path / "shadow_snap.json"
        proc = run_cmd(
            "ingest",
            "--catalog",
            str(cat),
            "--policy",
            str(POLICY_DEFAULT),
            "--snapshot",
            str(snap),
        )
        assert proc.returncode == 0, proc.stderr
        body = json.loads(snap.read_text(encoding="utf-8"))
        ref = staging_snapshot_reference(frags)
        assert body["chain_fragment_ids"] == ref["chain_fragment_ids"]
        assert body["chain_overlaps"] == ref["chain_overlaps"]
        assert body["catalog_digest"] == ref["catalog_digest"]


class TestStrictOverlap:
    def test_strict_policy_min_overlap(self, require_binary, tmp_path):
        """strict policy min_row_overlap 5 filters short junctions on verifier fixture."""
        cat = HIDDEN_CATALOG_DIR / "strict_overlap.clfc"
        frags = HIDDEN_CATALOGS["strict_overlap"]
        out = tmp_path / "out.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(cat),
            "--policy",
            str(POLICY_STRICT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        expected = plan_expected(
            frags,
            {
                "min_row_overlap": 5,
                "case_fold_ascii": True,
                "required_replica_mask": 0x0007,
                "scan_cost_per_byte": 2,
                "scan_penalty_per_gap": 20,
            },
        )
        body = parse_json(proc.stdout)
        assert body["fragment_ids"] == expected["fragment_ids"]
        assert body["total_rows"] == expected["total_rows"]


class TestBundledCatalogs:
    def test_bundled_catalog_files_exist(self, require_binary):
        """Sample catalogs under /app/data/catalogs/ exist for local experimentation."""
        for name in ("alpha", "beta", "case_column", "replica_edge"):
            path = Path(f"/app/data/catalogs/{name}.clfc")
            assert path.is_file(), f"missing bundled catalog {path}"


class TestStagingPipeline:
    def test_ingest_writes_snapshot(self, require_binary, tmp_path):
        """ingest writes /app/state/compaction-snapshot.json with contract fields."""
        snap = tmp_path / "snap.json"
        proc = run_cmd(
            "ingest",
            "--catalog",
            str(CATALOG_ALPHA),
            "--policy",
            str(POLICY_DEFAULT),
            "--snapshot",
            str(snap),
        )
        assert proc.returncode == 0, proc.stderr
        assert snap.is_file()
        body = json.loads(snap.read_text(encoding="utf-8"))
        ref = staging_snapshot_reference(ALPHA_FRAGMENTS)
        assert body["version"] == 1
        assert body["open_fragment_id"] == ref["open_fragment_id"]
        assert body["chain_fragment_ids"] == ref["chain_fragment_ids"]
        assert body["chain_overlaps"] == ref["chain_overlaps"]
        assert body["replica_summary"] == ref["replica_summary"]
        assert body["catalog_digest"] == ref["catalog_digest"]

    def test_plan_writes_default_snapshot(self, require_binary, tmp_path):
        """plan leaves a staging snapshot at /app/state/compaction-snapshot.json."""
        out = tmp_path / "plan.json"
        if SNAPSHOT_PATH.exists():
            SNAPSHOT_PATH.unlink()
        proc = run_cmd(
            "plan",
            "--catalog",
            str(CATALOG_ALPHA),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        assert SNAPSHOT_PATH.is_file()
        body = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        ref = staging_snapshot_reference(ALPHA_FRAGMENTS)
        assert body["chain_fragment_ids"] == ref["chain_fragment_ids"]

    def test_export_requires_snapshot(self, require_binary, tmp_path):
        """export without prior ingest fails with STAGING_ERROR."""
        missing = tmp_path / "missing.json"
        proc = run_cmd(
            "export",
            "--catalog",
            str(CATALOG_ALPHA),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(tmp_path / "out.json"),
            "--snapshot",
            str(missing),
        )
        assert proc.returncode == 1
        assert proc.stderr.strip() == "STAGING_ERROR"

    def test_ingest_export_matches_plan(self, require_binary, tmp_path):
        """ingest then export produces the same plan JSON as plan."""
        snap = tmp_path / "snap.json"
        out_ingest = tmp_path / "via_export.json"
        out_plan = tmp_path / "via_plan.json"
        iproc = run_cmd(
            "ingest",
            "--catalog",
            str(CATALOG_BETA),
            "--policy",
            str(POLICY_DEFAULT),
            "--snapshot",
            str(snap),
        )
        assert iproc.returncode == 0, iproc.stderr
        eproc = run_cmd(
            "export",
            "--catalog",
            str(CATALOG_BETA),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out_ingest),
            "--snapshot",
            str(snap),
        )
        assert eproc.returncode == 0, eproc.stderr
        pproc = run_cmd(
            "plan",
            "--catalog",
            str(CATALOG_BETA),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out_plan),
        )
        assert pproc.returncode == 0, pproc.stderr
        assert parse_json(eproc.stdout) == parse_json(pproc.stdout)

    def test_staging_doc_exists(self, require_binary):
        """Staging contract doc cited in instruction is present."""
        assert STAGING_DOC.is_file()

    def test_plan_snapshot_bytes_stable_repeat(self, require_binary, tmp_path):
        """Two plan runs on the same catalog write identical snapshot bytes."""
        out = tmp_path / "plan.json"
        if SNAPSHOT_PATH.exists():
            SNAPSHOT_PATH.unlink()
        proc1 = run_cmd(
            "plan",
            "--catalog",
            str(CATALOG_ALPHA),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc1.returncode == 0, proc1.stderr
        first = SNAPSHOT_PATH.read_bytes()
        proc2 = run_cmd(
            "plan",
            "--catalog",
            str(CATALOG_ALPHA),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc2.returncode == 0, proc2.stderr
        second = SNAPSHOT_PATH.read_bytes()
        assert first == second

    def test_export_stale_snapshot_digest(self, require_binary, tmp_path):
        """export rejects snapshots whose catalog_digest does not match the catalog."""
        snap = tmp_path / "stale.json"
        iproc = run_cmd(
            "ingest",
            "--catalog",
            str(CATALOG_ALPHA),
            "--policy",
            str(POLICY_DEFAULT),
            "--snapshot",
            str(snap),
        )
        assert iproc.returncode == 0, iproc.stderr
        body = json.loads(snap.read_text(encoding="utf-8"))
        body["catalog_digest"] = "0" * 16
        snap.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        eproc = run_cmd(
            "export",
            "--catalog",
            str(CATALOG_ALPHA),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(tmp_path / "out.json"),
            "--snapshot",
            str(snap),
        )
        assert eproc.returncode == 1
        assert eproc.stderr.strip() == "STALE_SNAPSHOT"

    def test_repair_writes_snapshot_reset_token(self, require_binary, tmp_path):
        """repair records a one-shot snapshot reset token for the catalog digest."""
        token = Path("/app/state/repair-snapshot-reset.token")
        if token.exists():
            token.unlink()
        broken = dict(ALPHA_EXPECT)
        broken["fragment_ids"] = [2, 1, 3]
        broken["row_overlap_lengths"] = [1, 1]
        broken["total_rows"] = 1
        broken["fingerprint"] = "deadbeefdeadbeef"
        plan_path = tmp_path / "broken.json"
        out_path = tmp_path / "fixed.json"
        write_plan(plan_path, broken)
        proc = run_cmd(
            "repair",
            "--plan",
            str(plan_path),
            "--catalog",
            str(CATALOG_ALPHA),
            "--out",
            str(out_path),
        )
        assert proc.returncode == 0, proc.stderr
        assert token.is_file()
        digest = staging_snapshot_reference(ALPHA_FRAGMENTS)["catalog_digest"]
        assert token.read_text(encoding="utf-8").strip() == digest


class TestHiddenTraps:
    def test_hidden_row_wrap_plan(self, require_binary, tmp_path):
        """row_wrap hidden catalog plan matches reference merge order and fingerprint."""
        cat = HIDDEN_CATALOG_DIR / "row_wrap.clfc"
        frags = HIDDEN_CATALOGS["row_wrap"]
        expected = plan_expected(frags)
        out = tmp_path / "wrap.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(cat),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        body = parse_json(proc.stdout)
        assert body["fragment_ids"] == expected["fragment_ids"]
        assert body["fingerprint"] == expected["fingerprint"]

    def test_hidden_null_byte_column(self, require_binary, tmp_path):
        """null_byte_col hidden catalog normalizes embedded null bytes in column names."""
        cat = HIDDEN_CATALOG_DIR / "null_byte_col.clfc"
        frags = HIDDEN_CATALOGS["null_byte_col"]
        expected = plan_expected(frags)
        out = tmp_path / "null.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(cat),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        body = parse_json(proc.stdout)
        assert body["fragment_ids"] == expected["fragment_ids"]
        assert body["total_rows"] == expected["total_rows"]

    def test_hidden_replica_strict_policy(self, require_binary, tmp_path):
        """replica_strict_fail catalog fails replica_consistent under replica_strict policy."""
        cat = HIDDEN_CATALOG_DIR / "replica_strict_fail.clfc"
        frags = HIDDEN_CATALOGS["replica_strict_fail"]
        expected = plan_expected(frags, REPLICA_STRICT_POLICY)
        out = tmp_path / "rstrict.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(cat),
            "--policy",
            str(POLICY_REPLICA_STRICT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        body = parse_json(proc.stdout)
        assert body["replica_consistent"] is False
        assert body["fingerprint"] == expected["fingerprint"]

    def test_hidden_gap_chain_scan_penalty(self, require_binary, tmp_path):
        """gap_chain hidden catalog scan_cost includes fragmentation penalty when index is non-zero."""
        cat = HIDDEN_CATALOG_DIR / "gap_chain.clfc"
        frags = HIDDEN_CATALOGS["gap_chain"]
        expected = plan_expected(frags)
        out = tmp_path / "gap.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(cat),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        body = parse_json(proc.stdout)
        assert body["scan_cost_units"] == expected["scan_cost_units"]
        assert body["fragmentation_index"] == expected["fragmentation_index"]

    def test_hidden_poison_norm_tie(self, require_binary, tmp_path):
        """poison_norm_tie hidden catalog plan matches reference merge order and total_rows."""
        cat = HIDDEN_CATALOG_DIR / "poison_norm_tie.clfc"
        frags = HIDDEN_CATALOGS["poison_norm_tie"]
        expected = plan_expected(frags)
        out = tmp_path / "poison.json"
        proc = run_cmd(
            "plan",
            "--catalog",
            str(cat),
            "--policy",
            str(POLICY_DEFAULT),
            "--out",
            str(out),
        )
        assert proc.returncode == 0, proc.stderr
        body = parse_json(proc.stdout)
        assert body["fragment_ids"] == expected["fragment_ids"]
        assert body["total_rows"] == expected["total_rows"]
        assert body["fingerprint"] == expected["fingerprint"]

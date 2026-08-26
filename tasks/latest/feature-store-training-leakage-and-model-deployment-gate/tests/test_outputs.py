"""Verifier tests for feature-store training-run lineage audit outputs.

Golden expectations for the default bundled DuckDB live under tests/reference/.
Live policy/graph-binding mutations and probe databases reject hardcoded fixtures.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import duckdb

REFERENCE = Path("/tests/reference")
OUTPUT = Path("/app/output")
DATA = Path("/app/data")
POLICY_PATH = DATA / "governance_policy.json"
GRAPH_PATH = DATA / "graph_emission.prod.json"
MANIFEST = json.loads((DATA / "governance_manifest.json").read_text())
CASES = json.loads((REFERENCE / "compliance_cases.json").read_text())
VERDICTS = OUTPUT / "training_run_verdicts.json"
FINDINGS = OUTPUT / "leakage_findings.csv"
LINEAGE_DOT = OUTPUT / "rejected_run_lineage.dot"
CONTRACT = OUTPUT / "training_compliance_contract.md"
CLI = "/app/bin/feature_lineage_verdict"
CONTRACT_BINDING_PATH = DATA / "contract_binding_requirements.json"
if not CONTRACT_BINDING_PATH.is_file():
    CONTRACT_BINDING_PATH = REFERENCE / "contract_binding_requirements.json"
CONTRACT_BINDING = json.loads(CONTRACT_BINDING_PATH.read_text(encoding="utf-8"))


def _policy() -> dict:
    return json.loads(POLICY_PATH.read_text())


def _graph_doc() -> dict:
    return json.loads(GRAPH_PATH.read_text())


def _production_binding(doc: dict | None = None) -> dict:
    raw = doc if doc is not None else _graph_doc()
    return dict(raw["production_binding"])


def _contract_required_tokens() -> set[str]:
    tokens = {
        *CONTRACT_BINDING["required_filenames"],
        *CONTRACT_BINDING["required_ledger_tokens"],
        *CONTRACT_BINDING["required_violation_literals"],
    }
    marker_field = CONTRACT_BINDING.get("required_binding_marker_from_manifest_field")
    if marker_field:
        tokens.add(MANIFEST[marker_field])
    else:
        tokens.add(MANIFEST["binding_marker"])
    pb = _production_binding()
    tokens.add(pb["ledger_timestamp_column"])
    tokens.add(pb["digraph_name"])
    return tokens


def _run_cli(db_path: str, policy_path: str, output_dir: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    output_dir.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            CLI,
            "--evaluate-training-runs",
            "--db",
            db_path,
            "--policy",
            policy_path,
            "--output",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _rerun_seed() -> None:
    result = _run_cli(
        "/app/data/lineage.duckdb",
        str(POLICY_PATH),
        OUTPUT,
    )
    assert result.returncode == 0, result.stderr


class TestFeatureStoreTrainingCompliance:
    def test_required_outputs_exist(self) -> None:
        assert VERDICTS.exists()
        assert FINDINGS.exists()
        assert LINEAGE_DOT.exists()
        assert CONTRACT.exists()

    def test_training_compliance_contract_covers_binding(self) -> None:
        text = CONTRACT.read_text()
        lower = text.lower()
        for token in _contract_required_tokens():
            if token == MANIFEST["binding_marker"]:
                assert token in lower, f"contract missing binding marker {token!r}"
            else:
                assert token in text or token in lower, f"contract missing required token {token!r}"
        if CONTRACT_BINDING.get("committed_at_must_be_informational_only"):
            assert "committed_at" in lower
            assert "informational" in lower
        assert (DATA / "contract_binding_requirements.json").is_file()

    def test_contract_rejects_scratch_and_envelope_digraphs(self) -> None:
        """Contract must cite production digraph/freshness, not decoy digraph names."""
        text = CONTRACT.read_text()
        doc = _graph_doc()
        pb = doc["production_binding"]
        scratch = doc["counsel_scratch"]["production_binding"]
        assert pb["digraph_name"] in text
        assert pb["ledger_timestamp_column"] in text
        assert scratch["digraph_name"] not in text
        assert "scratch-leak" not in text
        # Envelope-root digraph is a lab decoy distinct from production_binding.
        assert doc["digraph_name"] != pb["digraph_name"]
        assert doc["digraph_name"] not in text

    def test_training_run_verdicts_match_golden_reference(self) -> None:
        produced = json.loads(VERDICTS.read_text())
        expected = json.loads((REFERENCE / "training_run_verdicts.json").read_text())
        assert produced == expected
        policy = _policy()
        assert produced["policy_version"] == policy["policy_version"]
        assert produced["ledger_cutoff"] == policy["ledger_cutoff"]
        assert produced["registry_base_url"] == policy["registry_base_url"]

    def test_leakage_findings_match_golden_reference(self) -> None:
        produced = FINDINGS.read_text()
        expected = (REFERENCE / "leakage_findings.csv").read_text()
        assert produced == expected
        # Details must follow production templates, not envelope-root decoys.
        assert "available after cutoff" in produced
        assert "posted after cutoff" not in produced

    def test_rejected_run_lineage_matches_golden_reference(self) -> None:
        produced = LINEAGE_DOT.read_text()
        expected = (REFERENCE / "rejected_run_lineage.dot").read_text()
        assert produced == expected
        pb = _production_binding()
        assert f"digraph {pb['digraph_name']} {{" in produced
        assert pb["pass2_parent_suffix"] in produced

    def test_rejected_run_lineage_is_valid_graphviz(self) -> None:
        result = subprocess.run(
            ["dot", "-Tsvg", str(LINEAGE_DOT)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_leaking_scenario_flags_post_cutoff_feature(self) -> None:
        report = json.loads(VERDICTS.read_text())
        leaking = next(row for row in report["runs"] if row["run_id"] == "leaking")
        assert leaking["approved"] is False
        assert leaking["violations"][0]["violation_type"] == "leaking_feature"
        assert "rolling_balance_7d@v4" in leaking["violations"][0]["detail"]

    def test_unapproved_model_scenario_uses_registry_policy(self) -> None:
        report = json.loads(VERDICTS.read_text())
        row = next(row for row in report["runs"] if row["run_id"] == "unapproved_model")
        assert row["approved"] is False
        assert row["violations"][0]["violation_type"] == "unapproved_model"
        assert "ranking_shadow" in row["violations"][0]["detail"]

    def test_clean_scenario_is_fully_approved(self) -> None:
        report = json.loads(VERDICTS.read_text())
        clean = next(row for row in report["runs"] if row["run_id"] == "clean")
        assert clean["approved"] is True
        assert clean["violations"] == []

    def test_graph_annotates_violations(self) -> None:
        dot = LINEAGE_DOT.read_text()
        pb = _production_binding()
        assert f"digraph {pb['digraph_name']} {{" in dot
        assert f"rankdir={pb['rankdir']};" in dot
        assert 'xlabel="VIOLATION: leaking_feature"' in dot
        assert 'xlabel="VIOLATION: unapproved_model"' in dot
        assert "balances_ledger" in dot
        assert "orders_ledger" in dot

    def test_rerun_is_deterministic(self) -> None:
        before_verdicts = VERDICTS.read_text()
        before_dot = LINEAGE_DOT.read_text()
        _rerun_seed()
        assert VERDICTS.read_text() == before_verdicts
        assert LINEAGE_DOT.read_text() == before_dot

    def test_evaluation_run_order_matches_manifest(self) -> None:
        report = json.loads(VERDICTS.read_text())
        run_ids = [row["run_id"] for row in report["runs"]]
        order = _production_binding()["run_manifest_order"]
        expected = list(CASES["run_id_order"])
        if "DESC" in order.upper():
            expected = list(reversed(expected))
        assert run_ids == expected

    def test_graph_feature_emission_order_leaking(self) -> None:
        dot = LINEAGE_DOT.read_text()
        cluster = dot.split("subgraph cluster_leaking")[1].split("}")[0]
        positions = [cluster.index(f'label="{name}"') for name in CASES["graph_feature_order"]]
        assert positions == sorted(positions)

    def test_graph_includes_rolling_to_purchase_edge(self) -> None:
        dot = LINEAGE_DOT.read_text()
        child, parent = CASES["graph_edge_child_parent"]
        suffix = _production_binding()["pass2_parent_suffix"]
        assert f'"leaking_{child}" -> "leaking_{parent}{suffix}"' in dot

    def test_leaking_violation_uses_ledger_as_of(self) -> None:
        report = json.loads(VERDICTS.read_text())
        leaking = next(row for row in report["runs"] if row["run_id"] == CASES["leaking_run_id"])
        detail = leaking["violations"][0]["detail"]
        assert detail.startswith(f"feature {CASES['leaking_feature']} ")
        tmpl = _production_binding()["violation_detail_templates"]["leaking_feature"]
        # Must follow production_binding template, not envelope-root / scratch decoys.
        assert "available after cutoff" in detail
        assert "posted after cutoff" not in detail
        assert "scratch-leak" not in detail
        assert "{feature_name}" in tmpl

    def test_ingest_trap_ignores_committed_at_ingest_stamp(self) -> None:
        report = json.loads(VERDICTS.read_text())
        row = next(row for row in report["runs"] if row["run_id"] == CASES["ingest_trap_run_id"])
        assert row["approved"] is True
        assert row["violations"] == []

    def test_cutoff_boundary_allows_equal_ledger_as_of(self) -> None:
        report = json.loads(VERDICTS.read_text())
        row = next(row for row in report["runs"] if row["run_id"] == CASES["cutoff_boundary_run_id"])
        assert row["approved"] is True
        assert row["violations"] == []

    def test_version_bind_uses_matched_ledger_version(self) -> None:
        report = json.loads(VERDICTS.read_text())
        row = next(row for row in report["runs"] if row["run_id"] == CASES["version_bind_run_id"])
        assert row["approved"] is True
        assert row["violations"] == []

    def test_dual_leak_emits_two_leakage_violations(self) -> None:
        report = json.loads(VERDICTS.read_text())
        row = next(row for row in report["runs"] if row["run_id"] == CASES["dual_leak_run_id"])
        assert row["approved"] is False
        assert [v["violation_type"] for v in row["violations"]] == [
            "leaking_feature",
            "leaking_feature",
        ]
        assert "credit_utilization@v1" in row["violations"][0]["detail"]
        assert "rolling_balance_7d@v4" in row["violations"][1]["detail"]

    def test_dual_leak_graph_feature_emission_order(self) -> None:
        dot = LINEAGE_DOT.read_text()
        cluster = dot.split("subgraph cluster_dual_leak")[1].split("}")[0]
        positions = [
            cluster.index(f'label="{name}"')
            for name in CASES["dual_leak_graph_feature_order"]
        ]
        assert positions == sorted(positions)

    def test_rejected_graph_cluster_order(self) -> None:
        dot = LINEAGE_DOT.read_text()
        rejected = [run_id for run_id in CASES["run_id_order"] if f"subgraph cluster_{run_id}" in dot]
        assert rejected == sorted(rejected)
        positions = [dot.index(f"subgraph cluster_{run_id}") for run_id in rejected]
        assert positions == sorted(positions)

    def test_both_flags_emits_leakage_and_registry_violations(self) -> None:
        report = json.loads(VERDICTS.read_text())
        row = next(row for row in report["runs"] if row["run_id"] == CASES["both_flags_run_id"])
        assert row["approved"] is False
        types = [v["violation_type"] for v in row["violations"]]
        assert types == ["leaking_feature", "unapproved_model"]

    def test_both_flags_graph_annotates_dual_violations(self) -> None:
        dot = LINEAGE_DOT.read_text()
        cluster = dot.split("subgraph cluster_both_flags")[1].split("  }")[0]
        assert 'xlabel="VIOLATION: unapproved_model"' in cluster
        assert 'xlabel="VIOLATION: leaking_feature"' in cluster

    def test_ignores_counsel_scratch_graph_binding(self) -> None:
        """Root counsel_scratch.production_binding must not drive digraph/suffix/details."""
        doc = _graph_doc()
        scratch = doc["counsel_scratch"]["production_binding"]
        prod = doc["production_binding"]
        assert scratch["digraph_name"] != prod["digraph_name"]
        assert scratch["pass2_parent_suffix"] != prod["pass2_parent_suffix"]
        dot = LINEAGE_DOT.read_text()
        assert f"digraph {prod['digraph_name']} {{" in dot
        assert f"digraph {scratch['digraph_name']} {{" not in dot
        assert f"rankdir={prod['rankdir']};" in dot
        assert prod["pass2_parent_suffix"] in dot
        assert scratch["pass2_parent_suffix"] not in dot
        report = json.loads(VERDICTS.read_text())
        leaking = next(row for row in report["runs"] if row["run_id"] == "leaking")
        assert "scratch-leak" not in leaking["violations"][0]["detail"]
        assert "available after cutoff" in leaking["violations"][0]["detail"]

    def _run_audit(self, db_path: Path, output_dir: Path) -> subprocess.CompletedProcess:
        return _run_cli(str(db_path), str(POLICY_PATH), output_dir)

    def test_probe_database_verdicts(self) -> None:
        cutoff = _policy()["ledger_cutoff"]
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "probe.duckdb"
            out = Path(tmp) / "output"
            out.mkdir(parents=True, exist_ok=True)
            con = duckdb.connect(str(db))
            con.execute(
                """
                CREATE TABLE feature_ledger (
                    feature_name VARCHAR, feature_version VARCHAR,
                    ledger_as_of TIMESTAMP, committed_at TIMESTAMP, source_table VARCHAR
                );
                CREATE TABLE run_manifest (run_id VARCHAR, model_name VARCHAR, scenario VARCHAR);
                CREATE TABLE run_features (run_id VARCHAR, feature_name VARCHAR, feature_version VARCHAR);
                CREATE TABLE lineage_edges (child_feature VARCHAR, parent_feature VARCHAR);
                """
            )
            con.execute(
                "INSERT INTO feature_ledger VALUES (?, ?, ?, ?, ?)",
                ["probe_feature", "v9", "2024-08-01 00:00:00", "2024-03-01 00:00:00", "probe_src"],
            )
            con.execute(
                "INSERT INTO run_manifest VALUES (?, ?, ?)",
                ["probe_leak", "fraud_guard_prod", "probe"],
            )
            con.execute(
                "INSERT INTO run_features VALUES (?, ?, ?)",
                ["probe_leak", "probe_feature", "v9"],
            )
            con.close()

            result = self._run_audit(db, out)
            assert result.returncode == 0, result.stderr
            report = json.loads((out / "training_run_verdicts.json").read_text())
            row = next(r for r in report["runs"] if r["run_id"] == "probe_leak")
            assert row["approved"] is False
            assert row["violations"][0]["violation_type"] == "leaking_feature"
            assert cutoff in row["violations"][0]["detail"]

    def test_probe_version_join_prevents_false_leak(self) -> None:
        cutoff = _policy()["ledger_cutoff"]
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "probe_version.duckdb"
            out = Path(tmp) / "output"
            con = duckdb.connect(str(db))
            con.execute(
                """
                CREATE TABLE feature_ledger (
                    feature_name VARCHAR, feature_version VARCHAR,
                    ledger_as_of TIMESTAMP, committed_at TIMESTAMP, source_table VARCHAR
                );
                CREATE TABLE run_manifest (run_id VARCHAR, model_name VARCHAR, scenario VARCHAR);
                CREATE TABLE run_features (run_id VARCHAR, feature_name VARCHAR, feature_version VARCHAR);
                CREATE TABLE lineage_edges (child_feature VARCHAR, parent_feature VARCHAR);
                """
            )
            con.execute(
                "INSERT INTO feature_ledger VALUES (?, ?, ?, ?, ?)",
                ["bind_probe", "v1", "2024-04-01 00:00:00", "2024-01-01 00:00:00", "probe_src"],
            )
            con.execute(
                "INSERT INTO feature_ledger VALUES (?, ?, ?, ?, ?)",
                ["bind_probe", "v2", "2024-08-01 00:00:00", "2024-01-01 00:00:00", "probe_src"],
            )
            con.execute(
                "INSERT INTO run_manifest VALUES (?, ?, ?)",
                ["probe_version_ok", "fraud_guard_prod", "probe"],
            )
            con.execute(
                "INSERT INTO run_features VALUES (?, ?, ?)",
                ["probe_version_ok", "bind_probe", "v1"],
            )
            con.close()

            result = self._run_audit(db, out)
            assert result.returncode == 0, result.stderr
            report = json.loads((out / "training_run_verdicts.json").read_text())
            row = next(r for r in report["runs"] if r["run_id"] == "probe_version_ok")
            assert row["approved"] is True, (
                f"version-qualified bind must ignore newer ledger row for bind_probe v2 (cutoff {cutoff})"
            )
            assert row["violations"] == []

    def test_probe_rejects_hardcoded_bundled_verdicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "probe.duckdb"
            out = Path(tmp) / "output"
            out.mkdir(parents=True, exist_ok=True)
            con = duckdb.connect(str(db))
            con.execute(
                """
                CREATE TABLE feature_ledger (
                    feature_name VARCHAR, feature_version VARCHAR,
                    ledger_as_of TIMESTAMP, committed_at TIMESTAMP, source_table VARCHAR
                );
                CREATE TABLE run_manifest (run_id VARCHAR, model_name VARCHAR, scenario VARCHAR);
                CREATE TABLE run_features (run_id VARCHAR, feature_name VARCHAR, feature_version VARCHAR);
                CREATE TABLE lineage_edges (child_feature VARCHAR, parent_feature VARCHAR);
                """
            )
            con.execute(
                "INSERT INTO feature_ledger VALUES (?, ?, ?, ?, ?)",
                ["probe_clean", "v1", "2024-01-01 00:00:00", "2024-01-01 00:00:00", "probe_src"],
            )
            con.execute(
                "INSERT INTO run_manifest VALUES (?, ?, ?)",
                ["probe_clean", "fraud_guard_prod", "probe"],
            )
            con.execute(
                "INSERT INTO run_features VALUES (?, ?, ?)",
                ["probe_clean", "probe_clean", "v1"],
            )
            con.close()

            shutil.copy(REFERENCE / "training_run_verdicts.json", out / "training_run_verdicts.json")
            bundled = json.loads((out / "training_run_verdicts.json").read_text())
            assert all(row["run_id"] != "probe_clean" for row in bundled["runs"])

            result = self._run_audit(db, out)
            assert result.returncode == 0, result.stderr
            report = json.loads((out / "training_run_verdicts.json").read_text())
            row = next(r for r in report["runs"] if r["run_id"] == "probe_clean")
            assert row["approved"] is True

    def test_live_policy_cutoff_mutation(self) -> None:
        """Mutating ledger_cutoff must change which features leak."""
        original = POLICY_PATH.read_text()
        try:
            policy = json.loads(original)
            # Move cutoff after all seed ledger_as_of values → no leaks from freshness
            policy["ledger_cutoff"] = "2030-01-01 00:00:00"
            POLICY_PATH.write_text(json.dumps(policy, indent=2))
            _rerun_seed()
            report = json.loads(VERDICTS.read_text())
            leaking = next(row for row in report["runs"] if row["run_id"] == "leaking")
            # Still may have only registry issues; freshness leaks must clear
            assert all(v["violation_type"] != "leaking_feature" for v in leaking["violations"])
            assert report["ledger_cutoff"] == "2030-01-01 00:00:00"
            assert FINDINGS.read_text() != (REFERENCE / "leakage_findings.csv").read_text()
        finally:
            POLICY_PATH.write_text(original)
            _rerun_seed()

    def test_live_graph_digraph_and_suffix_mutation(self) -> None:
        """Mutating digraph_name / pass2_parent_suffix must change DOT output."""
        original = GRAPH_PATH.read_text()
        before = LINEAGE_DOT.read_text()
        try:
            doc = json.loads(original)
            doc["production_binding"]["digraph_name"] = "mutated_store_lineage"
            doc["production_binding"]["rankdir"] = "LR"
            doc["production_binding"]["pass2_parent_suffix"] = "_mut"
            GRAPH_PATH.write_text(json.dumps(doc, indent=2))
            _rerun_seed()
            dot = LINEAGE_DOT.read_text()
            assert dot != before, "must react to production_binding digraph/suffix/rankdir"
            assert "digraph mutated_store_lineage {" in dot
            assert "rankdir=LR;" in dot
            assert "_mut" in dot
            assert "digraph rejected_store_lineage {" not in dot
            assert "_origin" not in dot
        finally:
            GRAPH_PATH.write_text(original)
            _rerun_seed()

    def test_live_violation_template_mutation(self) -> None:
        """Mutating violation_detail_templates must change verdict/CSV detail strings."""
        original = GRAPH_PATH.read_text()
        try:
            doc = json.loads(original)
            doc["production_binding"]["violation_detail_templates"]["leaking_feature"] = (
                "feature {feature_name}@{feature_version} LIVE-LEAK {ledger_cutoff}"
            )
            doc["production_binding"]["violation_detail_templates"]["unapproved_model"] = (
                "model {model_name} LIVE-DENY"
            )
            GRAPH_PATH.write_text(json.dumps(doc, indent=2))
            _rerun_seed()
            report = json.loads(VERDICTS.read_text())
            leaking = next(row for row in report["runs"] if row["run_id"] == "leaking")
            assert "LIVE-LEAK" in leaking["violations"][0]["detail"]
            assert "available after cutoff" not in leaking["violations"][0]["detail"]
            unapproved = next(row for row in report["runs"] if row["run_id"] == "unapproved_model")
            assert "LIVE-DENY" in unapproved["violations"][0]["detail"]
            assert VERDICTS.read_text() != (REFERENCE / "training_run_verdicts.json").read_text()
        finally:
            GRAPH_PATH.write_text(original)
            _rerun_seed()

    def test_live_pass1_feature_order_mutation(self) -> None:
        """Mutating production_binding.pass1_feature_order_by must change graph emission."""
        original = GRAPH_PATH.read_text()
        before_dot = LINEAGE_DOT.read_text()
        before_cluster = before_dot.split("subgraph cluster_dual_leak")[1].split("}")[0]
        names = CASES["dual_leak_graph_feature_order"]
        before_account = before_cluster.index(f'label="{names[0]}"')
        before_credit = before_cluster.index(f'label="{names[1]}"')
        assert before_account < before_credit, "seed production binding must emit ASC feature order"
        try:
            doc = json.loads(original)
            doc["production_binding"]["pass1_feature_order_by"] = "feature_name DESC"
            GRAPH_PATH.write_text(json.dumps(doc, indent=2))
            _rerun_seed()
            after_dot = LINEAGE_DOT.read_text()
            assert after_dot != before_dot, (
                "must react to production_binding.pass1_feature_order_by (not envelope/scratch decoys)"
            )
            cluster = after_dot.split("subgraph cluster_dual_leak")[1].split("}")[0]
            pos_first = cluster.index(f'label="{names[0]}"')
            pos_second = cluster.index(f'label="{names[1]}"')
            assert pos_second < pos_first, "DESC order must emit credit before account"
        finally:
            GRAPH_PATH.write_text(original)
            _rerun_seed()

    def test_live_registry_json_field_mutation(self) -> None:
        """Reading deployment_approved instead of approved must flip ranking_shadow runs."""
        original = GRAPH_PATH.read_text()
        before = VERDICTS.read_text()
        try:
            doc = json.loads(original)
            doc["production_binding"]["registry_json_field"] = "deployment_approved"
            GRAPH_PATH.write_text(json.dumps(doc, indent=2))
            _rerun_seed()
            after = VERDICTS.read_text()
            assert after != before, (
                "must react to production_binding.registry_json_field (not hardcoded/scratch decoys)"
            )
            report = json.loads(after)
            unapproved = next(row for row in report["runs"] if row["run_id"] == "unapproved_model")
            assert unapproved["approved"] is True
            assert unapproved["violations"] == []
            both = next(row for row in report["runs"] if row["run_id"] == "both_flags")
            assert both["approved"] is False
            assert [v["violation_type"] for v in both["violations"]] == ["leaking_feature"]
            assert "unapproved_model" not in FINDINGS.read_text()
        finally:
            GRAPH_PATH.write_text(original)
            _rerun_seed()

    def test_live_freshness_column_mutation(self) -> None:
        """Switching freshness to committed_at must flag ingest_trap and clear ledger_as_of-only leaks."""
        original = GRAPH_PATH.read_text()
        before = FINDINGS.read_text()
        try:
            doc = json.loads(original)
            doc["production_binding"]["ledger_timestamp_column"] = "committed_at"
            GRAPH_PATH.write_text(json.dumps(doc, indent=2))
            _rerun_seed()
            after = FINDINGS.read_text()
            assert after != before, (
                "must react to production_binding.ledger_timestamp_column "
                "(not envelope-root / counsel_scratch decoys)"
            )
            report = json.loads(VERDICTS.read_text())
            ingest = next(row for row in report["runs"] if row["run_id"] == "ingest_trap")
            assert ingest["approved"] is False
            assert ingest["violations"][0]["violation_type"] == "leaking_feature"
            assert "session_length" in ingest["violations"][0]["detail"]
            # rolling_balance_7d has early committed_at — must not leak under committed_at freshness
            leaking = next(row for row in report["runs"] if row["run_id"] == "leaking")
            assert all(
                "rolling_balance_7d" not in v["detail"] for v in leaking["violations"]
            ), "committed_at freshness must not flag rolling_balance_7d via ledger_as_of"
            assert after != (REFERENCE / "leakage_findings.csv").read_text()
        finally:
            GRAPH_PATH.write_text(original)
            _rerun_seed()

    def test_live_run_manifest_order_mutation(self) -> None:
        """Mutating run_manifest_order to DESC must reverse verdict run order."""
        original = GRAPH_PATH.read_text()
        before_ids = [row["run_id"] for row in json.loads(VERDICTS.read_text())["runs"]]
        assert before_ids == CASES["run_id_order"]
        try:
            doc = json.loads(original)
            doc["production_binding"]["run_manifest_order"] = "run_id DESC"
            GRAPH_PATH.write_text(json.dumps(doc, indent=2))
            _rerun_seed()
            report = json.loads(VERDICTS.read_text())
            run_ids = [row["run_id"] for row in report["runs"]]
            assert run_ids != before_ids, (
                "must react to production_binding.run_manifest_order (not scratch DESC decoy)"
            )
            assert run_ids == list(reversed(CASES["run_id_order"]))
        finally:
            GRAPH_PATH.write_text(original)
            _rerun_seed()

    def test_live_digraph_mutation_updates_evaluator_outputs(self) -> None:
        """Hardcoded digraph/suffix must fail when production_binding changes."""
        original = GRAPH_PATH.read_text()
        try:
            doc = json.loads(original)
            doc["production_binding"]["digraph_name"] = "live_contract_digraph"
            doc["production_binding"]["pass2_parent_suffix"] = "_live"
            GRAPH_PATH.write_text(json.dumps(doc, indent=2))
            _rerun_seed()
            dot = LINEAGE_DOT.read_text()
            assert "digraph live_contract_digraph {" in dot
            assert "_live" in dot
            assert "rejected_store_lineage" not in dot
            assert "_origin" not in dot
        finally:
            GRAPH_PATH.write_text(original)
            _rerun_seed()

    def test_live_graph_binding_updates_contract_brief(self) -> None:
        """Contract brief must re-emit live digraph + freshness when bindings change."""
        original = GRAPH_PATH.read_text()
        before = CONTRACT.read_text()
        assert "rejected_store_lineage" in before
        assert "ledger_as_of" in before
        try:
            doc = json.loads(original)
            doc["production_binding"]["digraph_name"] = "live_contract_digraph"
            doc["production_binding"]["ledger_timestamp_column"] = "committed_at"
            GRAPH_PATH.write_text(json.dumps(doc, indent=2))
            _rerun_seed()
            text = CONTRACT.read_text()
            tokens = _contract_required_tokens()
            assert "live_contract_digraph" in tokens
            assert "committed_at" in tokens
            for token in tokens:
                if token == MANIFEST["binding_marker"]:
                    assert token in text.lower(), f"contract missing binding marker {token!r}"
                else:
                    assert token in text or token in text.lower(), (
                        f"contract missing required token {token!r}"
                    )
            assert "live_contract_digraph" in text
            assert "rejected_store_lineage" not in text
            # Freshness column token must be the live value (committed_at), still
            # described as the compared column — not a stale ledger_as_of citation.
            assert "feature_ledger.committed_at" in text or (
                "committed_at" in text and "ledger_as_of" not in text
            )
            assert text != before
        finally:
            GRAPH_PATH.write_text(original)
            _rerun_seed()

"""Behavior tests for Iris Go module provenance loader."""
import json
import os
import re
import sqlite3
import subprocess

import jsonschema
import pytest

from audit_reference import (
    WORKSPACE,
    assert_graph_equivalent,
    assert_two_space_json,
    canonical_digest_lines,
    expected_digest_sha256,
    expected_normalized_graph,
    load_json,
    output_path,
    read_text,
    run_cli,
    write_double_prefix_checksum_probe_export,
    write_exclude_toolchain_probe_export,
    write_first_wins_replace_probe_export,
    write_isolated_paths,
    write_m1_probe_export,
    write_retract_replace_probe_export,
    write_same_path_replace_probe_export,
    write_test_flag_probe_export,
)

GRAPH_PATH = output_path("normalized-graph.json")
SCHEMA_PATH = os.path.join(WORKSPACE, "schemas", "normalized-graph.schema.json")
SQLITE_PATH = "/workspace/state/module-provenance.sqlite3"
DIGEST_PATH = "/workspace/output/dependency-digest.txt"
CHECKSUM_PATH = "/workspace/output/digest-checksum.sha256"
VERIFY_SCRIPT = "/workspace/iris-provenance/scripts/verify-provenance.sh"
NORMALIZE_CMD = [
    "normalize",
    "--export",
    "/workspace/data/proxy-exports/iris-gateway-provenance.json",
    "--paths",
    "/workspace/config/paths.json",
    "--out",
    GRAPH_PATH,
]
MIGRATE_CMD = [
    "migrate",
    "--graph",
    GRAPH_PATH,
    "--paths",
    "/workspace/config/paths.json",
]


@pytest.fixture(scope="module")
def prepared_workspace():
    """Normalize and migrate the shipped export once for shared happy-path reads."""
    run = run_cli(NORMALIZE_CMD)
    assert run.returncode == 0, run.stderr
    run = run_cli(MIGRATE_CMD)
    assert run.returncode == 0, run.stderr
    return load_json(GRAPH_PATH)


class TestNormalize:
    def test_normalize_exits_zero(self):
        """Normalize subcommand must succeed on the shipped proxy export."""
        run = run_cli(NORMALIZE_CMD)
        assert run.returncode == 0, run.stderr

    def test_normalize_matches_reference(self):
        """Normalized graph must match the reference ignoring array order."""
        run = run_cli(NORMALIZE_CMD)
        assert run.returncode == 0, run.stderr
        assert_graph_equivalent(load_json(GRAPH_PATH), expected_normalized_graph())
        assert_two_space_json(GRAPH_PATH)

    def test_normalize_two_space_json(self, prepared_workspace):
        """Normalized graph must use two-space JSON with trailing newline."""
        assert_two_space_json(GRAPH_PATH)

    def test_normalize_schema_valid(self, prepared_workspace):
        """Normalized graph must validate against the shipped schema."""
        with open(SCHEMA_PATH, encoding="utf-8") as handle:
            schema = json.load(handle)
        jsonschema.validate(prepared_workspace, schema)

    def test_normalize_module_count(self, prepared_workspace):
        """Eight reachable module versions remain after retract/replace/decoy/scaffold filtering."""
        assert len(prepared_workspace["modules"]) == 8

    def test_normalize_replace_edge_for_net(self, prepared_workspace):
        """Gateway edge to x/net must use replace kind at v0.21.0."""
        matches = [
            e
            for e in prepared_workspace["edges"]
            if e["parent_path"] == "github.com/iris-labs/gateway"
            and e["child_path"] == "golang.org/x/net"
        ]
        assert len(matches) == 1
        assert matches[0]["child_version"] == "v0.21.0"
        assert matches[0]["edge_kind"] == "replace"

    def test_normalize_retract_replaced_by_valid_target(self, prepared_workspace):
        """Retracted legacy-cache require must resolve to cache-modern via replace."""
        paths = {m["module_path"] for m in prepared_workspace["modules"]}
        assert "github.com/iris-labs/legacy-cache" not in paths
        assert "github.com/iris-labs/cache-modern" in paths
        matches = [
            e
            for e in prepared_workspace["edges"]
            if e["parent_path"] == "github.com/iris-labs/authkit"
            and e["child_path"] == "github.com/iris-labs/cache-modern"
        ]
        assert len(matches) == 1
        assert matches[0]["edge_kind"] == "replace"
        assert matches[0]["child_version"] == "v2.0.0"

    def test_normalize_retracted_module_absent(self, prepared_workspace):
        """Retracted legacy-cache must not appear in modules or edges."""
        paths = {m["module_path"] for m in prepared_workspace["modules"]}
        assert "github.com/iris-labs/legacy-cache" not in paths
        for edge in prepared_workspace["edges"]:
            assert edge["child_path"] != "github.com/iris-labs/legacy-cache"
            assert edge["parent_path"] != "github.com/iris-labs/legacy-cache"

    def test_normalize_unreachable_decoy_absent(self, prepared_workspace):
        """Unreachable module_index decoys must not appear in the graph."""
        paths = {m["module_path"] for m in prepared_workspace["modules"]}
        assert "github.com/iris-labs/debug-tools" not in paths
        assert "github.com/iris-labs/cache-shim" not in paths

    def test_normalize_stale_net_version_absent(self, prepared_workspace):
        """Stale golang.org/x/net v0.17.0 must not remain after replace resolution."""
        nets = [
            m
            for m in prepared_workspace["modules"]
            if m["module_path"] == "golang.org/x/net"
        ]
        assert len(nets) == 1
        assert nets[0]["version"] == "v0.21.0"

    def test_normalize_indirect_edge_absent(self, prepared_workspace):
        """Indirect telemetry require edges must not be emitted."""
        matches = [
            e
            for e in prepared_workspace["edges"]
            if e["parent_path"] == "github.com/iris-labs/telemetry"
            and e["child_path"] == "github.com/iris-labs/authkit"
        ]
        assert matches == []
        assert len(prepared_workspace["edges"]) == 7

    def test_normalize_sha256_prefix_stripped(self, prepared_workspace):
        """Checksums with a sha256: prefix must store the bare digest."""
        crypto = [
            m
            for m in prepared_workspace["modules"]
            if m["module_path"] == "golang.org/x/crypto" and m["version"] == "v0.14.0"
        ]
        assert len(crypto) == 1
        assert not crypto[0]["checksum_sha256"].startswith("sha256:")
        assert not crypto[0]["checksum_sha256"].startswith("h1:")
        assert crypto[0]["checksum_sha256"] == "fe" * 32

    def test_normalize_arrays_sorted(self, prepared_workspace):
        """Normalized arrays must follow the binding sort keys."""
        expected = expected_normalized_graph()
        assert prepared_workspace["modules"] == expected["modules"]
        assert prepared_workspace["edges"] == expected["edges"]
        assert prepared_workspace["replace_rules"] == expected["replace_rules"]

    def test_normalize_telemetry_incompatible_stripped(self, prepared_workspace):
        """Telemetry version must drop the incompatible suffix."""
        telem = [
            m
            for m in prepared_workspace["modules"]
            if m["module_path"] == "github.com/iris-labs/telemetry"
        ]
        assert len(telem) == 1
        assert telem[0]["version"] == "v0.2.0"

    def test_normalize_export_missing_exits_nonzero(self):
        """Missing export must exit non-zero on stderr and leave --out unwritten."""
        out = "/tmp/iris-prov-missing-export-out.json"
        if os.path.isfile(out):
            os.remove(out)
        run = run_cli(
            [
                "normalize",
                "--export",
                "/workspace/output/missing-export.json",
                "--paths",
                "/workspace/config/paths.json",
                "--out",
                out,
            ]
        )
        assert run.returncode != 0
        assert "export not found" in run.stderr
        assert not os.path.isfile(out)

    def test_normalize_export_meta_incomplete_exits_nonzero(self):
        """Incomplete export_meta must exit on stderr without writing --out."""
        bad_export = "/tmp/iris-prov-bad-export-meta.json"
        out = "/tmp/iris-prov-bad-meta-graph.json"
        if os.path.isfile(out):
            os.remove(out)
        with open(bad_export, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "export_meta": {"proxy_id": "bad"},
                    "retract_queue": [],
                    "module_index": {},
                },
                handle,
                indent=2,
            )
            handle.write("\n")
        run = run_cli(
            [
                "normalize",
                "--export",
                bad_export,
                "--paths",
                "/workspace/config/paths.json",
                "--out",
                out,
            ]
        )
        assert run.returncode != 0
        assert "export_meta incomplete" in run.stderr
        assert not os.path.isfile(out)

    def test_normalize_verifier_probe_export(self):
        """Normalize must handle verifier-written probe exports and isolated paths."""
        base = "/tmp/iris-prov-normalize-probe"
        os.makedirs(base, exist_ok=True)
        probe = os.path.join(base, "export.json")
        probe_out = os.path.join(base, "normalized-graph.json")
        write_m1_probe_export(probe)
        paths = write_isolated_paths(
            base,
            schema_version="iris-probe-schema-9",
            proxy_export=probe,
        )
        expected = expected_normalized_graph(probe, paths)
        run = run_cli(
            [
                "normalize",
                "--export",
                probe,
                "--paths",
                paths,
                "--out",
                probe_out,
            ]
        )
        assert run.returncode == 0, run.stderr
        actual = load_json(probe_out)
        assert_graph_equivalent(actual, expected)
        assert actual["schema_version"] == "iris-probe-schema-9"
        paths = {m["module_path"] for m in actual["modules"]}
        assert paths == {"github.com/probe/widget", "github.com/probe/lib"}
        assert all(e["child_path"] != "github.com/probe/legacy" for e in actual["edges"])
        assert "github.com/probe/orphan" not in paths
        assert "github.com/probe/metrics" not in paths
        assert "github.com/probe/shim" not in paths
        lib = [m for m in actual["modules"] if m["module_path"] == "github.com/probe/lib"][0]
        assert lib["checksum_sha256"] == "cd" * 32

    def test_normalize_retract_replace_probe_independent(self):
        """Retracted require replaced by a valid module must match probe expected graph."""
        base = "/tmp/iris-prov-retract-replace-probe"
        os.makedirs(base, exist_ok=True)
        probe = os.path.join(base, "export.json")
        probe_out = os.path.join(base, "normalized-graph.json")
        write_retract_replace_probe_export(probe)
        paths = write_isolated_paths(
            base,
            schema_version="iris-probe-retract-replace",
            proxy_export=probe,
        )
        expected = expected_normalized_graph(probe, paths)
        run = run_cli(
            [
                "normalize",
                "--export",
                probe,
                "--paths",
                paths,
                "--out",
                probe_out,
            ]
        )
        assert run.returncode == 0, run.stderr
        actual = load_json(probe_out)
        assert_graph_equivalent(actual, expected)
        paths_set = {m["module_path"] for m in actual["modules"]}
        assert "github.com/probe/broken-dep" not in paths_set
        assert "github.com/probe/fixed-dep" in paths_set
        assert actual["edges"] == [
            {
                "parent_path": "github.com/probe/app",
                "parent_version": "v1.0.0",
                "child_path": "github.com/probe/fixed-dep",
                "child_version": "v2.0.0",
                "edge_kind": "replace",
            }
        ]

    def test_normalize_same_path_replace_edge_kind_probe(self):
        """Same-path replace must emit edge_kind replace with independent expected graph."""
        base = "/tmp/iris-prov-same-path-replace-probe"
        os.makedirs(base, exist_ok=True)
        probe = os.path.join(base, "export.json")
        probe_out = os.path.join(base, "normalized-graph.json")
        write_same_path_replace_probe_export(probe)
        paths = write_isolated_paths(
            base,
            schema_version="iris-probe-same-path-replace",
            proxy_export=probe,
        )
        expected = expected_normalized_graph(probe, paths)
        run = run_cli(
            [
                "normalize",
                "--export",
                probe,
                "--paths",
                paths,
                "--out",
                probe_out,
            ]
        )
        assert run.returncode == 0, run.stderr
        actual = load_json(probe_out)
        assert_graph_equivalent(actual, expected)
        matches = [
            e
            for e in actual["edges"]
            if e["parent_path"] == "github.com/probe/svc"
            and e["child_path"] == "github.com/probe/libx"
        ]
        assert len(matches) == 1
        assert matches[0]["child_version"] == "v0.4.0"
        assert matches[0]["edge_kind"] == "replace"
        assert matches[0]["edge_kind"] != "require"
        versions = {
            m["version"]
            for m in actual["modules"]
            if m["module_path"] == "github.com/probe/libx"
        }
        assert versions == {"v0.4.0"}
        assert len(actual["replace_rules"]) == 1
        assert all(r["old_path"] != "github.com/probe/unused" for r in actual["replace_rules"])
        assert "github.com/probe/unused" not in {
            m["module_path"] for m in actual["modules"]
        }

    def test_normalize_unused_replace_absent(self, prepared_workspace):
        """Unused replace directives on reachable units must not enter replace_rules."""
        assert len(prepared_workspace["replace_rules"]) == 2
        assert all(
            r["old_path"] != "golang.org/x/sys" for r in prepared_workspace["replace_rules"]
        )
        paths = {m["module_path"] for m in prepared_workspace["modules"]}
        assert "golang.org/x/sys" not in paths

    def test_normalize_exclude_and_toolchain_absent(self, prepared_workspace):
        """exclude_queue and toolchain requires must not appear in modules or edges."""
        paths = {m["module_path"] for m in prepared_workspace["modules"]}
        assert "github.com/iris-labs/telemetry-stub" not in paths
        assert "golang.org/x/mod" not in paths
        for edge in prepared_workspace["edges"]:
            assert edge["child_path"] != "github.com/iris-labs/telemetry-stub"
            assert edge["child_path"] != "golang.org/x/mod"

    def test_normalize_explicit_false_scaffold_flags_retained(self, prepared_workspace):
        """Requires with explicit JSON false scaffold flags must still enter the graph."""
        paths = {m["module_path"] for m in prepared_workspace["modules"]}
        assert "github.com/iris-labs/metrics-bridge" in paths
        bridge_edges = [
            e
            for e in prepared_workspace["edges"]
            if e["child_path"] == "github.com/iris-labs/metrics-bridge"
        ]
        assert len(bridge_edges) == 1
        assert bridge_edges[0]["edge_kind"] == "require"
        assert bridge_edges[0]["parent_path"] == "github.com/iris-labs/gateway"

    def test_normalize_root_unit_path_not_nested_decoy(self, prepared_workspace):
        """Root checksum must come from the unit whose path matches the module path."""
        gateway = [
            m
            for m in prepared_workspace["modules"]
            if m["module_path"] == "github.com/iris-labs/gateway"
        ]
        assert len(gateway) == 1
        assert gateway[0]["checksum_sha256"] != "ee" * 32
        assert gateway[0]["checksum_sha256"].startswith("8f3c2a1b")

    def test_normalize_published_sum_not_used(self, prepared_workspace):
        """published_sum decoy must not override unit checksum for crypto."""
        crypto = [
            m
            for m in prepared_workspace["modules"]
            if m["module_path"] == "golang.org/x/crypto" and m["version"] == "v0.14.0"
        ]
        assert len(crypto) == 1
        assert crypto[0]["checksum_sha256"] == "fe" * 32
        assert crypto[0]["checksum_sha256"] != "aa" * 32

    def test_normalize_go_version_from_version_block(self, prepared_workspace):
        """go_version must come from the module_index version block, not unit fields."""
        gateway = [
            m
            for m in prepared_workspace["modules"]
            if m["module_path"] == "github.com/iris-labs/gateway"
        ]
        assert len(gateway) == 1
        assert gateway[0]["go_version"] == "1.22.0"
        assert gateway[0]["go_version"] != "1.99.0"

    def test_normalize_shadow_index_absent(self, prepared_workspace):
        """shadow_index decoys must not appear in the resolved module graph."""
        paths = {m["module_path"] for m in prepared_workspace["modules"]}
        assert "github.com/iris-labs/shadow-root" not in paths

    def test_normalize_dual_crypto_versions_retained(self, prepared_workspace):
        """Distinct crypto versions reached via different parents must both remain."""
        cryptos = [
            m
            for m in prepared_workspace["modules"]
            if m["module_path"] == "golang.org/x/crypto"
        ]
        versions = sorted(m["version"] for m in cryptos)
        assert versions == ["v0.12.0", "v0.14.0"]

    def test_normalize_path_only_replace_decoy_ignored(self, prepared_workspace):
        """Replace matching requires path and version; path-only decoy must not win."""
        nets = [
            m
            for m in prepared_workspace["modules"]
            if m["module_path"] == "golang.org/x/net"
        ]
        assert len(nets) == 1
        assert nets[0]["version"] == "v0.21.0"
        assert all(r["old_version"] != "v0.16.0" for r in prepared_workspace["replace_rules"])

    def test_normalize_development_require_absent(self, prepared_workspace):
        """development requires must not create edges or modules."""
        paths = {m["module_path"] for m in prepared_workspace["modules"]}
        assert "golang.org/x/text" not in paths
        for edge in prepared_workspace["edges"]:
            assert edge["child_path"] != "golang.org/x/text"

    def test_normalize_exclude_toolchain_probe_independent(self):
        """Exclude, toolchain, nested-unit, and published_sum traps must hold on probe export."""
        base = "/tmp/iris-prov-exclude-toolchain-probe"
        os.makedirs(base, exist_ok=True)
        probe = os.path.join(base, "export.json")
        probe_out = os.path.join(base, "normalized-graph.json")
        write_exclude_toolchain_probe_export(probe)
        paths = write_isolated_paths(
            base,
            schema_version="iris-probe-exclude-toolchain",
            proxy_export=probe,
        )
        expected = expected_normalized_graph(probe, paths)
        run = run_cli(
            [
                "normalize",
                "--export",
                probe,
                "--paths",
                paths,
                "--out",
                probe_out,
            ]
        )
        assert run.returncode == 0, run.stderr
        actual = load_json(probe_out)
        assert_graph_equivalent(actual, expected)
        mods = {m["module_path"]: m for m in actual["modules"]}
        assert set(mods) == {
            "github.com/probe/core",
            "github.com/probe/lib",
            "github.com/probe/metrics",
        }
        assert mods["github.com/probe/core"]["checksum_sha256"] == "55" * 32
        assert mods["github.com/probe/lib"]["checksum_sha256"] == "66" * 32
        assert mods["github.com/probe/metrics"]["checksum_sha256"] == "99" * 32
        assert "github.com/probe/tooldep" not in mods
        assert "github.com/probe/banned" not in mods

    def test_normalize_first_wins_replace_for_net(self, prepared_workspace):
        """Two replaces match x/net v0.17.0; the first listed row (v0.21.0) must win."""
        rules = [
            r
            for r in prepared_workspace["replace_rules"]
            if r["scope_path"] == "github.com/iris-labs/gateway"
            and r["old_path"] == "golang.org/x/net"
        ]
        assert len(rules) == 1
        assert rules[0]["old_version"] == "v0.17.0"
        assert rules[0]["new_version"] == "v0.21.0"
        assert all(r["new_version"] != "v0.99.0" for r in prepared_workspace["replace_rules"])
        nets = {
            m["version"]
            for m in prepared_workspace["modules"]
            if m["module_path"] == "golang.org/x/net"
        }
        assert nets == {"v0.21.0"}
        assert "v0.99.0" not in nets
        for edge in prepared_workspace["edges"]:
            assert not (
                edge["child_path"] == "golang.org/x/net"
                and edge["child_version"] == "v0.99.0"
            )

    def test_normalize_exclude_pre_replace_does_not_drop_replacement(self, prepared_workspace):
        """exclude_queue of the pre-replace require must not drop a healthy replace target."""
        nets = [
            m
            for m in prepared_workspace["modules"]
            if m["module_path"] == "golang.org/x/net"
        ]
        assert len(nets) == 1
        assert nets[0]["version"] == "v0.21.0"
        edges = [
            e
            for e in prepared_workspace["edges"]
            if e["child_path"] == "golang.org/x/net"
        ]
        assert len(edges) == 1
        assert edges[0]["child_version"] == "v0.21.0"
        assert edges[0]["edge_kind"] == "replace"
        assert all(
            not (e["child_path"] == "golang.org/x/net" and e["child_version"] == "v0.17.0")
            for e in prepared_workspace["edges"]
        )

    def test_normalize_single_prefix_checksum_strip(self, prepared_workspace):
        """A h1:sha256: checksum must lose only the first prefix, keeping sha256:."""
        bridge = [
            m
            for m in prepared_workspace["modules"]
            if m["module_path"] == "github.com/iris-labs/metrics-bridge"
        ]
        assert len(bridge) == 1
        checksum = bridge[0]["checksum_sha256"]
        assert checksum == "sha256:" + "b0" * 32
        assert checksum.startswith("sha256:")
        assert not checksum.startswith("h1:")
        assert checksum != "b0" * 32

    def test_normalize_test_flag_require_skipped(self, prepared_workspace):
        """A require flagged test true must be scaffolding; test false must still walk."""
        paths = {m["module_path"] for m in prepared_workspace["modules"]}
        assert "github.com/iris-labs/test-harness" not in paths
        for edge in prepared_workspace["edges"]:
            assert edge["child_path"] != "github.com/iris-labs/test-harness"
        assert "github.com/iris-labs/metrics-bridge" in paths

    def test_normalize_rejects_archive_register_tokens(self):
        """Wiring the legacy archive register must not match the live cutover golden."""
        base = "/tmp/iris-prov-archive-register-probe"
        os.makedirs(base, exist_ok=True)
        paths = write_isolated_paths(
            base,
            schema_version="iris-probe-archive-register",
            cutover_register="/workspace/config/archive-cutover-register.json",
        )
        expected_live = expected_normalized_graph(
            paths_path="/workspace/config/paths.json"
        )
        expected_archive = expected_normalized_graph(paths_path=paths)
        assert expected_archive != expected_live
        archive_paths = {m["module_path"] for m in expected_archive["modules"]}
        assert "github.com/iris-labs/metrics-bridge" not in archive_paths
        live_nets = {
            m["version"]
            for m in expected_live["modules"]
            if m["module_path"] == "golang.org/x/net"
        }
        archive_nets = {
            m["version"]
            for m in expected_archive["modules"]
            if m["module_path"] == "golang.org/x/net"
        }
        assert live_nets == {"v0.21.0"}
        assert "v0.21.0" not in archive_nets

    def test_normalize_first_wins_replace_probe_independent(self):
        """First matching replace row must win on a verifier-written probe export."""
        base = "/tmp/iris-prov-first-wins-probe"
        os.makedirs(base, exist_ok=True)
        probe = os.path.join(base, "export.json")
        probe_out = os.path.join(base, "normalized-graph.json")
        write_first_wins_replace_probe_export(probe)
        paths = write_isolated_paths(
            base,
            schema_version="iris-probe-first-wins",
            proxy_export=probe,
        )
        expected = expected_normalized_graph(probe, paths)
        run = run_cli(
            ["normalize", "--export", probe, "--paths", paths, "--out", probe_out]
        )
        assert run.returncode == 0, run.stderr
        actual = load_json(probe_out)
        assert_graph_equivalent(actual, expected)
        deps = {
            m["version"]
            for m in actual["modules"]
            if m["module_path"] == "github.com/probe/dep"
        }
        assert deps == {"v0.5.0"}
        edges = [
            e for e in actual["edges"] if e["child_path"] == "github.com/probe/dep"
        ]
        assert len(edges) == 1
        assert edges[0]["child_version"] == "v0.5.0"
        assert edges[0]["edge_kind"] == "replace"
        assert all(r["new_version"] != "v0.9.0" for r in actual["replace_rules"])

    def test_normalize_double_prefix_checksum_probe_independent(self):
        """Only the first checksum prefix is stripped on a verifier-written probe."""
        base = "/tmp/iris-prov-double-prefix-probe"
        os.makedirs(base, exist_ok=True)
        probe = os.path.join(base, "export.json")
        probe_out = os.path.join(base, "normalized-graph.json")
        write_double_prefix_checksum_probe_export(probe)
        paths = write_isolated_paths(
            base,
            schema_version="iris-probe-double-prefix",
            proxy_export=probe,
        )
        expected = expected_normalized_graph(probe, paths)
        run = run_cli(
            ["normalize", "--export", probe, "--paths", paths, "--out", probe_out]
        )
        assert run.returncode == 0, run.stderr
        actual = load_json(probe_out)
        assert_graph_equivalent(actual, expected)
        leaf = [
            m for m in actual["modules"] if m["module_path"] == "github.com/probe/leaf"
        ]
        assert len(leaf) == 1
        assert leaf[0]["checksum_sha256"] == "sha256:" + "cc" * 32
        assert leaf[0]["checksum_sha256"] != "cc" * 32

    def test_normalize_test_flag_probe_independent(self):
        """test-flagged requires drop and explicit test false requires walk on a probe."""
        base = "/tmp/iris-prov-test-flag-probe"
        os.makedirs(base, exist_ok=True)
        probe = os.path.join(base, "export.json")
        probe_out = os.path.join(base, "normalized-graph.json")
        write_test_flag_probe_export(probe)
        paths = write_isolated_paths(
            base,
            schema_version="iris-probe-test-flag",
            proxy_export=probe,
        )
        expected = expected_normalized_graph(probe, paths)
        run = run_cli(
            ["normalize", "--export", probe, "--paths", paths, "--out", probe_out]
        )
        assert run.returncode == 0, run.stderr
        actual = load_json(probe_out)
        assert_graph_equivalent(actual, expected)
        paths_set = {m["module_path"] for m in actual["modules"]}
        assert "github.com/probe/keep" in paths_set
        assert "github.com/probe/skip" not in paths_set
        for edge in actual["edges"]:
            assert edge["child_path"] != "github.com/probe/skip"


class TestMigrate:
    def test_migrate_graph_bytes_preserved(self, prepared_workspace):
        """Migrate must not rewrite normalized-graph.json."""
        before = read_text(GRAPH_PATH)
        run = run_cli(MIGRATE_CMD)
        assert run.returncode == 0, run.stderr
        assert read_text(GRAPH_PATH) == before

    def test_migrate_sqlite_tables_exist(self, prepared_workspace):
        """Migrate must create module_units module_edges replace_rules tables."""
        run = run_cli(MIGRATE_CMD)
        assert run.returncode == 0, run.stderr
        conn = sqlite3.connect(SQLITE_PATH)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            assert {"module_units", "module_edges", "replace_rules"}.issubset(tables)
        finally:
            conn.close()

    def test_migrate_sqlite_column_schema(self, prepared_workspace):
        """SQLite tables must expose the binding-required column names."""
        run = run_cli(MIGRATE_CMD)
        assert run.returncode == 0, run.stderr
        expected = {
            "module_units": {
                "module_path",
                "version",
                "checksum_sha256",
                "go_version",
                "is_root",
            },
            "module_edges": {
                "parent_path",
                "parent_version",
                "child_path",
                "child_version",
                "edge_kind",
            },
            "replace_rules": {
                "scope_path",
                "scope_version",
                "old_path",
                "old_version",
                "new_path",
                "new_version",
            },
        }
        conn = sqlite3.connect(SQLITE_PATH)
        try:
            for table, cols in expected.items():
                found = {
                    row[1]
                    for row in conn.execute(f"PRAGMA table_info({table})")
                }
                assert cols.issubset(found), f"{table} missing columns: {cols - found}"
        finally:
            conn.close()

    def test_migrate_module_row_count(self, prepared_workspace):
        """SQLite must hold one module_units row per normalized graph module."""
        run = run_cli(MIGRATE_CMD)
        assert run.returncode == 0, run.stderr
        conn = sqlite3.connect(SQLITE_PATH)
        try:
            count = conn.execute("SELECT COUNT(*) FROM module_units").fetchone()[0]
            assert count == len(prepared_workspace["modules"])
            assert count == 8
        finally:
            conn.close()

    def test_migrate_root_flag(self, prepared_workspace):
        """Gateway row must be the only is_root value set to 1."""
        run = run_cli(MIGRATE_CMD)
        assert run.returncode == 0, run.stderr
        conn = sqlite3.connect(SQLITE_PATH)
        try:
            roots = conn.execute(
                "SELECT module_path, version FROM module_units WHERE is_root = 1"
            ).fetchall()
            assert roots == [("github.com/iris-labs/gateway", "v1.4.2")]
        finally:
            conn.close()

    def test_migrate_replace_edge_loaded(self, prepared_workspace):
        """Replace edge to golang.org/x/net v0.21.0 must be stored."""
        run = run_cli(MIGRATE_CMD)
        assert run.returncode == 0, run.stderr
        conn = sqlite3.connect(SQLITE_PATH)
        try:
            row = conn.execute(
                """
                SELECT edge_kind FROM module_edges
                WHERE parent_path = ? AND child_path = ? AND child_version = ?
                """,
                ("github.com/iris-labs/gateway", "golang.org/x/net", "v0.21.0"),
            ).fetchone()
            assert row is not None
            assert row[0] == "replace"
        finally:
            conn.close()

    def test_migrate_graph_missing_exits_nonzero(self):
        """Missing graph file must print graph not found and exit non-zero."""
        run = run_cli(
            [
                "migrate",
                "--graph",
                "/workspace/output/missing-graph.json",
                "--paths",
                "/workspace/config/paths.json",
            ]
        )
        assert run.returncode != 0
        assert "graph not found" in run.stderr

    def test_migrate_probe_graph_load(self, prepared_workspace):
        """Migrate must load an isolated probe graph without touching shared paths."""
        base = "/tmp/iris-prov-migrate-probe"
        os.makedirs(base, exist_ok=True)
        paths = write_isolated_paths(base)
        graph_path = os.path.join(base, "probe-graph.json")
        sqlite_path = load_json(paths)["sqlite_path"]
        probe_doc = {
            "schema_version": load_json(paths)["schema_version"],
            "root_module": "github.com/probe/widget",
            "root_version": "v2.0.0",
            "modules": [
                {
                    "module_path": "github.com/probe/widget",
                    "version": "v2.0.0",
                    "checksum_sha256": "ab" * 32,
                    "go_version": "1.22.0",
                    "is_root": True,
                }
            ],
            "edges": [],
            "replace_rules": [],
        }
        with open(graph_path, "w", encoding="utf-8") as handle:
            json.dump(probe_doc, handle, indent=2)
            handle.write("\n")
        shared_before = read_text(GRAPH_PATH)
        shared_sqlite_before = (
            os.path.getmtime(SQLITE_PATH) if os.path.isfile(SQLITE_PATH) else None
        )
        paths_doc = load_json(paths)
        assert paths_doc["database_path"] == SQLITE_PATH
        assert paths_doc["phinx_sqlite_name"] == "/workspace/state/module-provenance"
        assert paths_doc["sqlite_path"] == sqlite_path
        assert paths_doc["sqlite_path"] != paths_doc["database_path"]
        run = run_cli(["migrate", "--graph", graph_path, "--paths", paths])
        assert run.returncode == 0, run.stderr
        assert read_text(GRAPH_PATH) == shared_before
        if shared_sqlite_before is not None:
            assert os.path.getmtime(SQLITE_PATH) == shared_sqlite_before
        assert os.path.isfile(sqlite_path), "migrate must create paths.sqlite_path, not phinx.php default"
        conn = sqlite3.connect(sqlite_path)
        try:
            row = conn.execute(
                "SELECT module_path FROM module_units WHERE is_root = 1"
            ).fetchone()
            assert row[0] == "github.com/probe/widget"
        finally:
            conn.close()
        shared_conn = sqlite3.connect(SQLITE_PATH)
        try:
            shared_roots = {
                r[0]
                for r in shared_conn.execute(
                    "SELECT module_path FROM module_units WHERE is_root = 1"
                )
            }
            assert "github.com/probe/widget" not in shared_roots
        finally:
            shared_conn.close()


class TestDigestExport:
    def test_export_digest_exits_zero(self, prepared_workspace):
        """Export digest subcommand must succeed when SQLite is populated."""
        run = run_cli(MIGRATE_CMD)
        assert run.returncode == 0, run.stderr
        run = run_cli(["export-digest", "--paths", "/workspace/config/paths.json"])
        assert run.returncode == 0, run.stderr

    def test_digest_matches_reference(self, prepared_workspace):
        """Digest lines must match the reference derived from the normalized graph."""
        run = run_cli(MIGRATE_CMD)
        assert run.returncode == 0, run.stderr
        run = run_cli(["export-digest", "--paths", "/workspace/config/paths.json"])
        assert run.returncode == 0, run.stderr
        lines = [ln for ln in read_text(DIGEST_PATH).splitlines() if ln]
        expected_lines = canonical_digest_lines(expected_normalized_graph())
        assert lines == expected_lines
        assert read_text(DIGEST_PATH).endswith("\n")

    def test_checksum_matches_digest_bytes(self, prepared_workspace):
        """Checksum must equal SHA-256 of digest file including trailing newline."""
        run = run_cli(MIGRATE_CMD)
        assert run.returncode == 0, run.stderr
        run = run_cli(["export-digest", "--paths", "/workspace/config/paths.json"])
        assert run.returncode == 0, run.stderr
        expected = expected_digest_sha256(expected_normalized_graph())
        actual_text = read_text(CHECKSUM_PATH)
        assert actual_text == expected + "\n"
        assert re.fullmatch(r"[0-9a-f]{64}\n", actual_text)
        assert " " not in actual_text
        assert "/" not in actual_text

    def test_digest_lines_include_kind_key(self, prepared_workspace):
        """Each digest line must include kind module, edge, or replace only."""
        run = run_cli(MIGRATE_CMD)
        assert run.returncode == 0, run.stderr
        run = run_cli(["export-digest", "--paths", "/workspace/config/paths.json"])
        assert run.returncode == 0, run.stderr
        for line in read_text(DIGEST_PATH).splitlines():
            if not line:
                continue
            doc = json.loads(line)
            assert doc["kind"] in {"module", "edge", "replace"}
            assert doc["kind"] != "replace_rule"
            if doc["kind"] == "module":
                assert isinstance(doc["is_root"], bool)
                assert "\\/" not in line

    def test_verify_script_exits_zero(self, prepared_workspace):
        """verify-provenance.sh must accept a self-consistent digest checksum."""
        run = run_cli(MIGRATE_CMD)
        assert run.returncode == 0, run.stderr
        run = run_cli(["export-digest", "--paths", "/workspace/config/paths.json"])
        assert run.returncode == 0, run.stderr
        verify = subprocess.run(
            [VERIFY_SCRIPT],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert verify.returncode == 0, verify.stderr
        assert "provenance verify ok" in verify.stdout

    def test_verify_script_checksum_mismatch_exits_nonzero(self, prepared_workspace):
        """verify-provenance.sh must reject a checksum that does not match digest bytes."""
        run = run_cli(MIGRATE_CMD)
        assert run.returncode == 0, run.stderr
        run = run_cli(["export-digest", "--paths", "/workspace/config/paths.json"])
        assert run.returncode == 0, run.stderr
        with open(CHECKSUM_PATH, "w", encoding="utf-8") as handle:
            handle.write("0" * 64 + "\n")
        verify = subprocess.run(
            [VERIFY_SCRIPT],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert verify.returncode != 0
        assert "digest checksum mismatch" in verify.stderr
        assert "digest checksum mismatch" not in verify.stdout

    def test_skip_env_rejected(self, prepared_workspace):
        """Skip env must abort on stderr without changing digest or checksum bytes."""
        run = run_cli(MIGRATE_CMD)
        assert run.returncode == 0, run.stderr
        run = run_cli(["export-digest", "--paths", "/workspace/config/paths.json"])
        assert run.returncode == 0, run.stderr
        digest_before = open(DIGEST_PATH, "rb").read()
        checksum_before = open(CHECKSUM_PATH, "rb").read()
        env = os.environ.copy()
        env["IRIS_PROV_SKIP_INTERNAL_PHPUNIT"] = "1"
        verify = subprocess.run(
            [VERIFY_SCRIPT],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        assert verify.returncode != 0
        assert "IRIS_PROV_SKIP_INTERNAL_PHPUNIT" in verify.stderr
        assert open(DIGEST_PATH, "rb").read() == digest_before
        assert open(CHECKSUM_PATH, "rb").read() == checksum_before
        assert "provenance verify ok" not in verify.stdout

    def test_sqlite_missing_exits_nonzero(self):
        """Export must fail without writing digest or checksum when sqlite is absent."""
        base = "/tmp/iris-prov-missing-sqlite"
        paths = write_isolated_paths(base)
        digest = load_json(paths)["digest_path"]
        checksum = load_json(paths)["checksum_path"]
        for path in (digest, checksum):
            if os.path.isfile(path):
                os.remove(path)
        run = run_cli(["export-digest", "--paths", paths])
        assert run.returncode != 0
        assert "sqlite database missing" in run.stderr
        assert not os.path.isfile(digest)
        assert not os.path.isfile(checksum)

    def test_export_digest_isolated_probe(self, prepared_workspace):
        """Export-digest must work against an isolated sqlite populated from a probe graph."""
        base = "/tmp/iris-prov-digest-probe"
        os.makedirs(base, exist_ok=True)
        paths = write_isolated_paths(base)
        graph_path = os.path.join(base, "probe-graph.json")
        probe_doc = {
            "schema_version": load_json(paths)["schema_version"],
            "root_module": "github.com/probe/widget",
            "root_version": "v2.0.0",
            "modules": [
                {
                    "module_path": "github.com/probe/widget",
                    "version": "v2.0.0",
                    "checksum_sha256": "ab" * 32,
                    "go_version": "1.22.0",
                    "is_root": True,
                },
                {
                    "module_path": "github.com/probe/lib",
                    "version": "v1.1.0",
                    "checksum_sha256": "cd" * 32,
                    "go_version": "1.22.0",
                    "is_root": False,
                },
            ],
            "edges": [
                {
                    "parent_path": "github.com/probe/widget",
                    "parent_version": "v2.0.0",
                    "child_path": "github.com/probe/lib",
                    "child_version": "v1.1.0",
                    "edge_kind": "require",
                }
            ],
            "replace_rules": [],
        }
        with open(graph_path, "w", encoding="utf-8") as handle:
            json.dump(probe_doc, handle, indent=2)
            handle.write("\n")
        run = run_cli(["migrate", "--graph", graph_path, "--paths", paths])
        assert run.returncode == 0, run.stderr
        run = run_cli(["export-digest", "--paths", paths])
        assert run.returncode == 0, run.stderr
        digest_path = load_json(paths)["digest_path"]
        checksum_path = load_json(paths)["checksum_path"]
        lines = [ln for ln in read_text(digest_path).splitlines() if ln]
        assert lines == canonical_digest_lines(probe_doc)
        assert read_text(checksum_path).strip() == expected_digest_sha256(probe_doc)

"""Milestone 2 — stale eligibility, gates, digest, and rebuild flags."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REPORT = Path("/app/output/lineage_frontier.json")
LINEAGE = Path("/app/cfg/lineage.toml")
MANIFEST = Path("/app/data/manifest.json")

EMPTY_DIGEST = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

BASELINE = {
    "consumer_harbor": {
        "stale_inputs": ["B"],
        "rebuild_required": True,
        "frontier_digest_hex": "89edb3b2a61c253f62cca46b07e24dbd744a02d68af27e90af2a5e776c8229b7",
    },
    "consumer_lantern": {
        "stale_inputs": ["A"],
        "rebuild_required": True,
        "frontier_digest_hex": "f075979b872eef62ab83ed1d92e51aca403c9fafa0564747cafe7180898150a7",
    },
    "consumer_cinder": {
        "stale_inputs": [],
        "rebuild_required": False,
        "frontier_digest_hex": EMPTY_DIGEST,
    },
    "consumer_slate": {
        "stale_inputs": ["E"],
        "rebuild_required": True,
        "frontier_digest_hex": "046cfd9abb35b258cf8c4e5f901cecf162aedb521b80980bd24e305442b026dd",
    },
    "consumer_quartz": {
        "stale_inputs": ["B"],
        "rebuild_required": True,
        "frontier_digest_hex": "8483fa80036ceda4c0b18aef36997480f51e5bce220592d95e7d2f28d9edff3c",
    },
    "consumer_marble": {
        "stale_inputs": ["B", "C", "D"],
        "rebuild_required": True,
        "frontier_digest_hex": "50a4ed6d6826faf2499326b53e16629480c8a3510f75ab37494feeb1ec9d7777",
    },
    "consumer_pioneer": {
        "stale_inputs": [],
        "rebuild_required": False,
        "frontier_digest_hex": EMPTY_DIGEST,
    },
    "consumer_cairn": {
        "stale_inputs": [],
        "rebuild_required": False,
        "frontier_digest_hex": EMPTY_DIGEST,
    },
    "consumer_keystone": {
        "stale_inputs": ["D", "E"],
        "rebuild_required": True,
        "frontier_digest_hex": "8d961422d0e3e70c12290510f5394d49ee94cfcdf6490687a63973a7eb5445d5",
    },
}


def _doc() -> dict[str, object]:
    return json.loads(REPORT.read_text(encoding="utf-8"))


def _rebuild() -> None:
    REPORT.unlink(missing_ok=True)
    subprocess.run(["/app/scripts/frontier.sh"], check=True, cwd="/app")


class TestMilestone2:
    def test_fixture_stale_matrix_after_rebuild(self) -> None:
        """A fresh rebuild matches stale flags and digests on every manifest consumer."""
        _rebuild()
        doc = _doc()
        for consumer_id, want in BASELINE.items():
            block = doc["consumers"][consumer_id]
            assert block["stale_inputs"] == want["stale_inputs"]
            assert block["rebuild_required"] == want["rebuild_required"]
            assert block["frontier_digest_hex"] == want["frontier_digest_hex"]

    def test_gate_active_at_min_rows_boundary(self) -> None:
        """Gate readiness uses at-or-above comparison on watched min_rows."""
        from eng.gates import gate_active

        graph = {
            "nodes": {"E": {"depends": ["C"]}},
            "gates": {"E": {"watch": "C", "min_rows": 10}},
        }
        at_floor = {"C": {"node": "C", "hash": "hc", "gen": 1, "seq": 1, "rows": 10}}
        below_floor = {"C": {"node": "C", "hash": "hc", "gen": 1, "seq": 1, "rows": 9}}
        assert gate_active(graph, "E", at_floor) is True
        assert gate_active(graph, "E", below_floor) is False

    def test_metrics_digest_matches_join_contract(self) -> None:
        """Visible digests use one joined hash over stale node rows."""
        from eng.row_canon import frontier_digest_hex

        graph = {
            "nodes": {
                "A": {"depends": []},
                "B": {"depends": ["A"]},
                "C": {"depends": ["B"]},
            },
            "gates": {},
        }
        latest = {
            "B": {"node": "B", "hash": "hb", "gen": 1, "seq": 2},
            "C": {"node": "C", "hash": "hc", "gen": 1, "seq": 3},
        }
        lines = [
            json.dumps(
                {"node": node, "hash": value, "gen": gen, "seq": seq},
                separators=(",", ":"),
            )
            for node, value, gen, seq in [("C", "hc", 1, 3), ("B", "hb", 1, 2)]
        ]
        joined = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
        bundled = hashlib.sha256(
            b"".join(
                json.dumps(
                    {"node": node, "hash": h, "gen": g, "seq": s},
                    separators=(",", ":"),
                ).encode("utf-8")
                for node, h, g, s in [("B", "hb", 1, 2), ("C", "hc", 1, 3)]
            )
        ).hexdigest()
        assert joined != bundled
        assert frontier_digest_hex(["B", "C"], latest, graph) == joined
        sort_keys_digest = hashlib.sha256(
            "\n".join(
                json.dumps(
                    {"gen": gen, "hash": value, "node": node, "seq": seq},
                    separators=(",", ":"),
                )
                for node, value, gen, seq in [("C", "hc", 1, 3), ("B", "hb", 1, 2)]
            ).encode("utf-8")
        ).hexdigest()
        assert frontier_digest_hex(["B", "C"], latest, graph) != sort_keys_digest

    def test_reverse_topo_fork_sibling_order(self) -> None:
        """Stale fork siblings use reverse forward-topo order, not alphabetical stale order."""
        from eng.dag import forward_topo, reverse_topo
        from eng.row_canon import frontier_digest_hex

        graph = {
            "nodes": {
                "A": {"depends": []},
                "B": {"depends": ["A"]},
                "C": {"depends": ["A"]},
                "D": {"depends": ["B", "C"]},
            },
            "gates": {},
        }
        stale = ["B", "C", "D"]
        forward = forward_topo(stale, graph)
        assert reverse_topo(stale, graph) == list(reversed(forward))
        assert reverse_topo(stale, graph) == ["D", "C", "B"]
        latest = {
            "B": {"node": "B", "hash": "hb", "gen": 1, "seq": 2},
            "C": {"node": "C", "hash": "hc", "gen": 1, "seq": 3},
            "D": {"node": "D", "hash": "hd", "gen": 1, "seq": 4},
        }
        alpha_lines = [
            json.dumps(
                {"node": node, "hash": latest[node]["hash"], "gen": 1, "seq": latest[node]["seq"]},
                separators=(",", ":"),
            )
            for node in sorted(stale)
        ]
        alpha_digest = hashlib.sha256("\n".join(alpha_lines).encode("utf-8")).hexdigest()
        assert frontier_digest_hex(stale, latest, graph) != alpha_digest

    def test_pack_audit_wired_row_canon_digest(self) -> None:
        """Wired pack_audit emits reverse-topo digest rows for stale finish metadata."""
        from eng.pack_audit import audit_consumer

        graph = {
            "nodes": {
                "A": {"depends": []},
                "B": {"depends": ["A"]},
                "C": {"depends": ["A"]},
                "D": {"depends": ["B", "C"]},
            },
            "gates": {},
        }
        latest = {
            "B": {"node": "B", "hash": "hb", "gen": 1, "seq": 2},
            "C": {"node": "C", "hash": "hc", "gen": 1, "seq": 3},
            "D": {"node": "D", "hash": "hd", "gen": 1, "seq": 4},
        }
        consumer = {
            "subscribes": ["B", "C", "D"],
            "last_materialized": {"B": "old_b", "C": "old_c", "D": "old_d"},
        }
        lines = [
            json.dumps(
                {"node": node, "hash": latest[node]["hash"], "gen": 1, "seq": latest[node]["seq"]},
                separators=(",", ":"),
            )
            for node in ["D", "C", "B"]
        ]
        want = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
        block = audit_consumer(graph, consumer, latest, fan_in_require_all=False)
        assert block["frontier_digest_hex"] == want
        assert block["rebuild_required"] is True
        assert block["stale_inputs"] == ["B", "C", "D"]

    def test_latest_finish_keeps_highest_seq(self) -> None:
        """Projected latest map keeps the highest-seq finish when a node repeats."""
        from eng.registry import latest_finish

        events = [
            {"kind": "finish", "node": "B", "gen": 1, "seq": 2, "hash": "hb_old", "rows": 1},
            {"kind": "finish", "node": "B", "gen": 1, "seq": 9, "hash": "hb_new", "rows": 2},
            {"kind": "finish", "node": "C", "gen": 1, "seq": 3, "hash": "hc", "rows": 1},
        ]
        latest = latest_finish(events)
        assert latest["B"]["hash"] == "hb_new"
        assert int(latest["B"]["seq"]) == 9

    def test_digest_rejects_trailing_newline_body(self) -> None:
        """frontier_digest_hex must not append a trailing newline after the final row."""
        from eng.row_canon import frontier_digest_hex

        graph = {
            "nodes": {"B": {"depends": []}, "C": {"depends": ["B"]}},
            "gates": {},
        }
        latest = {
            "B": {"node": "B", "hash": "hb", "gen": 1, "seq": 2},
            "C": {"node": "C", "hash": "hc", "gen": 1, "seq": 3},
        }
        lines = [
            json.dumps({"node": "C", "hash": "hc", "gen": 1, "seq": 3}, separators=(",", ":")),
            json.dumps({"node": "B", "hash": "hb", "gen": 1, "seq": 2}, separators=(",", ":")),
        ]
        clean = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
        trailed = hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()
        assert clean != trailed
        assert frontier_digest_hex(["B", "C"], latest, graph) == clean

    def test_rebuild_required_pairs_with_stale_set(self) -> None:
        """rebuild_required is true exactly when stale_inputs is non-empty."""
        from eng.subscribe import rebuild_required

        assert rebuild_required([]) is False
        assert rebuild_required(["B"]) is True

    def test_rebuild_required_when_stale_missing_from_latest(self) -> None:
        """Stale ids with no projected finish row still force rebuild_required true."""
        from eng.pack_audit import audit_consumer

        graph = {
            "nodes": {
                "A": {"depends": []},
                "B": {"depends": ["A"]},
            },
            "gates": {},
        }
        consumer = {
            "subscribes": ["B"],
            "last_materialized": {},
        }
        block = audit_consumer(graph, consumer, latest={}, fan_in_require_all=False)
        assert block["stale_inputs"] == ["B"]
        assert block["rebuild_required"] is True
        assert block["frontier_digest_hex"] == EMPTY_DIGEST

    def test_feed_frontier_differs_from_wired_digest(self) -> None:
        """Offline feed_frontier digests must not match the wired reverse-topo join."""
        from eng.feed_frontier import frontier_digest_hex as feed_digest
        from eng.row_canon import frontier_digest_hex as wired_digest

        graph = {
            "nodes": {
                "A": {"depends": []},
                "B": {"depends": ["A"]},
                "C": {"depends": ["A"]},
                "D": {"depends": ["B", "C"]},
            },
            "gates": {},
        }
        stale = ["B", "C", "D"]
        latest = {
            "B": {"node": "B", "hash": "hb", "gen": 1, "seq": 2},
            "C": {"node": "C", "hash": "hc", "gen": 1, "seq": 3},
            "D": {"node": "D", "hash": "hd", "gen": 1, "seq": 4},
        }
        assert feed_digest(stale, latest, graph) != wired_digest(stale, latest, graph)

    def test_diamond_reverse_topo_digest_order(self) -> None:
        """Diamond stale subgraph digests as reverse forward-topo, not sibling lexical alone."""
        from eng.dag import forward_topo, reverse_topo
        from eng.row_canon import frontier_digest_hex

        graph = {
            "nodes": {
                "A": {"depends": []},
                "B": {"depends": ["A"]},
                "C": {"depends": ["A"]},
                "D": {"depends": ["B", "C"]},
            },
            "gates": {},
        }
        stale = ["A", "B", "C", "D"]
        forward = forward_topo(stale, graph)
        assert forward == ["A", "B", "C", "D"]
        assert reverse_topo(stale, graph) == ["D", "C", "B", "A"]
        latest = {
            "A": {"node": "A", "hash": "ha", "gen": 1, "seq": 1},
            "B": {"node": "B", "hash": "hb", "gen": 1, "seq": 2},
            "C": {"node": "C", "hash": "hc", "gen": 1, "seq": 3},
            "D": {"node": "D", "hash": "hd", "gen": 1, "seq": 4},
        }
        lines = [
            json.dumps(
                {"node": node, "hash": latest[node]["hash"], "gen": 1, "seq": latest[node]["seq"]},
                separators=(",", ":"),
            )
            for node in ["D", "C", "B", "A"]
        ]
        want = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
        assert frontier_digest_hex(stale, latest, graph) == want

    def test_fan_in_blocks_until_parents_ready(self) -> None:
        """With fan_in_require_all, a child stays out of stale until every parent has finished."""
        from eng.subscribe import stale_inputs

        graph = {
            "nodes": {
                "A": {"depends": []},
                "B": {"depends": []},
                "C": {"depends": ["A", "B"]},
            },
            "gates": {},
        }
        consumer = {
            "subscribes": ["C"],
            "last_materialized": {},
        }
        partial = {"A": {"node": "A", "hash": "ha", "gen": 1, "seq": 1, "rows": 1}}
        assert stale_inputs(graph, consumer, partial, fan_in_require_all=True) == []
        ready = {
            "A": {"node": "A", "hash": "ha", "gen": 1, "seq": 1, "rows": 1},
            "B": {"node": "B", "hash": "hb", "gen": 1, "seq": 2, "rows": 1},
        }
        assert stale_inputs(graph, consumer, ready, fan_in_require_all=True) == ["C"]

    def test_runtime_generation_floor_reloads_on_rebuild(self) -> None:
        """Runtime generation-floor changes made after startup are reflected."""
        original_cfg = LINEAGE.read_text(encoding="utf-8")
        original_manifest = MANIFEST.read_text(encoding="utf-8")
        original_report = REPORT.read_text(encoding="utf-8") if REPORT.exists() else None
        try:
            manifest = json.loads(original_manifest)
            manifest["consumers"] = [
                row for row in manifest["consumers"] if row["id"] == "consumer_harbor"
            ]
            MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            LINEAGE.write_text(
                original_cfg.replace("generation_floor = 1", "generation_floor = 2"),
                encoding="utf-8",
            )
            _rebuild()
            assert set(_doc()["consumers"]) == {"consumer_harbor"}
            assert _doc()["consumers"]["consumer_harbor"] == {
                "stale_inputs": [],
                "rebuild_required": False,
                "frontier_digest_hex": EMPTY_DIGEST,
            }
        finally:
            MANIFEST.write_text(original_manifest, encoding="utf-8")
            LINEAGE.write_text(original_cfg, encoding="utf-8")
            if original_report is None:
                REPORT.unlink(missing_ok=True)
            else:
                REPORT.write_text(original_report, encoding="utf-8")

    def test_zero_manifest_floor_shadows_runtime_floor(self) -> None:
        """A zero manifest generation floor keeps gen-1 rows in scope for stale detection."""
        original_manifest = MANIFEST.read_text(encoding="utf-8")
        original_cfg = LINEAGE.read_text(encoding="utf-8")
        original_report = REPORT.read_text(encoding="utf-8") if REPORT.exists() else None
        try:
            manifest = json.loads(original_manifest)
            manifest["consumers"] = [
                row for row in manifest["consumers"] if row["id"] == "consumer_harbor"
            ]
            for row in manifest["consumers"]:
                if row["id"] == "consumer_harbor":
                    row["generation_floor"] = 0
            MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            LINEAGE.write_text(
                original_cfg.replace("generation_floor = 1", "generation_floor = 2"),
                encoding="utf-8",
            )

            _rebuild()
            block = _doc()["consumers"]["consumer_harbor"]
            assert block["stale_inputs"] == ["B"]
            assert block["rebuild_required"] is True
            assert block["frontier_digest_hex"] == BASELINE["consumer_harbor"]["frontier_digest_hex"]
        finally:
            MANIFEST.write_text(original_manifest, encoding="utf-8")
            LINEAGE.write_text(original_cfg, encoding="utf-8")
            if original_report is None:
                REPORT.unlink(missing_ok=True)
            else:
                REPORT.write_text(original_report, encoding="utf-8")

    def test_runtime_fan_in_reload_on_rebuild(self) -> None:
        """Changing fan_in_require_all mid-session affects the next rebuild."""
        original_cfg = LINEAGE.read_text(encoding="utf-8")
        original_manifest = MANIFEST.read_text(encoding="utf-8")
        original_report = REPORT.read_text(encoding="utf-8") if REPORT.exists() else None
        try:
            manifest = json.loads(original_manifest)
            manifest["consumers"] = [
                row for row in manifest["consumers"] if row["id"] == "consumer_keystone"
            ]
            MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            _rebuild()
            baseline = _doc()["consumers"]["consumer_keystone"]
            patched = original_cfg.replace(
                "fan_in_require_all = true",
                "fan_in_require_all = false",
            )
            assert patched != original_cfg
            LINEAGE.write_text(patched, encoding="utf-8")
            _rebuild()
            block = _doc()["consumers"]["consumer_keystone"]
            assert block["stale_inputs"] == ["B", "D", "E"]
            assert block["rebuild_required"] is True
            assert block != baseline
        finally:
            MANIFEST.write_text(original_manifest, encoding="utf-8")
            LINEAGE.write_text(original_cfg, encoding="utf-8")
            if original_report is None:
                REPORT.unlink(missing_ok=True)
            else:
                REPORT.write_text(original_report, encoding="utf-8")

    def test_fan_in_reload_in_process(self) -> None:
        """fan_in_require_all reloads from disk across in-process build_report calls."""
        original_cfg = LINEAGE.read_text(encoding="utf-8")
        original_manifest = MANIFEST.read_text(encoding="utf-8")
        probe_script = r"""
import json
import sys
from pathlib import Path

from eng.run import build_report

registry = Path("/app/data/manifest.json")
runtime = Path("/app/cfg/lineage.toml")
payload = json.loads(sys.argv[1])
registry.write_text(json.dumps({"consumers": [payload["row"]]}, indent=2) + "\n", encoding="utf-8")
runtime.write_text(payload["cfg_true"], encoding="utf-8")
first = build_report()["consumers"][payload["row"]["id"]]
runtime.write_text(payload["cfg_false"], encoding="utf-8")
second = build_report()["consumers"][payload["row"]["id"]]
print(json.dumps({"first": first, "second": second}))
"""
        try:
            manifest = json.loads(original_manifest)
            row = next(item for item in manifest["consumers"] if item["id"] == "consumer_keystone")
            payload = {
                "row": row,
                "cfg_true": original_cfg,
                "cfg_false": original_cfg.replace(
                    "fan_in_require_all = true",
                    "fan_in_require_all = false",
                ),
            }
            proc = subprocess.run(
                ["python3", "-c", probe_script, json.dumps(payload)],
                cwd="/app",
                check=False,
                capture_output=True,
                text=True,
            )
            assert proc.returncode == 0, proc.stderr or proc.stdout
            got = json.loads(proc.stdout.strip())
            assert got["second"]["stale_inputs"] == ["B", "D", "E"]
            assert got["second"] != got["first"]
        finally:
            LINEAGE.write_text(original_cfg, encoding="utf-8")
            MANIFEST.write_text(original_manifest, encoding="utf-8")

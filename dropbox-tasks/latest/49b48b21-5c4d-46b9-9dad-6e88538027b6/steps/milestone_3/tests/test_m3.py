"""Milestone 3 — digest encoding, launcher parity, full rebuild matrix."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REPORT = Path("/app/output/lineage_frontier.json")
SCHEMA_STUB = Path("/app/stubs/schema_level.txt")
LINEAGE = Path("/app/cfg/lineage.toml")
MANIFEST = Path("/app/data/manifest.json")
GRAPH_DIR = Path("/app/data/graphs")
LEDGER_DIR = Path("/app/data/ledgers")
CONSUMER_DIR = Path("/app/data/consumers")

Event = tuple[str, str, int, int]

EMPTY_DIGEST = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _digest(events: list[Event]) -> str:
    lines = [
        json.dumps(
            {"node": node, "hash": value, "gen": gen, "seq": seq},
            separators=(",", ":"),
        )
        for node, value, gen, seq in events
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


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
        "frontier_digest_hex": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
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
        "frontier_digest_hex": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    },
    "consumer_cairn": {
        "stale_inputs": [],
        "rebuild_required": False,
        "frontier_digest_hex": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    },
    "consumer_keystone": {
        "stale_inputs": ["D", "E"],
        "rebuild_required": True,
        "frontier_digest_hex": "8d961422d0e3e70c12290510f5394d49ee94cfcdf6490687a63973a7eb5445d5",
    },
}


def _doc() -> dict[str, object]:
    return json.loads(REPORT.read_text(encoding="utf-8"))


def _rebuild(path: str = "/app/scripts/frontier.sh") -> None:
    REPORT.unlink(missing_ok=True)
    subprocess.run([path], check=True, cwd="/app")


class TestMilestone3:
    def test_fixture_matrix_rebuilds_to_baseline(self) -> None:
        """A fresh frontier rebuild matches the shipped fixture matrix."""
        _rebuild()
        doc = _doc()
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        assert doc["schema_mark"] == int(SCHEMA_STUB.read_text(encoding="utf-8").strip())
        assert set(doc["consumers"]) == {str(row["id"]) for row in manifest["consumers"]}
        assert doc["consumers"] == BASELINE

    def test_launcher_entrypoint_rebuilds_same_report(self) -> None:
        """The launcher path produces the same rebuilt report."""
        _rebuild("/app/launcher/lf_align")
        assert _doc()["consumers"] == BASELINE

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
        joined = _digest([("C", "hc", 1, 3), ("B", "hb", 1, 2)])
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

    def test_runtime_generation_floor_changes_rebuild_digest(self) -> None:
        """Raising runtime generation_floor mid-session changes rebuilt digests."""
        original_cfg = LINEAGE.read_text(encoding="utf-8")
        original_manifest = MANIFEST.read_text(encoding="utf-8")
        original_report = REPORT.read_text(encoding="utf-8") if REPORT.exists() else None
        try:
            manifest = json.loads(original_manifest)
            manifest["consumers"] = [
                row for row in manifest["consumers"] if row["id"] == "consumer_harbor"
            ]
            MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            _rebuild()
            baseline = _doc()["consumers"]["consumer_harbor"]
            assert baseline == BASELINE["consumer_harbor"]
            patched = original_cfg.replace("generation_floor = 1", "generation_floor = 2")
            assert patched != original_cfg
            LINEAGE.write_text(patched, encoding="utf-8")
            _rebuild()
            block = _doc()["consumers"]["consumer_harbor"]
            assert block["stale_inputs"] == []
            assert block["rebuild_required"] is False
            assert block != baseline
        finally:
            MANIFEST.write_text(original_manifest, encoding="utf-8")
            LINEAGE.write_text(original_cfg, encoding="utf-8")
            if original_report is None:
                REPORT.unlink(missing_ok=True)
            else:
                REPORT.write_text(original_report, encoding="utf-8")

    def test_manifest_rows_added_after_startup_are_included(self) -> None:
        """Manifest rows and referenced files added at runtime are audited."""
        original_manifest = MANIFEST.read_text(encoding="utf-8")
        original_report = REPORT.read_text(encoding="utf-8") if REPORT.exists() else None
        graph = GRAPH_DIR / "probe.json"
        ledger = LEDGER_DIR / "probe.jsonl"
        consumer = CONSUMER_DIR / "probe.json"
        try:
            graph.write_text(
                json.dumps(
                    {
                        "nodes": {
                            "A": {"depends": []},
                            "B": {"depends": ["A"]},
                            "C": {"depends": ["B"]},
                        },
                        "gates": {},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            ledger.write_text(
                '{"kind":"finish","node":"A","gen":1,"seq":1,"hash":"ha_probe","rows":1}\n'
                '{"kind":"finish","node":"B","gen":1,"seq":2,"hash":"hb_probe","rows":2}\n'
                '{"kind":"finish","node":"C","gen":1,"seq":3,"hash":"hc_probe","rows":3}\n',
                encoding="utf-8",
            )
            consumer.write_text(
                json.dumps(
                    {
                        "subscribes": ["B", "C"],
                        "last_materialized": {"B": "hb_old", "C": "hc_old"},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = json.loads(original_manifest)
            manifest["consumers"].append(
                {
                    "id": "consumer_probe",
                    "graph": "/app/data/graphs/probe.json",
                    "ledger": "/app/data/ledgers/probe.jsonl",
                    "consumer": "/app/data/consumers/probe.json",
                }
            )
            MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            _rebuild()
            assert _doc()["consumers"]["consumer_probe"] == {
                "stale_inputs": ["B", "C"],
                "rebuild_required": True,
                "frontier_digest_hex": _digest(
                    [("C", "hc_probe", 1, 3), ("B", "hb_probe", 1, 2)]
                ),
            }
        finally:
            MANIFEST.write_text(original_manifest, encoding="utf-8")
            graph.unlink(missing_ok=True)
            ledger.unlink(missing_ok=True)
            consumer.unlink(missing_ok=True)
            if original_report is None:
                REPORT.unlink(missing_ok=True)
            else:
                REPORT.write_text(original_report, encoding="utf-8")

    def test_manifest_reload_in_process(self) -> None:
        """Manifest rows added mid-session are included by in-process build_report."""
        original_manifest = MANIFEST.read_text(encoding="utf-8")
        probe_script = r"""
import json
import sys
from pathlib import Path

from eng.run import build_report

registry = Path("/app/data/manifest.json")
payload = json.loads(sys.argv[1])
registry.write_text(json.dumps(payload["first"], indent=2) + "\n", encoding="utf-8")
first = sorted(build_report()["consumers"])
registry.write_text(json.dumps(payload["second"], indent=2) + "\n", encoding="utf-8")
second = sorted(build_report()["consumers"])
print(json.dumps({"first": first, "second": second}))
"""
        try:
            manifest = json.loads(original_manifest)
            harbor = next(row for row in manifest["consumers"] if row["id"] == "consumer_harbor")
            probe_row = {
                "id": "consumer_probe_m3",
                "graph": harbor["graph"],
                "ledger": harbor["ledger"],
                "consumer": harbor["consumer"],
            }
            payload = {
                "first": {"consumers": [harbor]},
                "second": {"consumers": [harbor, probe_row]},
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
            assert got["first"] == ["consumer_harbor"]
            assert sorted(got["second"]) == sorted(["consumer_harbor", "consumer_probe_m3"])
        finally:
            MANIFEST.write_text(original_manifest, encoding="utf-8")

    def test_out_of_order_ledger_seq_prefers_latest_finish(self) -> None:
        """Rebuild keeps highest-seq finish hashes when ledger rows arrive out of order."""
        original_manifest = MANIFEST.read_text(encoding="utf-8")
        original_report = REPORT.read_text(encoding="utf-8") if REPORT.exists() else None
        graph = Path("/app/data/graphs/probe_seq.json")
        ledger = Path("/app/data/ledgers/probe_seq.jsonl")
        consumer = Path("/app/data/consumers/probe_seq.json")
        try:
            graph.write_text(
                json.dumps(
                    {
                        "nodes": {
                            "A": {"depends": []},
                            "B": {"depends": ["A"]},
                        },
                        "gates": {},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            ledger.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "kind": "finish",
                                "node": "B",
                                "gen": 1,
                                "seq": 2,
                                "hash": "hb_first",
                                "rows": 1,
                            }
                        ),
                        json.dumps(
                            {
                                "kind": "finish",
                                "node": "B",
                                "gen": 1,
                                "seq": 8,
                                "hash": "hb_later",
                                "rows": 2,
                            }
                        ),
                        json.dumps(
                            {
                                "kind": "finish",
                                "node": "A",
                                "gen": 1,
                                "seq": 1,
                                "hash": "ha",
                                "rows": 1,
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            consumer.write_text(
                json.dumps(
                    {
                        "subscribes": ["B"],
                        "last_materialized": {"B": "hb_first"},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = {
                "consumers": [
                    {
                        "id": "consumer_probe_seq",
                        "graph": str(graph),
                        "ledger": str(ledger),
                        "consumer": str(consumer),
                    }
                ]
            }
            MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            _rebuild()
            block = _doc()["consumers"]["consumer_probe_seq"]
            assert block["stale_inputs"] == ["B"]
            assert block["rebuild_required"] is True
            lines = [
                json.dumps(
                    {"node": "B", "hash": "hb_later", "gen": 1, "seq": 8},
                    separators=(",", ":"),
                )
            ]
            want = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
            assert block["frontier_digest_hex"] == want
        finally:
            MANIFEST.write_text(original_manifest, encoding="utf-8")
            for path in (graph, ledger, consumer):
                path.unlink(missing_ok=True)
            if original_report is not None:
                REPORT.write_text(original_report, encoding="utf-8")
            elif REPORT.exists():
                REPORT.unlink(missing_ok=True)


def test_rebuild_required_when_stale_missing_from_latest() -> None:
    """Stale ids without projected finish rows still pair rebuild_required true with empty digest."""
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


def test_feed_frontier_offline_differs_from_row_canon() -> None:
    """Offline feed_frontier join must disagree with the wired reverse-topo digest."""
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

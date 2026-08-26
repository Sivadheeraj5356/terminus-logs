import hashlib
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

ops_root = Path("/app/ops")
OUT_BASE = Path("/app/output")
BIN = Path("/usr/local/bin/rotlogctl")


def load_json(path: Path):
    return json.loads(path.read_text())


def load_trace():
    records = []
    for line in (ops_root / "runtime" / "cursor_trace.jsonl").read_text().splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return sorted(records, key=lambda item: item["seq"])


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def omit_hash(entry: dict) -> str:
    payload = "|".join([
        entry["partition_id"],
        entry.get("omission_reason", ""),
        entry["cursor_start"],
        entry["cursor_end"],
        entry["prev_cursor"],
    ])
    return hashlib.sha256(payload.encode()).hexdigest()


def lineage_hash(entries: list[dict]) -> str:
    payload = "".join(
        f"{entry['partition_id']}|{entry['prev_cursor']}|{entry['cursor_end']}\n"
        for entry in entries
        if entry["status"] == "export"
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def manifest_digest(entries: list[dict]) -> str:
    raw = json.dumps(entries, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def signature_hex(key_id: str, line_hash: str, man_hash: str) -> str:
    return hashlib.sha256(f"{key_id}\n{line_hash}\n{man_hash}".encode()).hexdigest()


def expected_entries() -> list[dict]:
    expected = []
    for event in load_trace():
        if "partition_id" not in event or event.get("action") not in {"export", "omit"}:
            continue
        entry = {
            "partition_id": event["partition_id"],
            "sequence": event["seq"],
            "path": f"logs/{event['partition_id']}.journal",
            "status": event["action"],
            "cursor_start": event["cursor_start"],
            "cursor_end": event["cursor_end"],
            "prev_cursor": event.get("prev_cursor", ""),
            "digest_hex": sha_file(ops_root / "logs" / f"{event['partition_id']}.journal"),
        }
        if entry["status"] == "omit":
            entry["omission_reason"] = event["omission_reason"]
            entry["omission_digest_hex"] = omit_hash(entry)
        expected.append(entry)
    return expected


def read_ledger_rows() -> list[dict]:
    conn = sqlite3.connect(ops_root / "state" / "export_ledger.sqlite")
    conn.row_factory = sqlite3.Row
    rows = [dict(row) for row in conn.execute(
        """
        select partition_id, sequence, status, cursor_start, cursor_end, prev_cursor,
               digest_hex, coalesce(omission_reason, '') as omission_reason,
               coalesce(omission_digest_hex, '') as omission_digest_hex,
               service_generation, batch_id, terminal
        from checkpoint order by sequence
        """
    )]
    conn.close()
    return rows


def normalize_ledger(rows: list[dict]) -> list[dict]:
    normalized = []
    for row in rows:
        item = {
            "partition_id": row["partition_id"],
            "sequence": row["sequence"],
            "path": f"logs/{row['partition_id']}.journal",
            "status": row["status"],
            "cursor_start": row["cursor_start"],
            "cursor_end": row["cursor_end"],
            "prev_cursor": row["prev_cursor"],
            "digest_hex": row["digest_hex"],
        }
        if row["status"] == "omit":
            item["omission_reason"] = row["omission_reason"]
            item["omission_digest_hex"] = row["omission_digest_hex"]
        normalized.append(item)
    return normalized


def run_cmd(command, *, check=True):
    return subprocess.run(command, text=True, capture_output=True, check=check)


def assert_partition_file_headers(entries: list[dict]):
    for entry in entries:
        first = (ops_root / entry["path"]).read_text().splitlines()[0]
        assert f"partition_id={entry['partition_id']}" in first
        assert f"cursor_start={entry['cursor_start']}" in first
        assert f"cursor_end={entry['cursor_end']}" in first


def test_operational_authorities_match_cursor_trace():
    """The persistent authorities must match the lifecycle trace, not merely a rendered report."""
    entries = expected_entries()
    exported = [entry["partition_id"] for entry in entries if entry["status"] == "export"]
    omitted = [entry["partition_id"] for entry in entries if entry["status"] == "omit"]
    assert exported == [event["partition_id"] for event in load_trace() if event.get("action") == "export"]
    assert omitted == [event["partition_id"] for event in load_trace() if event.get("action") == "omit"]
    assert_partition_file_headers(entries)

    manifest = load_json(ops_root / "manifests" / "bundle_manifest.json")
    assert manifest["schema_version"] == 2
    assert manifest["partition_entries"] == entries
    assert manifest["signer"]["lineage_hash_hex"] == lineage_hash(entries)

    state = load_json(ops_root / "state" / "export_state.json")
    assert state == {
        "schema_version": 2,
        "service_unit": "rotlog-export.service",
        "status": "complete",
        "succeeded_after_partition": "part-0004",
        "high_water_cursor": "s=32;b=boot-b",
        "last_complete_event_seq": 6,
        "resume_generation": "gen-42/reload-1",
        "lineage": exported,
        "omitted_partitions": omitted,
    }

    ledger_rows = read_ledger_rows()
    assert normalize_ledger(ledger_rows) == entries
    assert all(row["terminal"] == 1 for row in ledger_rows)
    assert {row["service_generation"] for row in ledger_rows} == {"gen-42/reload-1"}
    assert {row["batch_id"] for row in ledger_rows} == {"batch-20260714"}


def test_regenerated_export_bundle_is_provenance_complete_and_stable():
    """A regenerated bundle must be complete, provenance-bound, and replay-stable."""
    entries = expected_entries()
    out_a = OUT_BASE / "case-a"
    out_b = OUT_BASE / "case-b"
    shutil.rmtree(out_a, ignore_errors=True)
    shutil.rmtree(out_b, ignore_errors=True)

    run_cmd([str(BIN), "export", "--root", str(ops_root), "--out", str(out_a)])
    report_a = load_json(out_a / "compliance_report.json")
    signed_a = load_json(out_a / "bundle_manifest.signed.json")

    assert report_a["status"] == "complete"
    assert report_a["authority_mismatches"] == []
    assert report_a["exported_partitions"] == [entry["partition_id"] for entry in entries if entry["status"] == "export"]
    assert report_a["omitted_partitions"] == [entry["partition_id"] for entry in entries if entry["status"] == "omit"]
    assert report_a["partitions"] == entries
    terminal_cursor = next(event["cursor_end"] for event in reversed(load_trace()) if event.get("action") == "export")
    assert report_a["high_water_cursor"] == terminal_cursor
    assert report_a["lineage_hash_hex"] == lineage_hash(entries)

    expected_manifest_digest = manifest_digest(entries)
    expected_signature = signature_hex("local-offline-ed25519", lineage_hash(entries), expected_manifest_digest)
    assert report_a["manifest_digest_hex"] == expected_manifest_digest
    assert report_a["signature_hex"] == expected_signature
    assert signed_a["partition_entries"] == entries
    assert signed_a["signer"]["manifest_digest_hex"] == expected_manifest_digest
    assert signed_a["signer"]["signature_hex"] == expected_signature

    copied = sorted(path.name for path in (out_a / "partitions").glob("*.journal"))
    assert copied == ["part-0001.journal", "part-0002.journal", "part-0004.journal"]
    for name in copied:
        assert sha_file(out_a / "partitions" / name) == sha_file(ops_root / "logs" / name)

    shutil.rmtree(out_a)
    run_cmd([str(BIN), "export", "--root", str(ops_root), "--out", str(out_a)])
    run_cmd([str(BIN), "export", "--root", str(ops_root), "--out", str(out_b)])
    assert load_json(out_a / "compliance_report.json") == load_json(out_b / "compliance_report.json")
    assert load_json(out_a / "bundle_manifest.signed.json") == load_json(out_b / "bundle_manifest.signed.json")


def test_verify_commands_and_legacy_bundle_survive_replay():
    """The current verifier and the legacy v1 verifier must both succeed after reconciliation."""
    out = OUT_BASE / "verify-run"
    shutil.rmtree(out, ignore_errors=True)
    run_cmd([str(BIN), "verify", "--root", str(ops_root), "--out", str(out)])
    run_cmd([str(BIN), "legacy-verify", "--root", str(ops_root)])

    legacy = load_json(ops_root / "legacy" / "bundle_manifest_v1.json")
    assert legacy["schema_version"] == 1
    assert [entry["partition_id"] for entry in legacy["partition_entries"]] == ["part-0001", "part-0002"]
    previous_cursor = ""
    for entry in legacy["partition_entries"]:
        assert entry["status"] == "export"
        assert entry["prev_cursor"] == previous_cursor
        legacy_file = ops_root.joinpath(*entry["path"].split("/"))
        legacy_digest = hashlib.sha256(legacy_file.read_bytes()).hexdigest()
        assert entry["digest_hex"] == legacy_digest
        previous_cursor = entry["cursor_end"]


def test_state_deletion_or_output_only_completion_is_not_sufficient():
    """Deleting authorities or staging output alone must not satisfy regenerated verification."""
    entries = expected_entries()
    required_paths = [
        ops_root / "runtime" / "cursor_trace.jsonl",
        ops_root / "state" / "export_state.json",
        ops_root / "state" / "export_ledger.sqlite",
        ops_root / "manifests" / "bundle_manifest.json",
        ops_root / "legacy" / "bundle_manifest_v1.json",
    ]
    assert all(path.exists() and path.stat().st_size > 0 for path in required_paths)
    assert len(list((ops_root / "logs").glob("*.journal"))) == 4

    shutil.rmtree(OUT_BASE / "current", ignore_errors=True)
    result = run_cmd([str(BIN), "verify", "--root", str(ops_root), "--out", str(OUT_BASE / "current")], check=False)
    assert result.returncode == 0, result.stderr
    regenerated = load_json(OUT_BASE / "current" / "compliance_report.json")
    assert regenerated["partitions"] == entries
    assert regenerated["authority_mismatches"] == []

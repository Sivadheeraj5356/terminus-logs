"""
Integration tests for the cryptographic audit log validation pipeline.

Each scenario exercises emergent behavior across the cooperating modules
(chain tracking, Merkle recomputation, manifest signature, duplicate detection,
and timestamp ordering) rather than isolated single-rule checks.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

REF_DATA_DIR = os.environ.get("REF_DATA_DIR", "/app/data")
VERIFIER_PATH = os.environ.get("VERIFIER_PATH", "/app/src/audit_verify.py")


def sha256(data):
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def compute_merkle_root(leaves):
    if not leaves:
        return sha256("")
    current = list(leaves)
    while len(current) > 1:
        next_level = []
        for index in range(0, len(current), 2):
            left = current[index]
            right = current[index + 1] if index + 1 < len(current) else current[index]
            next_level.append(sha256(left + right))
        current = next_level
    return current[0]


def compute_record_hash(event_id, timestamp, payload, previous_hash):
    serialized = f"{event_id}:{timestamp}:{payload}:{previous_hash}"
    return sha256(serialized)


def recompute_segment_hashes(segment, initial_previous_hash=None):
    previous_hash = initial_previous_hash
    leaves = []
    for record in segment["records"]:
        if previous_hash is None:
            previous_hash = "0" * 64
        record["previous_hash"] = previous_hash
        record["record_hash"] = compute_record_hash(
            record["event_id"],
            record["timestamp"],
            record["payload"],
            previous_hash,
        )
        leaves.append(record["record_hash"])
        previous_hash = record["record_hash"]
    segment["merkle_root"] = compute_merkle_root(leaves)
    return previous_hash


def recompute_manifest_signature(data_dir, manifest):
    roots = []
    previous_hash = None
    for segment_file in manifest["segments"]:
        with open(os.path.join(data_dir, segment_file), "r", encoding="utf-8") as handle:
            segment = json.load(handle)
        previous_hash = recompute_segment_hashes(segment, initial_previous_hash=previous_hash)
        roots.append(segment["merkle_root"])
        with open(os.path.join(data_dir, segment_file), "w", encoding="utf-8") as handle:
            json.dump(segment, handle, indent=2)
    manifest["signature"] = sha256("".join(roots))
    return manifest


def run_verifier(data_dir, report_path):
    command = [sys.executable, VERIFIER_PATH, "--data-dir", str(data_dir), "--report", str(report_path)]
    return subprocess.run(command, capture_output=True, text=True)


def copy_ref_data(dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    for item in os.listdir(REF_DATA_DIR):
        source = os.path.join(REF_DATA_DIR, item)
        destination = os.path.join(dest_dir, item)
        if os.path.isdir(source):
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)


def load_report(report_path):
    with open(report_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def error_sort_key(error):
    return (
        error.get("segment_id") if error.get("segment_id") is not None else "\uffff",
        error.get("event_id") if error.get("event_id") is not None else "\uffff",
        error.get("type") if error.get("type") is not None else "\uffff",
    )


def test_pipeline_accepts_valid_multi_segment_chain(tmp_path):
    """A clean three-segment chain with cross-boundary continuity must pass every invariant."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    result = run_verifier(data_dir, report_file)
    assert result.returncode == 0, result.stderr
    report = load_report(report_file)

    assert report["valid"] is True
    assert report["summary"]["error_count"] == 0
    assert report["summary"]["segments_checked"] == 3
    assert report["summary"]["records_checked"] == 6


def test_cross_segment_duplicate_and_timestamp_interaction(tmp_path):
    """Duplicate IDs and timestamp regressions that only appear across segment boundaries must surface."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    with open(data_dir / "segment_1.json", "r", encoding="utf-8") as handle:
        segment_one = json.load(handle)
    segment_one["records"][0]["event_id"] = "evt_001"
    segment_one["records"][0]["timestamp"] = "2000-01-01T00:00:00Z"

    previous_hash = segment_one["records"][0]["previous_hash"]
    leaves = []
    for record in segment_one["records"]:
        serialized = f"{record['event_id']}:{record['timestamp']}:{record['payload']}:{previous_hash}"
        record["record_hash"] = sha256(serialized)
        leaves.append(record["record_hash"])
        previous_hash = record["record_hash"]
    segment_one["merkle_root"] = compute_merkle_root(leaves)

    with open(data_dir / "segment_1.json", "w", encoding="utf-8") as handle:
        json.dump(segment_one, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)
    error_types = {error["type"] for error in report["errors"]}

    assert report["valid"] is False
    assert "duplicate_event_id" in error_types
    assert "bad_timestamp_order" in error_types


def test_simultaneous_cryptographic_and_structural_failures(tmp_path):
    """Multiple independent invariant violations must accumulate in one report."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    with open(data_dir / "segment_0.json", "r", encoding="utf-8") as handle:
        segment_zero = json.load(handle)
    segment_zero["records"][1]["payload"] = "Tampered payload"
    with open(data_dir / "segment_0.json", "w", encoding="utf-8") as handle:
        json.dump(segment_zero, handle, indent=2)

    with open(data_dir / "manifest.json", "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    manifest["signature"] = "f" * 64
    with open(data_dir / "manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)
    error_types = {error["type"] for error in report["errors"]}

    assert report["valid"] is False
    assert len(report["errors"]) >= 2
    assert "tampered_record" in error_types
    assert "bad_manifest_signature" in error_types


def test_missing_segment_skips_manifest_signature_check(tmp_path):
    """Missing segments must be classified correctly and suppress manifest signature verification."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    os.remove(data_dir / "segment_2.json")

    with open(data_dir / "manifest.json", "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    manifest["signature"] = "a" * 64
    with open(data_dir / "manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)
    error_types = {error["type"] for error in report["errors"]}

    assert "missing_segment" in error_types
    assert "bad_manifest_signature" not in error_types


def test_chain_continuity_across_segment_boundary(tmp_path):
    """A broken hash chain at a segment boundary must be detected even when intra-segment hashes match."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    with open(data_dir / "segment_1.json", "r", encoding="utf-8") as handle:
        segment_one = json.load(handle)
    segment_one["records"][0]["previous_hash"] = "b" * 64
    with open(data_dir / "segment_1.json", "w", encoding="utf-8") as handle:
        json.dump(segment_one, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)

    assert any(error["type"] == "broken_chain" for error in report["errors"])


def test_merkle_root_recomputed_from_record_hashes(tmp_path):
    """Stored Merkle roots must be validated against independently recomputed trees."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    with open(data_dir / "segment_0.json", "r", encoding="utf-8") as handle:
        segment_zero = json.load(handle)
    segment_zero["merkle_root"] = "a" * 64
    with open(data_dir / "segment_0.json", "w", encoding="utf-8") as handle:
        json.dump(segment_zero, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)

    assert any(error["type"] == "bad_merkle_root" for error in report["errors"])


def test_manifest_signature_over_recomputed_roots(tmp_path):
    """Manifest signatures must be validated from recomputed segment Merkle roots."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    with open(data_dir / "manifest.json", "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    manifest["signature"] = "a" * 64
    with open(data_dir / "manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)

    assert any(error["type"] == "bad_manifest_signature" for error in report["errors"])


def test_manifest_signature_rejects_stored_root_binding(tmp_path):
    """Manifest signature checks must use recomputed roots, not stored merkle_root metadata."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    stored_roots = []
    with open(data_dir / "manifest.json", "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    for segment_file in manifest["segments"]:
        with open(data_dir / segment_file, "r", encoding="utf-8") as handle:
            segment = json.load(handle)
        if segment_file == "segment_0.json":
            segment["merkle_root"] = "b" * 64
        stored_roots.append(segment["merkle_root"])
        with open(data_dir / segment_file, "w", encoding="utf-8") as handle:
            json.dump(segment, handle, indent=2)

    manifest["signature"] = sha256("".join(stored_roots))
    with open(data_dir / "manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)
    error_types = {error["type"] for error in report["errors"]}

    assert "bad_merkle_root" in error_types
    assert "bad_manifest_signature" in error_types


def test_hash_format_rejects_non_lowercase_hex(tmp_path):
    """Uppercase or otherwise invalid hash encodings must be rejected before tamper checks."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    with open(data_dir / "segment_0.json", "r", encoding="utf-8") as handle:
        segment_zero = json.load(handle)
    record_hash = list(segment_zero["records"][0]["record_hash"])
    record_hash[-1] = "A"
    segment_zero["records"][0]["record_hash"] = "".join(record_hash)
    with open(data_dir / "segment_0.json", "w", encoding="utf-8") as handle:
        json.dump(segment_zero, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)

    assert any(error["type"] == "malformed_hash" for error in report["errors"])


def test_malformed_record_and_invalid_segment_json(tmp_path):
    """Structural parsing failures must be reported without mutating the data directory."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    with open(data_dir / "segment_0.json", "r", encoding="utf-8") as handle:
        segment_zero = json.load(handle)
    del segment_zero["records"][0]["payload"]
    with open(data_dir / "segment_0.json", "w", encoding="utf-8") as handle:
        json.dump(segment_zero, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)
    assert any(error["type"] == "malformed_record" for error in report["errors"])

    with open(data_dir / "segment_1.json", "w", encoding="utf-8") as handle:
        handle.write("{invalid json content")

    run_verifier(data_dir, report_file)
    report = load_report(report_file)
    assert any(error["type"] == "malformed_record" for error in report["errors"])


def test_empty_segment_merkle_root(tmp_path):
    """An empty segment must use the sha256 of an empty string as its Merkle root."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    with open(data_dir / "segment_0.json", "r", encoding="utf-8") as handle:
        segment_zero = json.load(handle)
    segment_zero["records"] = []
    segment_zero["merkle_root"] = sha256("")
    with open(data_dir / "segment_0.json", "w", encoding="utf-8") as handle:
        json.dump(segment_zero, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)

    assert not any(
        error["type"] == "bad_merkle_root" and error["segment_id"] == "segment_0"
        for error in report["errors"]
    )


def test_deterministic_error_ordering_under_composite_failures(tmp_path):
    """Error lists must remain stably sorted when several segments fail at once."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    os.remove(data_dir / "segment_2.json")
    with open(data_dir / "segment_0.json", "r", encoding="utf-8") as handle:
        segment_zero = json.load(handle)
    segment_zero["records"][1]["payload"] = "Tampered"
    with open(data_dir / "segment_0.json", "w", encoding="utf-8") as handle:
        json.dump(segment_zero, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)
    errors = report["errors"]

    assert len(errors) >= 2
    assert errors == sorted(errors, key=error_sort_key)


def test_report_schema_and_read_only_data(tmp_path):
    """Reports must follow the documented schema and the verifier must not modify source data."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    run_verifier(data_dir, report_file)
    report = load_report(report_file)

    assert isinstance(report["valid"], bool)
    assert isinstance(report["summary"]["segments_checked"], int)
    assert isinstance(report["summary"]["records_checked"], int)
    assert isinstance(report["summary"]["error_count"], int)
    assert isinstance(report["errors"], list)
    for error in report["errors"]:
        assert "type" in error
        assert "segment_id" in error
        assert "event_id" in error
        assert "details" in error

    files_before = {}
    for item in os.listdir(REF_DATA_DIR):
        path = os.path.join(REF_DATA_DIR, item)
        if os.path.isfile(path):
            with open(path, "rb") as handle:
                files_before[item] = handle.read()

    temp_report = os.path.join(os.path.dirname(REF_DATA_DIR), "temp_report.json")
    run_verifier(REF_DATA_DIR, temp_report)
    if os.path.exists(temp_report):
        os.remove(temp_report)

    for item, content_before in files_before.items():
        path = os.path.join(REF_DATA_DIR, item)
        with open(path, "rb") as handle:
            assert handle.read() == content_before


def test_equal_timestamps_allowed_in_sequence(tmp_path):
    """Consecutive records may share the same timestamp; ordering is non-decreasing."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    with open(data_dir / "segment_0.json", "r", encoding="utf-8") as handle:
        segment_zero = json.load(handle)
    shared_timestamp = segment_zero["records"][0]["timestamp"]
    segment_zero["records"][1]["timestamp"] = shared_timestamp
    with open(data_dir / "segment_0.json", "w", encoding="utf-8") as handle:
        json.dump(segment_zero, handle, indent=2)

    with open(data_dir / "manifest.json", "r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    recompute_manifest_signature(data_dir, manifest)
    with open(data_dir / "manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)

    assert report["valid"] is True
    assert not any(error["type"] == "bad_timestamp_order" for error in report["errors"])


def test_numeric_epoch_timestamps_across_segments(tmp_path):
    """Numeric epoch timestamps must chain and compare correctly across segment boundaries."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    epoch_values = [1718870400, 1718870460, 1718870520, 1718870580, 1718870640, 1718870700]
    record_index = 0
    for segment_name in ("segment_0.json", "segment_1.json", "segment_2.json"):
        with open(data_dir / segment_name, "r", encoding="utf-8") as handle:
            segment = json.load(handle)
        for record in segment["records"]:
            record["timestamp"] = epoch_values[record_index]
            record_index += 1
        with open(data_dir / segment_name, "w", encoding="utf-8") as handle:
            json.dump(segment, handle, indent=2)

    with open(data_dir / "manifest.json", "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    recompute_manifest_signature(data_dir, manifest)
    with open(data_dir / "manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)

    assert report["valid"] is True


def test_non_adjacent_duplicate_event_id(tmp_path):
    """Duplicate event IDs separated by intervening segments must still be detected."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    with open(data_dir / "segment_2.json", "r", encoding="utf-8") as handle:
        segment_two = json.load(handle)
    segment_two["records"][0]["event_id"] = "evt_002"
    with open(data_dir / "segment_2.json", "w", encoding="utf-8") as handle:
        json.dump(segment_two, handle, indent=2)

    with open(data_dir / "manifest.json", "r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    recompute_manifest_signature(data_dir, manifest)
    with open(data_dir / "manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)

    assert any(error["type"] == "duplicate_event_id" for error in report["errors"])


def test_segment_id_mismatch(tmp_path):
    """Embedded segment_id must match the segment filename stem."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    with open(data_dir / "segment_0.json", "r", encoding="utf-8") as handle:
        segment_zero = json.load(handle)
    segment_zero["segment_id"] = "segment_wrong"
    with open(data_dir / "segment_0.json", "w", encoding="utf-8") as handle:
        json.dump(segment_zero, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)

    assert any(error["type"] == "segment_id_mismatch" for error in report["errors"])


def test_mixed_iso_and_epoch_equal_instants_allowed(tmp_path):
    """Equal instants expressed as epoch and ISO-8601 must not violate timestamp ordering."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    shared_epoch = 1718870400
    shared_iso = datetime.fromtimestamp(shared_epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(data_dir / "segment_0.json", "r", encoding="utf-8") as handle:
        segment_zero = json.load(handle)
    segment_zero["records"][0]["timestamp"] = shared_epoch
    segment_zero["records"][1]["timestamp"] = shared_iso
    with open(data_dir / "segment_0.json", "w", encoding="utf-8") as handle:
        json.dump(segment_zero, handle, indent=2)

    with open(data_dir / "manifest.json", "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    recompute_manifest_signature(data_dir, manifest)
    with open(data_dir / "manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)

    assert report["valid"] is True
    assert not any(error["type"] == "bad_timestamp_order" for error in report["errors"])


def test_offset_aware_iso_equal_instants_allowed(tmp_path):
    """Equal UTC instants with different ISO offsets must compare as non-decreasing."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    with open(data_dir / "segment_0.json", "r", encoding="utf-8") as handle:
        segment_zero = json.load(handle)
    segment_zero["records"][0]["timestamp"] = "2024-06-20T12:00:00+02:00"
    segment_zero["records"][1]["timestamp"] = "2024-06-20T10:00:00Z"
    with open(data_dir / "segment_0.json", "w", encoding="utf-8") as handle:
        json.dump(segment_zero, handle, indent=2)

    with open(data_dir / "manifest.json", "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    recompute_manifest_signature(data_dir, manifest)
    with open(data_dir / "manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)

    assert report["valid"] is True
    assert not any(error["type"] == "bad_timestamp_order" for error in report["errors"])


def test_manifest_signature_sensitive_to_segment_order(tmp_path):
    """Manifest signatures bind recomputed roots in manifest order, not lexicographic order."""
    data_dir = tmp_path / "data"
    copy_ref_data(data_dir)
    report_file = tmp_path / "report.json"

    with open(data_dir / "manifest.json", "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    manifest["segments"] = list(reversed(manifest["segments"]))
    with open(data_dir / "manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    run_verifier(data_dir, report_file)
    report = load_report(report_file)

    assert report["valid"] is False
    assert any(error["type"] == "broken_chain" for error in report["errors"])


#!/bin/bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/app}"

cat << 'EOF' > "$APP_ROOT/src/hash_utils.py"
"""Hash format checks and record-hash recomputation."""

import hashlib


def is_valid_sha256(value):
    if not isinstance(value, str):
        return False
    if len(value) != 64:
        return False
    return all(c in "0123456789abcdef" for c in value)


def compute_record_hash(event_id, timestamp, payload, previous_hash):
    serialized = f"{event_id}:{timestamp}:{payload}:{previous_hash}"
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def sha256_hex(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()
EOF

cat << 'EOF' > $APP_ROOT/src/timestamp_codec.py
"""Timestamp normalization and ordering comparisons."""

from datetime import datetime, timezone


def to_epoch_seconds(timestamp):
    if isinstance(timestamp, (int, float)):
        return float(timestamp)
    if isinstance(timestamp, str):
        text = timestamp.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)
        return parsed.timestamp()
    raise ValueError(f"Unsupported timestamp type: {type(timestamp)}")


def timestamps_in_order(previous, current):
    if previous is None:
        return True
    try:
        return to_epoch_seconds(current) >= to_epoch_seconds(previous)
    except ValueError:
        return str(current) >= str(previous)
EOF

cat << 'EOF' > $APP_ROOT/src/chain_tracker.py
"""Cross-segment chain, timestamp, and event-id state."""

from timestamp_codec import timestamps_in_order


class ChainTracker:
    def __init__(self):
        self.previous_hash = "0" * 64
        self.last_timestamp = None
        self.seen_event_ids = set()
        self.global_record_index = 0

    def begin_segment(self):
        return

    def is_genesis_record(self):
        return self.global_record_index == 0

    def check_chain(self, previous_hash):
        return previous_hash == self.previous_hash

    def advance_chain(self, record_hash):
        self.previous_hash = record_hash
        self.global_record_index += 1

    def check_timestamp(self, timestamp):
        return timestamps_in_order(self.last_timestamp, timestamp)

    def advance_timestamp(self, timestamp):
        self.last_timestamp = timestamp

    def is_duplicate(self, event_id):
        return event_id in self.seen_event_ids

    def register_event_id(self, event_id):
        self.seen_event_ids.add(event_id)
EOF

cat << 'EOF' > $APP_ROOT/src/merkle_builder.py
"""Merkle tree construction from record-hash leaves."""

from hash_utils import sha256_hex


def build_merkle_root(leaves):
    if not leaves:
        return sha256_hex("")
    current = list(leaves)
    while len(current) > 1:
        next_level = []
        for index in range(0, len(current), 2):
            left = current[index]
            right = current[index + 1] if index + 1 < len(current) else current[index]
            next_level.append(sha256_hex(left + right))
        current = next_level
    return current[0]
EOF

cat << 'EOF' > $APP_ROOT/src/segment_identity.py
"""Segment file stem versus embedded segment_id checks."""


def segment_identity_ok(segment_file, segment_data):
    expected = segment_file.replace(".json", "")
    actual = segment_data.get("segment_id")
    return actual == expected
EOF

cat << 'EOF' > $APP_ROOT/src/manifest_loader.py
"""Manifest and segment file loading."""

import json
import os


def load_manifest(data_dir):
    manifest_path = os.path.join(data_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        return None, {
            "type": "malformed_record",
            "segment_id": None,
            "event_id": None,
            "details": "manifest.json not found",
        }
    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except Exception as exc:
        return None, {
            "type": "malformed_record",
            "segment_id": None,
            "event_id": None,
            "details": f"manifest.json invalid JSON: {exc}",
        }


def load_segment(data_dir, segment_file, segment_id):
    segment_path = os.path.join(data_dir, segment_file)
    if not os.path.exists(segment_path):
        return None, {
            "type": "missing_segment",
            "segment_id": segment_id,
            "event_id": None,
            "details": f"Segment file {segment_file} is missing",
        }
    try:
        with open(segment_path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except Exception as exc:
        return None, {
            "type": "malformed_record",
            "segment_id": segment_id,
            "event_id": None,
            "details": f"Invalid segment JSON: {exc}",
        }
EOF

cat << 'EOF' > $APP_ROOT/src/manifest_validator.py
"""Manifest signature verification."""

from hash_utils import is_valid_sha256, sha256_hex


def verify_manifest_signature(recomputed_roots, stored_signature):
    if not is_valid_sha256(stored_signature):
        return False, "malformed_hash"
    concatenated = "".join(recomputed_roots)
    expected = sha256_hex(concatenated)
    if expected == stored_signature:
        return True, None
    return False, "bad_manifest_signature"
EOF

cat << 'EOF' > $APP_ROOT/src/record_validator.py
"""Record-level schema and cryptographic checks."""

from hash_utils import compute_record_hash, is_valid_sha256


REQUIRED_FIELDS = ["event_id", "timestamp", "payload", "previous_hash", "record_hash"]


def validate_record(record, segment_id, chain):
    errors = []
    if not isinstance(record, dict):
        return errors, None

    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        errors.append({
            "type": "malformed_record",
            "segment_id": segment_id,
            "event_id": record.get("event_id") if isinstance(record.get("event_id"), str) else None,
            "details": f"Missing fields: {', '.join(missing)}" if len(missing) > 1 else "Missing required fields",
        })
        return errors, None

    event_id = record["event_id"]
    timestamp = record["timestamp"]
    payload = record["payload"]
    previous_hash = record["previous_hash"]
    record_hash = record["record_hash"]

    if not isinstance(event_id, str) or not isinstance(payload, str):
        errors.append({
            "type": "malformed_record",
            "segment_id": segment_id,
            "event_id": event_id if isinstance(event_id, str) else None,
            "details": "Incorrect types for record fields",
        })
        return errors, None

    if not is_valid_sha256(record_hash):
        errors.append({
            "type": "malformed_hash",
            "segment_id": segment_id,
            "event_id": event_id,
            "details": f"Record hash format invalid: {record_hash}",
        })
    if not is_valid_sha256(previous_hash):
        errors.append({
            "type": "malformed_hash",
            "segment_id": segment_id,
            "event_id": event_id,
            "details": f"Previous hash format invalid: {previous_hash}",
        })

    if chain.is_duplicate(event_id):
        errors.append({
            "type": "duplicate_event_id",
            "segment_id": segment_id,
            "event_id": event_id,
            "details": f"Duplicate event ID across segments: {event_id}",
        })
    chain.register_event_id(event_id)

    computed = compute_record_hash(event_id, timestamp, payload, previous_hash)
    if computed != record_hash:
        errors.append({
            "type": "tampered_record",
            "segment_id": segment_id,
            "event_id": event_id,
            "details": f"Record hash mismatch: computed {computed} != {record_hash}",
        })

    if not chain.check_chain(previous_hash):
        errors.append({
            "type": "broken_chain",
            "segment_id": segment_id,
            "event_id": event_id,
            "details": f"Chain broken: previous_hash {previous_hash} does not match preceding hash {chain.previous_hash}",
        })
    chain.advance_chain(record_hash)

    if not chain.check_timestamp(timestamp):
        errors.append({
            "type": "bad_timestamp_order",
            "segment_id": segment_id,
            "event_id": event_id,
            "details": f"Timestamp ordering violation: {timestamp} is earlier than preceding {chain.last_timestamp}",
        })
    chain.advance_timestamp(timestamp)

    return errors, record_hash
EOF

cat << 'EOF' > $APP_ROOT/src/segment_processor.py
"""Process one manifest segment and accumulate validation findings."""

from hash_utils import is_valid_sha256
from merkle_builder import build_merkle_root
from record_validator import validate_record
from segment_identity import segment_identity_ok


def process_segment(segment_data, segment_id, segment_file, chain):
    findings = {
        "errors": [],
        "records_checked": 0,
        "record_hashes": [],
        "recomputed_root": None,
    }

    if not isinstance(segment_data, dict):
        findings["errors"].append({
            "type": "malformed_record",
            "segment_id": segment_id,
            "event_id": None,
            "details": "Segment data must be a JSON object",
        })
        return findings

    if not segment_identity_ok(segment_file, segment_data):
        findings["errors"].append({
            "type": "segment_id_mismatch",
            "segment_id": segment_id,
            "event_id": None,
            "details": f"segment_id {segment_data.get('segment_id')!r} does not match file stem {segment_id!r}",
        })

    records = segment_data.get("records")
    stored_root = segment_data.get("merkle_root")

    if records is None or not isinstance(records, list):
        findings["errors"].append({
            "type": "malformed_record",
            "segment_id": segment_id,
            "event_id": None,
            "details": "Segment missing records list",
        })
        return findings

    if stored_root is None or not is_valid_sha256(stored_root):
        findings["errors"].append({
            "type": "malformed_hash",
            "segment_id": segment_id,
            "event_id": None,
            "details": f"Segment Merkle root format invalid: {stored_root}",
        })

    chain.begin_segment()

    for record in records:
        findings["records_checked"] += 1
        record_errors, record_hash = validate_record(record, segment_id, chain)
        findings["errors"].extend(record_errors)
        if record_hash is not None:
            findings["record_hashes"].append(record_hash)

    computed_root = build_merkle_root(findings["record_hashes"])
    findings["recomputed_root"] = computed_root
    if computed_root != stored_root:
        findings["errors"].append({
            "type": "bad_merkle_root",
            "segment_id": segment_id,
            "event_id": None,
            "details": f"Merkle root mismatch: computed {computed_root} != expected {stored_root}",
        })

    return findings
EOF

cat << 'EOF' > $APP_ROOT/src/report_writer.py
"""Validation report assembly and deterministic sorting."""


def sort_errors(errors):
    def sort_key(error):
        segment_id = error.get("segment_id")
        event_id = error.get("event_id")
        error_type = error.get("type")
        return (
            (segment_id is None, segment_id or ""),
            (event_id is None, event_id or ""),
            (error_type is None, error_type or ""),
        )

    errors.sort(key=sort_key)
    return errors


def build_report(errors, segments_checked, records_checked):
    errors = sort_errors(errors)
    return {
        "valid": len(errors) == 0,
        "summary": {
            "segments_checked": segments_checked,
            "records_checked": records_checked,
            "error_count": len(errors),
        },
        "errors": errors,
    }


def write_report(report, report_path):
    import json
    import os

    directory = os.path.dirname(report_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
EOF

cat << 'EOF' > $APP_ROOT/src/validation_pipeline.py
"""End-to-end audit log validation orchestration."""

from chain_tracker import ChainTracker
from hash_utils import is_valid_sha256
from manifest_loader import load_manifest, load_segment
from manifest_validator import verify_manifest_signature
from report_writer import build_report
from segment_processor import process_segment


def run_validation(data_dir):
    manifest, manifest_error = load_manifest(data_dir)
    if manifest_error is not None:
        return build_report([manifest_error], 0, 0)

    segments = manifest.get("segments", [])
    signature = manifest.get("signature")
    chain = ChainTracker()
    errors = []
    segments_checked = 0
    records_checked = 0
    recomputed_roots = []
    missing_segments = False

    for segment_file in segments:
        segment_id = segment_file.replace(".json", "")
        segment_data, segment_error = load_segment(data_dir, segment_file, segment_id)
        if segment_error is not None:
            errors.append(segment_error)
            if segment_error["type"] == "missing_segment":
                missing_segments = True
            continue

        segments_checked += 1
        findings = process_segment(segment_data, segment_id, segment_file, chain)
        errors.extend(findings["errors"])
        records_checked += findings["records_checked"]
        if findings["recomputed_root"] is not None:
            recomputed_roots.append(findings["recomputed_root"])

    if not missing_segments and len(recomputed_roots) == len(segments):
        if signature is None or not is_valid_sha256(signature):
            errors.append({
                "type": "malformed_hash",
                "segment_id": None,
                "event_id": None,
                "details": f"Manifest signature format invalid: {signature}",
            })
        else:
            ok, failure = verify_manifest_signature(recomputed_roots, signature)
            if not ok:
                if failure == "malformed_hash":
                    errors.append({
                        "type": "malformed_hash",
                        "segment_id": None,
                        "event_id": None,
                        "details": f"Manifest signature format invalid: {signature}",
                    })
                else:
                    errors.append({
                        "type": "bad_manifest_signature",
                        "segment_id": None,
                        "event_id": None,
                        "details": "Manifest signature mismatch",
                    })

    return build_report(errors, segments_checked, records_checked)
EOF

cat << 'EOF' > $APP_ROOT/src/audit_verify.py
#!/usr/bin/env python3
"""Cryptographic audit log verifier CLI."""

import argparse

from report_writer import write_report
from validation_pipeline import run_validation


def parse_args():
    parser = argparse.ArgumentParser(description="Cryptographic Audit Segment Verifier")
    parser.add_argument("--data-dir", required=True, help="Path to data directory")
    parser.add_argument("--report", required=True, help="Path to write the report JSON")
    return parser.parse_args()


def main():
    args = parse_args()
    report = run_validation(args.data_dir)
    write_report(report, args.report)


if __name__ == "__main__":
    main()
EOF

chmod +x $APP_ROOT/src/audit_verify.py

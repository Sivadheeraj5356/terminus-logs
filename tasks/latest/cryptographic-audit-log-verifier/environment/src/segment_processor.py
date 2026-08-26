"""Process one manifest segment and accumulate validation findings."""

from hash_utils import is_valid_sha256
from merkle_builder import build_merkle_root
from record_validator import validate_record


def process_segment(segment_data, segment_id, chain):
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

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

    if chain.is_genesis_record():
        if previous_hash != "0" * 64:
            errors.append({
                "type": "broken_chain",
                "segment_id": segment_id,
                "event_id": event_id,
                "details": f"Chain broken: previous_hash {previous_hash} does not match genesis hash",
            })
    elif not chain.check_chain(previous_hash):
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

"""Private self-checks for the Python reference."""

from __future__ import annotations

import hashlib

from .binary import encode_lower_hex, sha256
from .p256 import N, sign_ecdsa_p256_sha256, verify_ecdsa_p256_sha256
from .pcr import replay_events, selected_pcr_digest, zero_pcrs
from .protected_inputs import capture_from_dir, mutation_detected
from .quote import (
    MAGIC,
    encode_quote,
    encode_signature,
    parse_quote,
    parse_signature,
    pcr_select_bytes,
)


def run_all() -> None:
    # Quote parse roundtrip
    qn = b"\x00\x0b" + b"\x11" * 32
    extra = b"\x22" * 32
    digest = b"\x33" * 32
    raw = encode_quote(
        qualified_signer=qn,
        extra_data=extra,
        clock=99,
        reset_count=1,
        restart_count=2,
        safe=1,
        firmware_version=7,
        selected_pcrs=[0, 4, 7],
        pcr_digest=digest,
    )
    pq = parse_quote(raw)
    assert pq.magic == MAGIC
    assert pq.selected_pcrs == [0, 4, 7]
    assert pq.extra_data == extra

    # Signature parse
    r = b"\x01" + b"\x00" * 31
    s = b"\x02" + b"\x00" * 31
    ps = parse_signature(encode_signature(r, s))
    assert ps.r == r and ps.s == s

    # Trailing bytes rejected
    try:
        parse_quote(raw + b"\x00")
        raise AssertionError("expected trailing reject")
    except ValueError:
        pass

    # PCR zero + extend
    pcrs = zero_pcrs()
    assert pcrs[0] == bytes(32)
    events = [
        {
            "event_seq": 2,
            "pcr_index": 0,
            "event_type": "T",
            "component": "C",
            "version": "1",
            "measurement_digest": encode_lower_hex(b"\xaa" * 32),
        },
        {
            "event_seq": 1,
            "pcr_index": 0,
            "event_type": "T",
            "component": "C",
            "version": "1",
            "measurement_digest": encode_lower_hex(b"\xbb" * 32),
        },
    ]
    # Physical order vs seq order
    a = replay_events(events)
    b = replay_events(list(reversed(events)))
    assert a[0] == b[0]
    # Semantic order change
    events2 = [
        {**events[0], "event_seq": 1, "measurement_digest": encode_lower_hex(b"\xaa" * 32)},
        {**events[1], "event_seq": 2, "measurement_digest": encode_lower_hex(b"\xbb" * 32)},
    ]
    c = replay_events(events2)
    assert c[0] != a[0]

    # Multi-PCR selected digest ascending
    p = zero_pcrs()
    p[0] = b"\x01" * 32
    p[4] = b"\x02" * 32
    p[7] = b"\x03" * 32
    d = selected_pcr_digest(p, [7, 0, 4])
    assert d == sha256(p[0] + p[4] + p[7])

    # PCR bitset
    assert pcr_select_bytes([0, 4, 7])[0] == ((1 << 0) | (1 << 4) | (1 << 7))

    # ECDSA roundtrip with cryptography-derived key
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    d_int = int.from_bytes(hashlib.sha256(b"self-check-key").digest(), "big") % N
    if d_int == 0:
        d_int = 1
    sk = ec.derive_private_key(d_int, ec.SECP256R1())
    pub = sk.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    rr, ss = sign_ecdsa_p256_sha256(sk, raw)
    assert verify_ecdsa_p256_sha256(pub, raw, rr, ss)
    assert not verify_ecdsa_p256_sha256(pub, raw + b"x", rr, ss)

    # Scalar range
    assert N > 0

    print("self_check: basic OK")


# Closed conflict vocabulary and request-level reason → projection rules.
# Mirrors the public report_schema.md contract and tests/reference/report.py.
CONFLICT_TYPES = frozenset(
    {"identity", "nonce", "pcr", "counter", "firmware", "measurement", "event_order"}
)

NO_CONFLICT_REASONS = frozenset({"quote_malformed", "signature_malformed"})

CONFLICT_REASON_TYPES: dict[str, str] = {
    "device_unknown": "identity",
    "attestation_key_unknown": "identity",
    "reference_policy_unknown": "identity",
    "event_log_unknown": "identity",
    "attestation_key_device_mismatch": "identity",
    "device_class_not_allowed": "identity",
    "quote_magic_invalid": "identity",
    "quote_type_invalid": "identity",
    "qualified_signer_mismatch": "identity",
    "attestation_key_not_valid": "identity",
    "quote_signature_invalid": "identity",
    "nonce_unknown": "nonce",
    "nonce_device_mismatch": "nonce",
    "nonce_not_yet_valid": "nonce",
    "nonce_expired": "nonce",
    "nonce_consumed": "nonce",
    "nonce_mismatch": "nonce",
    "quote_pcr_selection_invalid": "pcr",
    "event_log_device_mismatch": "pcr",
    "pcr_digest_mismatch": "pcr",
    "clock_unsafe": "counter",
    "counter_rollback": "counter",
    "firmware_not_allowed": "firmware",
    "reference_measurement_mismatch": "measurement",
    "event_order_violation": "event_order",
}


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted(set(values))


def run_conflict_contract_checks() -> None:
    from .report import _conflict

    # related_values: dedupe + ascending lexical sort
    row = _conflict("r", "counter", "dev", "counter_rollback", ["10", "2", "10", "1"])
    assert row["related_values"] == ["1", "10", "2"]

    # Measurement projects policy_id, never rule_id
    m = _conflict(
        "r",
        "measurement",
        "pol-x",
        "reference_measurement_mismatch",
        ["pol-x"],
    )
    assert m["subject"] == "pol-x"
    assert m["related_values"] == ["pol-x"]
    assert m["subject"] != "rule-kernel"

    # Event-order uses edge subject and sorted endpoints
    e = _conflict(
        "r",
        "event_order",
        "rule-boot->rule-kernel",
        "event_order_violation",
        ["rule-kernel", "rule-boot"],
    )
    assert e["subject"] == "rule-boot->rule-kernel"
    assert " " not in e["subject"]
    assert e["related_values"] == ["rule-boot", "rule-kernel"]

    assert CONFLICT_TYPES == set(CONFLICT_REASON_TYPES.values())
    assert set(CONFLICT_REASON_TYPES) & NO_CONFLICT_REASONS == set()
    assert len(CONFLICT_REASON_TYPES) >= 24
    print("self_check: conflict projection helpers OK")


def run_conflict_report_consistency(report: dict) -> None:
    """Validate a full report against the public conflict contract."""
    seen_types: set[str] = set()
    reasons_with_conflict: set[str] = set()
    for req in report["request_rows"]:
        rid = req["request_id"]
        reason = req["reason_or_null"]
        matches = [c for c in report["conflict_rows"] if c["request_id"] == rid]
        if req["status"] == "accepted":
            assert matches == [], f"accepted {rid} must emit no conflict"
            continue
        assert reason is not None
        if reason in NO_CONFLICT_REASONS:
            assert matches == [], f"{reason} must emit no conflict for {rid}"
            continue
        assert reason in CONFLICT_REASON_TYPES, f"unknown reject reason {reason}"
        assert len(matches) == 1, f"{rid}/{reason} must emit exactly one conflict"
        c = matches[0]
        assert c["reason_code"] == reason
        assert c["conflict_type"] == CONFLICT_REASON_TYPES[reason]
        assert c["conflict_type"] in CONFLICT_TYPES
        assert c["related_values"] == _sorted_unique(list(c["related_values"]))
        seen_types.add(c["conflict_type"])
        reasons_with_conflict.add(reason)

        if reason == "reference_measurement_mismatch":
            assert c["related_values"] == [c["subject"]]
            # Rule-level evidence must not appear as conflict subject.
            for mr in report["reference_match_rows"]:
                if mr["request_id"] == rid and mr["status"] not in {
                    "matched",
                    "absent_allowed",
                }:
                    assert c["subject"] != mr["rule_id"]
                    assert mr["rule_id"] not in c["related_values"]

        if reason == "event_order_violation":
            assert "->" in c["subject"] and " " not in c["subject"]
            before, after = c["subject"].split("->", 1)
            assert c["related_values"] == _sorted_unique([before, after])

    # Report conflicts must stay inside the closed vocabulary.
    assert seen_types <= CONFLICT_TYPES, f"unexpected conflict types {seen_types}"
    # Firmware is covered by the projection helper below; canonical may omit it.
    fw = _conflict_firmware_sample()
    assert fw["conflict_type"] == "firmware"
    assert fw["related_values"] == [fw["subject"]]
    assert seen_types | {"firmware"} == CONFLICT_TYPES
    assert "quote_malformed" not in reasons_with_conflict
    assert "signature_malformed" not in reasons_with_conflict
    print("self_check: conflict report consistency OK")


def _conflict_firmware_sample() -> dict:
    from .report import _conflict

    return _conflict("r", "firmware", "42", "firmware_not_allowed", ["42"])


def run_fixture_checks(data_dir) -> None:
    """Author-side checks. Pass a *copy* of fixtures — this mutates devices.json."""

    from pathlib import Path

    from .report import verify_from_protected

    root = Path(data_dir)
    snap = capture_from_dir(root)
    report = verify_from_protected(snap)
    assert report["summary"]["request_count"] > 0
    run_conflict_contract_checks()
    run_conflict_report_consistency(report)
    # Mutating disk after capture must not change protected verify
    (root / "devices.json").write_text("[]\n", encoding="utf-8")
    assert mutation_detected(snap, root)
    report2 = verify_from_protected(snap)
    assert report2 == report
    print("self_check: fixture protected baseline OK")

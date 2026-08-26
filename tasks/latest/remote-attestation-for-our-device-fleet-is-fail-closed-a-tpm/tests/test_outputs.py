"""Exactly 23 verifier tests for the TPM2 quote / event-log PCR policy attestor."""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
from pathlib import Path

import pytest
from reference.binary import decode_lower_hex, encode_lower_hex, sha256
from reference.protected_inputs import (
    capture_from_dir,
    mutation_detected,
    verify_unchanged,
)
from reference.report import verify_from_protected

APP_DIR = Path(os.environ.get("TPM2_QUOTE_APP_DIR", "/app"))
DATA_DIR = Path(os.environ.get("TPM2_QUOTE_DATA_DIR", "/app/data"))
OUTPUT = Path(os.environ.get("TPM2_QUOTE_OUTPUT", "/app/output/report.json"))
BIN = Path(
    os.environ.get(
        "TPM2_QUOTE_ATTESTOR_BIN",
        "/app/target/release/tpm2-quote-attestor",
    )
)
FIXTURES = Path(
    os.environ.get(
        "TPM2_QUOTE_FIXTURES",
        str(Path(__file__).parent / "protected_fixtures"),
    )
)


def restore_canonical() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for p in FIXTURES.iterdir():
        if p.is_file():
            shutil.copy2(p, DATA_DIR / p.name)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()
    tmp = Path(str(OUTPUT) + ".tmp")
    if tmp.exists():
        tmp.unlink()


def run_bin(
    data_dir: Path | None = None, output: Path | None = None
) -> subprocess.CompletedProcess:
    dd = data_dir or DATA_DIR
    out = output or OUTPUT
    if out.exists():
        out.unlink()
    return subprocess.run(
        [str(BIN), "--data-dir", str(dd), "--output", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )


def load_report() -> dict:
    return json.loads(OUTPUT.read_text(encoding="utf-8"))


def row_by_id(rows: list[dict], rid: str, key: str = "request_id") -> dict:
    for r in rows:
        if r[key] == rid:
            return r
    raise AssertionError(f"missing row {rid}")


def conflict_for(report: dict, request_id: str, reason_code: str) -> dict:
    matches = [
        row
        for row in report["conflict_rows"]
        if row["request_id"] == request_id and row["reason_code"] == reason_code
    ]
    assert len(matches) == 1, (
        f"expected exactly one conflict for {request_id}/{reason_code}, got {len(matches)}"
    )
    return matches[0]


def _write_json(name: str, obj: object) -> None:
    (DATA_DIR / name).write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def _load_json(name: str) -> object:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def _read_ndjson() -> list[dict]:
    lines = (DATA_DIR / "quote_requests.ndjson").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _write_ndjson(rows: list[dict]) -> None:
    text = "\n".join(json.dumps(r, separators=(",", ":")) for r in rows)
    if text:
        text += "\n"
    (DATA_DIR / "quote_requests.ndjson").write_text(text, encoding="utf-8")


def _mutate_request(request_id: str, **fields: object) -> None:
    rows = _read_ndjson()
    found = False
    for row in rows:
        if row["request_id"] == request_id:
            row.update(fields)
            found = True
            break
    if not found:
        raise AssertionError(f"request {request_id} not found")
    _write_ndjson(rows)


def _match_row(rep: dict, request_id: str, rule_id: str) -> dict:
    for r in rep["reference_match_rows"]:
        if r["request_id"] == request_id and r["rule_id"] == rule_id:
            return r
    raise AssertionError(f"missing match row {request_id}/{rule_id}")


@pytest.fixture()
def canonical_run():
    restore_canonical()
    snap = capture_from_dir(DATA_DIR)
    proc = run_bin()
    verify_unchanged(snap, DATA_DIR)
    return snap, proc


def test_01_cli_input_schema_and_duplicate_detection():
    """CLI schema fatals, duplicates, stale cleanup, success path, protected immutability."""
    restore_canonical()
    # Missing required file
    (DATA_DIR / "devices.json").unlink()
    proc = run_bin()
    assert proc.returncode != 0 and proc.stderr.strip()
    assert not OUTPUT.exists()

    restore_canonical()
    devices = _load_json("devices.json")
    assert isinstance(devices, list)
    devices.append(dict(devices[0]))
    _write_json("devices.json", devices)
    proc = run_bin()
    assert proc.returncode != 0, "duplicate device_id must be whole-run fatal"
    assert proc.stderr.strip(), "duplicate device_id must be whole-run fatal"
    assert not OUTPUT.exists(), "duplicate device_id must be whole-run fatal"
    assert not Path(str(OUTPUT) + ".tmp").exists(), "duplicate device_id must be whole-run fatal"

    restore_canonical()
    rows = _read_ndjson()
    rows.append(dict(rows[0]))
    _write_ndjson(rows)
    proc = run_bin()
    assert proc.returncode != 0, "duplicate request_id must be whole-run fatal"
    assert proc.stderr.strip(), "duplicate request_id must be whole-run fatal"
    assert not OUTPUT.exists(), "duplicate request_id must be whole-run fatal"
    assert not Path(str(OUTPUT) + ".tmp").exists(), "duplicate request_id must be whole-run fatal"

    restore_canonical()
    nonces = _load_json("nonce_challenges.json")
    assert isinstance(nonces, list)
    nonces[0]["nonce_hex"] = nonces[0]["nonce_hex"].upper()
    _write_json("nonce_challenges.json", nonces)
    proc = run_bin()
    assert proc.returncode != 0 and proc.stderr.strip()

    restore_canonical()
    nonces = _load_json("nonce_challenges.json")
    assert isinstance(nonces, list)
    nonces[0]["issued_at"] = int(nonces[0]["expires_at"]) + 1
    _write_json("nonce_challenges.json", nonces)
    proc = run_bin()
    assert proc.returncode != 0 and proc.stderr.strip()

    restore_canonical()
    OUTPUT.write_text('{"stale":true}\n', encoding="utf-8")
    (DATA_DIR / "policy.json").write_text("{", encoding="utf-8")
    proc = run_bin()
    assert proc.returncode != 0 and proc.stderr.strip()
    assert not OUTPUT.exists()

    restore_canonical()
    assert BIN.is_file() and os.access(BIN, os.X_OK)
    snap = capture_from_dir(DATA_DIR)
    proc = run_bin()
    assert proc.returncode == 0
    verify_unchanged(snap, DATA_DIR)
    expected = verify_from_protected(snap)
    (DATA_DIR / "devices.json").write_text("[]\n", encoding="utf-8")
    assert mutation_detected(snap, DATA_DIR)
    assert verify_from_protected(snap) == expected
    restore_canonical()


def test_02_bounded_quote_and_signature_binary_parsing():
    """Truncation, trailing bytes, and length-field faults yield quote/signature malformed."""
    restore_canonical()
    rows = _read_ndjson()
    target = next(r for r in rows if r["request_id"] == "req-edge-ok")
    qh = target["quote_hex"]
    _mutate_request("req-edge-ok", quote_hex=qh[:-2])
    assert run_bin().returncode == 0
    assert row_by_id(load_report()["request_rows"], "req-edge-ok")["reason_or_null"] == (
        "quote_malformed"
    )

    restore_canonical()
    _mutate_request("req-edge-ok", quote_hex=qh + "00")
    assert run_bin().returncode == 0
    assert row_by_id(load_report()["request_rows"], "req-edge-ok")["reason_or_null"] == (
        "quote_malformed"
    )

    restore_canonical()
    # Wrong qualified_signer length field (bytes 6-7 of quote).
    qb = bytearray(decode_lower_hex(qh))
    qb[6:8] = (33).to_bytes(2, "big")
    _mutate_request("req-edge-ok", quote_hex=encode_lower_hex(bytes(qb)))
    assert run_bin().returncode == 0
    reason = row_by_id(load_report()["request_rows"], "req-edge-ok")["reason_or_null"]
    assert reason in ("quote_malformed", "signature_malformed")

    restore_canonical()
    sh = target["signature_hex"]
    sb = bytearray(decode_lower_hex(sh))
    # Wrong r_length (bytes 4-5 of signature).
    sb[4:6] = (31).to_bytes(2, "big")
    _mutate_request("req-edge-ok", signature_hex=encode_lower_hex(bytes(sb)))
    assert run_bin().returncode == 0
    reason = row_by_id(load_report()["request_rows"], "req-edge-ok")["reason_or_null"]
    assert reason in ("signature_malformed", "quote_malformed")
    restore_canonical()


def test_03_quote_magic_type_and_qualified_signer(canonical_run):
    """Fixture signer mismatch and mutated magic produce identity rejections."""
    _, proc = canonical_run
    assert proc.returncode == 0
    rep = load_report()
    assert (
        row_by_id(rep["request_rows"], "req-signer-mismatch")["reason_or_null"]
        == "qualified_signer_mismatch"
    )
    c = conflict_for(rep, "req-signer-mismatch", "qualified_signer_mismatch")
    assert c["conflict_type"] == "identity"
    assert c["subject"] == "ak-edge-1"
    keys = {k["attestation_key_id"]: k for k in _load_json("attestation_keys.json")}
    qr = row_by_id(rep["quote_rows"], "req-signer-mismatch")
    assert c["related_values"] == sorted(
        {qr["qualified_signer_hex"], keys["ak-edge-1"]["qualified_name_hex"]}
    )

    restore_canonical()
    rows = _read_ndjson()
    target = next(r for r in rows if r["request_id"] == "req-edge-ok")
    qb = bytearray(decode_lower_hex(target["quote_hex"]))
    qb[0] ^= 0x01
    _mutate_request("req-edge-ok", quote_hex=encode_lower_hex(bytes(qb)))
    assert run_bin().returncode == 0
    rep_m = load_report()
    assert row_by_id(rep_m["request_rows"], "req-edge-ok")["reason_or_null"] == (
        "quote_magic_invalid"
    )
    c = conflict_for(rep_m, "req-edge-ok", "quote_magic_invalid")
    assert c["conflict_type"] == "identity"
    assert len(c["subject"]) == 8 and c["subject"] == c["subject"].lower()
    assert c["related_values"] == [c["subject"]]
    restore_canonical()


def test_04_attestation_key_and_ecdsa_signature_verification(canonical_run):
    """Invalid signature skips nonce consume; expired and inclusive key windows."""
    _, proc = canonical_run
    assert proc.returncode == 0
    rep = load_report()
    bad = row_by_id(rep["request_rows"], "req-bad-sig")
    assert bad["reason_or_null"] == "quote_signature_invalid"
    assert bad["nonce_consumed_by_this_request"] is False
    assert row_by_id(rep["nonce_rows"], "nonce-edge-4", "nonce_id")["final_status"] == ("available")
    c = conflict_for(rep, "req-bad-sig", "quote_signature_invalid")
    assert c["conflict_type"] == "identity"
    assert c["subject"] == "ak-edge-1"
    assert c["related_values"] == ["ak-edge-1"]
    assert (
        row_by_id(rep["request_rows"], "req-key-expired")["reason_or_null"]
        == "attestation_key_not_valid"
    )
    c = conflict_for(rep, "req-key-expired", "attestation_key_not_valid")
    assert c["conflict_type"] == "identity"
    assert c["subject"] == "ak-edge-expired"
    keys = {k["attestation_key_id"]: k for k in _load_json("attestation_keys.json")}
    rr = row_by_id(rep["request_rows"], "req-key-expired")
    k = keys["ak-edge-expired"]
    assert c["related_values"] == sorted(
        {str(rr["received_at"]), str(k["valid_from"]), str(k["valid_until"])}
    )

    restore_canonical()
    keys = _load_json("attestation_keys.json")
    assert isinstance(keys, list)
    for key in keys:
        if key["attestation_key_id"] == "ak-edge-1":
            key["valid_from"] = 10000
            key["valid_until"] = 10000
    _write_json("attestation_keys.json", keys)
    # Keep only the boundary request so later clocks do not fail the window.
    _write_ndjson([r for r in _read_ndjson() if r["request_id"] == "req-edge-ok"])
    assert run_bin().returncode == 0
    assert row_by_id(load_report()["request_rows"], "req-edge-ok")["status"] == "accepted"
    restore_canonical()


def test_05_nonce_binding_and_freshness(canonical_run):
    """Expired, not-yet-valid, and quote/nonce binding mismatches."""
    _, proc = canonical_run
    assert proc.returncode == 0
    rep = load_report()
    assert row_by_id(rep["request_rows"], "req-expired-nonce")["reason_or_null"] == "nonce_expired"
    c = conflict_for(rep, "req-expired-nonce", "nonce_expired")
    assert c["conflict_type"] == "nonce"
    rr = row_by_id(rep["request_rows"], "req-expired-nonce")
    req = next(r for r in _read_ndjson() if r["request_id"] == "req-expired-nonce")
    nonces = {n["nonce_id"]: n for n in _load_json("nonce_challenges.json")}
    assert c["subject"] == req["nonce_id"]
    assert c["related_values"] == sorted(
        {str(rr["received_at"]), str(nonces[req["nonce_id"]]["expires_at"])}
    )

    restore_canonical()
    nonces = _load_json("nonce_challenges.json")
    assert isinstance(nonces, list)
    for n in nonces:
        if n["nonce_id"] == "nonce-edge-1":
            # Keep key validity (valid_from=1000) but make nonce not yet issued.
            n["issued_at"] = 15000
    _write_json("nonce_challenges.json", nonces)
    assert run_bin().returncode == 0
    rep_ny = load_report()
    assert row_by_id(rep_ny["request_rows"], "req-edge-ok")["reason_or_null"] == (
        "nonce_not_yet_valid"
    )
    c = conflict_for(rep_ny, "req-edge-ok", "nonce_not_yet_valid")
    assert c["conflict_type"] == "nonce"
    assert c["subject"] == "nonce-edge-1"
    rr = row_by_id(rep_ny["request_rows"], "req-edge-ok")
    nonces_m = {n["nonce_id"]: n for n in _load_json("nonce_challenges.json")}
    assert c["related_values"] == sorted(
        {str(rr["received_at"]), str(nonces_m["nonce-edge-1"]["issued_at"])}
    )

    restore_canonical()
    nonces = _load_json("nonce_challenges.json")
    assert isinstance(nonces, list)
    for n in nonces:
        if n["nonce_id"] == "nonce-edge-1":
            hx = n["nonce_hex"]
            n["nonce_hex"] = ("0" if hx[0] != "0" else "1") + hx[1:]
    _write_json("nonce_challenges.json", nonces)
    assert run_bin().returncode == 0
    rep_mm = load_report()
    assert row_by_id(rep_mm["request_rows"], "req-edge-ok")["reason_or_null"] == ("nonce_mismatch")
    c = conflict_for(rep_mm, "req-edge-ok", "nonce_mismatch")
    assert c["conflict_type"] == "nonce"
    assert c["subject"] == "nonce-edge-1"
    qr = row_by_id(rep_mm["quote_rows"], "req-edge-ok")
    nonces_m = {n["nonce_id"]: n for n in _load_json("nonce_challenges.json")}
    assert c["related_values"] == sorted(
        {qr["extra_data_hex"], nonces_m["nonce-edge-1"]["nonce_hex"]}
    )
    restore_canonical()


def test_06_nonce_replay_and_consumption_boundary(canonical_run):
    """Accepted and PCR-mismatch consume; bad-sig does not; reuse is nonce_consumed."""
    _, proc = canonical_run
    assert proc.returncode == 0
    rep = load_report()
    assert row_by_id(rep["nonce_rows"], "nonce-edge-1", "nonce_id")[
        "consumed_by_request_id_or_null"
    ] == ("req-edge-ok")
    assert row_by_id(rep["nonce_rows"], "nonce-edge-4", "nonce_id")["final_status"] == ("available")
    assert row_by_id(rep["nonce_rows"], "nonce-edge-7", "nonce_id")[
        "consumed_by_request_id_or_null"
    ] == ("req-pcr-mismatch")
    assert row_by_id(rep["request_rows"], "req-nonce-reuse")["reason_or_null"] == "nonce_consumed"
    c = conflict_for(rep, "req-nonce-reuse", "nonce_consumed")
    assert c["conflict_type"] == "nonce"
    assert c["subject"] == "nonce-edge-1"
    assert c["related_values"] == ["req-edge-ok"]


def test_07_pcr_selection_bitset_and_required_set():
    """Policy required_pcrs mismatch against quoted selection is quote_pcr_selection_invalid."""
    restore_canonical()
    pols = _load_json("reference_policies.json")
    assert isinstance(pols, list)
    for pol in pols:
        if pol["policy_id"] == "pol-edge-strict":
            pol["required_pcrs"] = [0]
    _write_json("reference_policies.json", pols)
    assert run_bin().returncode == 0
    rep = load_report()
    row = row_by_id(rep["request_rows"], "req-edge-ok")
    assert row["reason_or_null"] == "quote_pcr_selection_invalid"
    assert row["nonce_consumed_by_this_request"] is True
    c = conflict_for(rep, "req-edge-ok", "quote_pcr_selection_invalid")
    assert c["conflict_type"] == "pcr"
    assert c["subject"] == "pol-edge-strict"
    qr = row_by_id(rep["quote_rows"], "req-edge-ok")
    selected_set = ",".join(str(i) for i in qr["selected_pcrs"])
    required_set = "0"
    assert c["related_values"] == sorted({selected_set, required_set})
    restore_canonical()


def test_08_single_pcr_extend_replay(canonical_run):
    """Sensor PCR0 matches sequential SHA-256 extend of event digests in seq order."""
    _, proc = canonical_run
    assert proc.returncode == 0
    logs = _load_json("event_logs.json")
    assert isinstance(logs, list)
    elog = next(x for x in logs if x["event_log_id"] == "elog-sensor-ok")
    pcr = bytes(32)
    for ev in sorted(elog["events"], key=lambda e: e["event_seq"]):
        if int(ev["pcr_index"]) == 0:
            pcr = sha256(pcr + decode_lower_hex(ev["measurement_digest"]))
    expected = encode_lower_hex(pcr)
    actual = next(
        r["replayed_value"]
        for r in load_report()["pcr_rows"]
        if r["request_id"] == "req-sensor-ok" and r["pcr_index"] == 0
    )
    assert actual == expected


def test_09_multi_pcr_replay_and_selected_digest(canonical_run):
    """Edge quote selected PCR set [0,4,7] and computed digest matches quoted digest."""
    _, proc = canonical_run
    assert proc.returncode == 0
    qr = row_by_id(load_report()["quote_rows"], "req-edge-ok")
    assert qr["selected_pcrs"] == [0, 4, 7]
    assert qr["computed_pcr_digest_or_null"] == qr["quoted_pcr_digest"]
    assert qr["pcr_digest_status"] == "matched"


def test_10_event_seq_order_and_physical_order_independence():
    """Physical event shuffle is irrelevant; swapping event_seq semantics breaks digest."""
    restore_canonical()
    logs = _load_json("event_logs.json")
    assert isinstance(logs, list)
    for log in logs:
        if log["event_log_id"] == "elog-edge-ok":
            random.Random(42).shuffle(log["events"])
    _write_json("event_logs.json", logs)
    assert run_bin().returncode == 0
    assert row_by_id(load_report()["request_rows"], "req-edge-ok")["status"] == "accepted"

    restore_canonical()
    logs = _load_json("event_logs.json")
    assert isinstance(logs, list)
    for log in logs:
        if log["event_log_id"] == "elog-edge-ok":
            # Swap two same-PCR event_seq values to change extension order.
            by_seq = {e["event_seq"]: e for e in log["events"]}
            a, b = by_seq[20], by_seq[30]
            a["event_seq"], b["event_seq"] = 30, 20
    _write_json("event_logs.json", logs)
    assert run_bin().returncode == 0
    assert (
        row_by_id(load_report()["request_rows"], "req-edge-ok")["reason_or_null"]
        == "pcr_digest_mismatch"
    )
    restore_canonical()


def test_11_event_log_device_binding_and_pcr_digest_mismatch(canonical_run):
    """Fixture PCR mismatch and mutated event-log device binding."""
    _, proc = canonical_run
    assert proc.returncode == 0
    rep = load_report()
    mm = row_by_id(rep["request_rows"], "req-pcr-mismatch")
    assert mm["reason_or_null"] == "pcr_digest_mismatch"
    assert mm["nonce_consumed_by_this_request"] is True
    assert mm["counter_committed"] is False
    c = conflict_for(rep, "req-pcr-mismatch", "pcr_digest_mismatch")
    assert c["conflict_type"] == "pcr"
    req = next(r for r in _read_ndjson() if r["request_id"] == "req-pcr-mismatch")
    assert c["subject"] == req["event_log_id"]
    qr = row_by_id(rep["quote_rows"], "req-pcr-mismatch")
    assert c["related_values"] == sorted(
        {qr["quoted_pcr_digest"], qr["computed_pcr_digest_or_null"]}
    )

    restore_canonical()
    logs = _load_json("event_logs.json")
    assert isinstance(logs, list)
    for log in logs:
        if log["event_log_id"] == "elog-edge-ok":
            log["device_id"] = "dev-sensor"
    _write_json("event_logs.json", logs)
    assert run_bin().returncode == 0
    rep_el = load_report()
    row = row_by_id(rep_el["request_rows"], "req-edge-ok")
    assert row["reason_or_null"] == "event_log_device_mismatch"
    assert row["nonce_consumed_by_this_request"] is True
    assert row["counter_committed"] is False
    c = conflict_for(rep_el, "req-edge-ok", "event_log_device_mismatch")
    assert c["conflict_type"] == "pcr"
    assert c["subject"] == "elog-edge-ok"
    assert c["related_values"] == sorted({"dev-sensor", "dev-edge"})
    restore_canonical()


def test_12_safe_clock_and_firmware_policy(canonical_run):
    """Unsafe clock rejects without commit; firmware allow-list rejects after commit."""
    _, proc = canonical_run
    assert proc.returncode == 0
    rep = load_report()
    unsafe = row_by_id(rep["request_rows"], "req-unsafe")
    assert unsafe["reason_or_null"] == "clock_unsafe"
    assert unsafe["counter_committed"] is False
    c = conflict_for(rep, "req-unsafe", "clock_unsafe")
    assert c["conflict_type"] == "counter"
    assert c["subject"] == "dev-edge"
    qr = row_by_id(rep["quote_rows"], "req-unsafe")
    assert c["related_values"] == [str(qr["safe"])]

    restore_canonical()
    pols = _load_json("reference_policies.json")
    assert isinstance(pols, list)
    for pol in pols:
        if pol["policy_id"] == "pol-edge-strict":
            pol["allowed_firmware_versions"] = [999]
    _write_json("reference_policies.json", pols)
    assert run_bin().returncode == 0
    rep_fw = load_report()
    row = row_by_id(rep_fw["request_rows"], "req-edge-ok")
    assert row["reason_or_null"] == "firmware_not_allowed"
    assert row["nonce_consumed_by_this_request"] is True
    assert row["counter_committed"] is True
    c = conflict_for(rep_fw, "req-edge-ok", "firmware_not_allowed")
    assert c["conflict_type"] == "firmware"
    qr = row_by_id(rep_fw["quote_rows"], "req-edge-ok")
    assert c["subject"] == str(qr["firmware_version"])
    assert c["related_values"] == [c["subject"]]
    restore_canonical()


def test_13_required_reference_measurement(canonical_run):
    """Missing required kernel event yields reference_measurement_mismatch with missing status."""
    _, proc = canonical_run
    assert proc.returncode == 0
    rep = load_report()
    row = row_by_id(rep["request_rows"], "req-missing")
    assert row["reason_or_null"] == "reference_measurement_mismatch"
    rule = _match_row(rep, "req-missing", "rule-kernel")
    assert rule["status"] == "missing"
    assert rule["reason_or_null"] == "required_event_missing"
    c = conflict_for(rep, "req-missing", "reference_measurement_mismatch")
    assert c["conflict_type"] == "measurement"
    assert c["subject"] == "pol-edge-strict"
    assert c["related_values"] == ["pol-edge-strict"]
    assert c["subject"] != "rule-kernel"
    assert rule["rule_id"] == "rule-kernel"


def test_14_optional_and_unknown_measurements(canonical_run):
    """Optional absent/present and unknown-event allow/reject modes."""
    _, proc = canonical_run
    assert proc.returncode == 0
    rep = load_report()
    assert _match_row(rep, "req-edge-ok", "rule-opt")["status"] == "absent_allowed"
    assert _match_row(rep, "req-sensor-ok", "rule-sensor-opt")["status"] == "matched"
    sensor_events = [e for e in rep["event_rows"] if e["request_id"] == "req-sensor-ok"]
    assert any(e["policy_status"] == "allowed_unknown" for e in sensor_events)

    restore_canonical()
    pols = _load_json("reference_policies.json")
    assert isinstance(pols, list)
    for pol in pols:
        if pol["policy_id"] == "pol-sensor-single":
            pol["unknown_event_mode"] = "reject"
    _write_json("reference_policies.json", pols)
    assert run_bin().returncode == 0
    rep_u = load_report()
    assert (
        row_by_id(rep_u["request_rows"], "req-sensor-ok")["reason_or_null"]
        == "reference_measurement_mismatch"
    )
    c = conflict_for(rep_u, "req-sensor-ok", "reference_measurement_mismatch")
    assert c["conflict_type"] == "measurement"
    assert c["subject"] == "pol-sensor-single"
    assert c["related_values"] == ["pol-sensor-single"]
    restore_canonical()


def test_15_forbidden_reference_measurement(canonical_run):
    """Forbidden event rejects with commit and forbidden_present rule status."""
    _, proc = canonical_run
    assert proc.returncode == 0
    rep = load_report()
    row = row_by_id(rep["request_rows"], "req-edge-forbidden")
    assert row["status"] == "rejected"
    assert row["reason_or_null"] == "reference_measurement_mismatch"
    assert row["nonce_consumed_by_this_request"] is True
    assert row["counter_committed"] is True
    rule = _match_row(rep, "req-edge-forbidden", "rule-debug")
    assert rule["status"] == "forbidden_present"
    c = conflict_for(rep, "req-edge-forbidden", "reference_measurement_mismatch")
    assert c["conflict_type"] == "measurement"
    assert c["subject"] == "pol-edge-strict"
    assert c["related_values"] == ["pol-edge-strict"]
    assert c["subject"] != rule["rule_id"]


def test_16_reference_version_and_digest_mismatch():
    """Mutating allowed_versions to exclude firmware causes version_mismatch reject."""
    restore_canonical()
    pols = _load_json("reference_policies.json")
    assert isinstance(pols, list)
    for pol in pols:
        if pol["policy_id"] == "pol-edge-strict":
            for rule in pol["measurement_rules"]:
                if rule["rule_id"] == "rule-fw":
                    rule["allowed_versions"] = ["9.9.9"]
    _write_json("reference_policies.json", pols)
    assert run_bin().returncode == 0
    rep = load_report()
    assert (
        row_by_id(rep["request_rows"], "req-edge-ok")["reason_or_null"]
        == "reference_measurement_mismatch"
    )
    assert _match_row(rep, "req-edge-ok", "rule-fw")["status"] == "version_mismatch"
    c = conflict_for(rep, "req-edge-ok", "reference_measurement_mismatch")
    assert c["conflict_type"] == "measurement"
    assert c["subject"] == "pol-edge-strict"
    assert c["related_values"] == ["pol-edge-strict"]
    assert "rule-fw" not in c["related_values"]
    assert c["subject"] != "rule-fw"
    restore_canonical()


def _resign_edge_request(request_id: str, event_log_id: str) -> None:
    """Recompute quote PCR digest and ECDSA signature for an edge-device request."""
    import hashlib

    from cryptography.hazmat.primitives.asymmetric import ec
    from reference.p256 import N, sign_ecdsa_p256_sha256
    from reference.pcr import replay_events, selected_pcr_digest
    from reference.quote import encode_quote, encode_signature, parse_quote

    d = int.from_bytes(hashlib.sha256(b"seed-ak-edge-1").digest(), "big") % N or 1
    sk = ec.derive_private_key(d, ec.SECP256R1())
    logs = _load_json("event_logs.json")
    assert isinstance(logs, list)
    elog = next(x for x in logs if x["event_log_id"] == event_log_id)
    rows = _read_ndjson()
    req = next(r for r in rows if r["request_id"] == request_id)
    old = parse_quote(decode_lower_hex(req["quote_hex"]))
    pcrs = replay_events(elog["events"])
    digest = selected_pcr_digest(pcrs, old.selected_pcrs)
    quote = encode_quote(
        qualified_signer=old.qualified_signer,
        extra_data=old.extra_data,
        clock=old.clock,
        reset_count=old.reset_count,
        restart_count=old.restart_count,
        safe=old.safe,
        firmware_version=old.firmware_version,
        selected_pcrs=old.selected_pcrs,
        pcr_digest=digest,
    )
    r_b, s_b = sign_ecdsa_p256_sha256(sk, quote)
    req["quote_hex"] = encode_lower_hex(quote)
    req["signature_hex"] = encode_lower_hex(encode_signature(r_b, s_b))
    _write_ndjson(rows)


def test_17_measurement_rule_duplicate_and_missing_behavior():
    """Duplicate selector match yields duplicate status; missing covered by fixture."""
    restore_canonical()
    logs = _load_json("event_logs.json")
    assert isinstance(logs, list)
    for log in logs:
        if log["event_log_id"] == "elog-edge-ok":
            fw = next(e for e in log["events"] if e["component"] == "firmware")
            dup = dict(fw)
            dup["event_seq"] = 11
            log["events"].append(dup)
    _write_json("event_logs.json", logs)
    _resign_edge_request("req-edge-ok", "elog-edge-ok")
    # Isolate to the mutated request so later edge requests do not confuse counters.
    _write_ndjson([r for r in _read_ndjson() if r["request_id"] == "req-edge-ok"])
    assert run_bin().returncode == 0
    rep = load_report()
    assert (
        row_by_id(rep["request_rows"], "req-edge-ok")["reason_or_null"]
        == "reference_measurement_mismatch"
    )
    assert _match_row(rep, "req-edge-ok", "rule-fw")["status"] == "duplicate"
    c = conflict_for(rep, "req-edge-ok", "reference_measurement_mismatch")
    assert c["conflict_type"] == "measurement"
    assert c["subject"] == "pol-edge-strict"
    assert c["related_values"] == ["pol-edge-strict"]

    restore_canonical()
    assert run_bin().returncode == 0
    rep_m = load_report()
    assert (
        row_by_id(rep_m["request_rows"], "req-missing")["reason_or_null"]
        == "reference_measurement_mismatch"
    )
    assert _match_row(rep_m, "req-missing", "rule-kernel")["status"] == "missing"
    c = conflict_for(rep_m, "req-missing", "reference_measurement_mismatch")
    assert c["conflict_type"] == "measurement"
    assert c["subject"] == "pol-edge-strict"
    assert c["related_values"] == ["pol-edge-strict"]


def test_18_event_order_constraints(canonical_run):
    """Order violation fixture; optional-absent skips order endpoint involving that rule."""
    _, proc = canonical_run
    assert proc.returncode == 0
    rep = load_report()
    assert (
        row_by_id(rep["request_rows"], "req-order-bad")["reason_or_null"] == "event_order_violation"
    )
    c = conflict_for(rep, "req-order-bad", "event_order_violation")
    assert c["conflict_type"] == "event_order"
    assert c["subject"] == "rule-boot->rule-kernel"
    assert " " not in c["subject"]
    assert c["related_values"] == sorted({"rule-boot", "rule-kernel"})
    # req-edge-ok has optional rule-opt absent; still accepted (order involving
    # absent optional endpoints is skipped).
    assert row_by_id(rep["request_rows"], "req-edge-ok")["status"] == "accepted"
    assert _match_row(rep, "req-edge-ok", "rule-opt")["status"] == "absent_allowed"


def test_19_reset_restart_and_clock_monotonicity(canonical_run):
    """Rollback rejects; reset-up and restart-up counter advances are accepted."""
    _, proc = canonical_run
    assert proc.returncode == 0
    rep = load_report()
    assert (
        row_by_id(rep["request_rows"], "req-edge-rollback")["reason_or_null"] == "counter_rollback"
    )
    c = conflict_for(rep, "req-edge-rollback", "counter_rollback")
    assert c["conflict_type"] == "counter"
    assert c["subject"] == "dev-edge"
    cr = row_by_id(rep["counter_rows"], "req-edge-rollback")
    expected_related = sorted(
        {
            str(cr["prior_reset_count"]),
            str(cr["prior_restart_count"]),
            str(cr["prior_clock"]),
            str(cr["quoted_reset_count"]),
            str(cr["quoted_restart_count"]),
            str(cr["quoted_clock"]),
        }
    )
    assert c["related_values"] == expected_related
    assert row_by_id(rep["request_rows"], "req-reset-up")["status"] == "accepted"
    assert row_by_id(rep["request_rows"], "req-restart-up")["status"] == "accepted"


def test_20_authenticated_rejection_state_commit_and_failure_precedence(canonical_run):
    """Forbidden commits state; rollback after; bad-sig no state; device_unknown precedence."""
    _, proc = canonical_run
    assert proc.returncode == 0
    rep = load_report()
    forbidden = row_by_id(rep["request_rows"], "req-edge-forbidden")
    assert forbidden["counter_committed"] is True
    assert forbidden["nonce_consumed_by_this_request"] is True
    rollback = row_by_id(rep["request_rows"], "req-edge-rollback")
    assert rollback["reason_or_null"] == "counter_rollback"
    assert rollback["counter_committed"] is False
    bad = row_by_id(rep["request_rows"], "req-bad-sig")
    assert bad["reason_or_null"] == "quote_signature_invalid"
    assert bad["nonce_consumed_by_this_request"] is False
    assert bad["counter_committed"] is False

    restore_canonical()
    rows = _read_ndjson()
    for row in rows:
        if row["request_id"] == "req-bad-sig":
            row["device_id"] = "dev-does-not-exist"
            # Also truncate quote so both faults are present.
            row["quote_hex"] = row["quote_hex"][:8]
    _write_ndjson(rows)
    assert run_bin().returncode == 0
    rep_u = load_report()
    assert row_by_id(rep_u["request_rows"], "req-bad-sig")["reason_or_null"] == "device_unknown"
    c = conflict_for(rep_u, "req-bad-sig", "device_unknown")
    assert c["conflict_type"] == "identity"
    assert c["subject"] == "dev-does-not-exist"
    assert c["related_values"] == ["dev-does-not-exist"]
    restore_canonical()


def test_21_dynamic_event_mutation_locality():
    """One event digest mutation localizes PCR mismatch without affecting other devices."""
    restore_canonical()
    snap0 = capture_from_dir(DATA_DIR)
    assert run_bin().returncode == 0
    verify_unchanged(snap0, DATA_DIR)
    base = load_report()

    logs = _load_json("event_logs.json")
    assert isinstance(logs, list)
    mutated = False
    for log in logs:
        if log["event_log_id"] == "elog-edge-ok":
            for ev in log["events"]:
                if ev["component"] == "firmware":
                    dig = ev["measurement_digest"]
                    ev["measurement_digest"] = ("0" if dig[0] != "0" else "1") + dig[1:]
                    mutated = True
                    break
    assert mutated
    _write_json("event_logs.json", logs)
    snap1 = capture_from_dir(DATA_DIR)
    assert run_bin().returncode == 0
    verify_unchanged(snap1, DATA_DIR)
    mut = load_report()

    edge = row_by_id(mut["request_rows"], "req-edge-ok")
    assert edge["reason_or_null"] == "pcr_digest_mismatch"
    assert edge["nonce_consumed_by_this_request"] is True
    assert edge["counter_committed"] is False
    base_pcrs = [r for r in base["pcr_rows"] if r["request_id"] == "req-edge-ok"]
    mut_pcrs = [r for r in mut["pcr_rows"] if r["request_id"] == "req-edge-ok"]
    assert base_pcrs != mut_pcrs
    # Sensor device projection unchanged.
    assert row_by_id(base["request_rows"], "req-sensor-ok") == row_by_id(
        mut["request_rows"], "req-sensor-ok"
    )
    assert [r for r in base["pcr_rows"] if r["request_id"] == "req-sensor-ok"] == [
        r for r in mut["pcr_rows"] if r["request_id"] == "req-sensor-ok"
    ]
    restore_canonical()


def test_22_five_seed_input_permutation_invariance():
    """Five-seed shuffle of unordered collections (with version/digest normalize) is invariant."""
    restore_canonical()
    assert run_bin().returncode == 0
    baseline = load_report()

    for seed in (7, 19, 41, 83, 127):
        restore_canonical()
        rng = random.Random(seed)
        devices = _load_json("devices.json")
        keys = _load_json("attestation_keys.json")
        pols = _load_json("reference_policies.json")
        logs = _load_json("event_logs.json")
        nonces = _load_json("nonce_challenges.json")
        rows = _read_ndjson()
        assert isinstance(devices, list)
        assert isinstance(keys, list)
        assert isinstance(pols, list)
        assert isinstance(logs, list)
        assert isinstance(nonces, list)

        rng.shuffle(devices)
        rng.shuffle(keys)
        rng.shuffle(pols)
        rng.shuffle(logs)
        rng.shuffle(nonces)
        rng.shuffle(rows)
        for pol in pols:
            for rule in pol.get("measurement_rules", []):
                if rule.get("allowed_versions"):
                    rng.shuffle(rule["allowed_versions"])
                if rule.get("allowed_digests"):
                    rng.shuffle(rule["allowed_digests"])
            if pol.get("allowed_firmware_versions"):
                rng.shuffle(pol["allowed_firmware_versions"])
            if pol.get("required_pcrs"):
                rng.shuffle(pol["required_pcrs"])
            if pol.get("allowed_device_classes"):
                rng.shuffle(pol["allowed_device_classes"])
            if pol.get("measurement_rules"):
                rng.shuffle(pol["measurement_rules"])
            if pol.get("order_constraints"):
                rng.shuffle(pol["order_constraints"])
        for log in logs:
            rng.shuffle(log["events"])

        _write_json("devices.json", devices)
        _write_json("attestation_keys.json", keys)
        _write_json("reference_policies.json", pols)
        _write_json("event_logs.json", logs)
        _write_json("nonce_challenges.json", nonces)
        _write_ndjson(rows)

        snap = capture_from_dir(DATA_DIR)
        assert run_bin().returncode == 0
        verify_unchanged(snap, DATA_DIR)
        assert load_report() == baseline
    restore_canonical()


def test_24_byte_identical_rerun_malformed_input_and_stale_cleanup():
    """Byte-identical rerun, indent/newline, request-level malformation, fatal stale cleanup."""
    restore_canonical()
    snap = capture_from_dir(DATA_DIR)
    assert run_bin().returncode == 0
    verify_unchanged(snap, DATA_DIR)
    b1 = OUTPUT.read_bytes()
    assert b1.endswith(b"\n")
    assert b"  " in b1
    assert run_bin().returncode == 0
    assert OUTPUT.read_bytes() == b1

    OUTPUT.write_text("stale\n", encoding="utf-8")
    Path(str(OUTPUT) + ".tmp").write_text("tmp\n", encoding="utf-8")
    assert run_bin().returncode == 0
    assert OUTPUT.read_bytes() == b1
    assert not Path(str(OUTPUT) + ".tmp").exists()

    restore_canonical()
    rows = _read_ndjson()
    for row in rows:
        if row["request_id"] == "req-edge-ok":
            row["quote_hex"] = row["quote_hex"][:-4]
    _write_ndjson(rows)
    snap_m = capture_from_dir(DATA_DIR)
    assert run_bin().returncode == 0
    verify_unchanged(snap_m, DATA_DIR)
    assert row_by_id(load_report()["request_rows"], "req-edge-ok")["reason_or_null"] == (
        "quote_malformed"
    )

    restore_canonical()
    snap2 = capture_from_dir(DATA_DIR)
    expected = verify_from_protected(snap2)
    (DATA_DIR / "policy.json").write_text("{", encoding="utf-8")
    proc = run_bin()
    assert proc.returncode != 0 and proc.stderr.strip()
    assert not OUTPUT.exists()
    assert mutation_detected(snap2, DATA_DIR)
    assert verify_from_protected(snap2) == expected
    restore_canonical()

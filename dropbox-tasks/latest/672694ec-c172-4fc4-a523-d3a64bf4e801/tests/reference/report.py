"""Independent attestation verification engine and report construction."""

from __future__ import annotations

import json
from typing import Any

from .binary import encode_lower_hex, sha256_hex
from .models import Dataset, load_dataset
from .p256 import verify_ecdsa_p256_sha256
from .pcr import replay_events, selected_pcr_digest
from .policy import appraise
from .protected_inputs import ProtectedInputSnapshot
from .quote import (
    ATTEST_QUOTE,
    MAGIC,
    magic_hex,
    parse_quote,
    parse_signature,
)

TOP_LEVEL_KEYS = [
    "request_rows",
    "quote_rows",
    "event_rows",
    "pcr_rows",
    "reference_match_rows",
    "counter_rows",
    "nonce_rows",
    "conflict_rows",
    "summary",
]


def serialize_report(report: dict[str, Any]) -> bytes:
    ordered = {k: report[k] for k in TOP_LEVEL_KEYS}
    text = json.dumps(ordered, indent=2, ensure_ascii=False)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    if not text.endswith("\n"):
        text += "\n"
    return text.encode("utf-8")


def _conflict(
    request_id: str, conflict_type: str, subject: str, reason: str, related: list[str]
) -> dict:
    return {
        "request_id": request_id,
        "conflict_type": conflict_type,
        "subject": subject,
        "reason_code": reason,
        "related_values": sorted(set(related)),
    }


def verify_dataset(ds: Dataset) -> dict[str, Any]:
    # Device mutable state
    device_state = {
        did: {
            "reset_count": d["last_reset_count"],
            "restart_count": d["last_restart_count"],
            "clock": d["last_clock"],
        }
        for did, d in ds.devices.items()
    }
    nonce_consumed: dict[str, str | None] = {}
    for nid, n in ds.nonces.items():
        if n["initially_consumed_by_request_id_or_null"] is not None:
            nonce_consumed[nid] = n["initially_consumed_by_request_id_or_null"]
        else:
            nonce_consumed[nid] = None

    request_rows: list[dict] = []
    quote_rows: list[dict] = []
    event_rows: list[dict] = []
    pcr_rows: list[dict] = []
    reference_match_rows: list[dict] = []
    counter_rows: list[dict] = []
    conflict_rows: list[dict] = []

    ordered_reqs = sorted(ds.requests, key=lambda r: (r["received_at"], r["request_id"]))

    for req in ordered_reqs:
        result = _process_one(
            ds,
            req,
            device_state,
            nonce_consumed,
            quote_rows,
            event_rows,
            pcr_rows,
            reference_match_rows,
            counter_rows,
            conflict_rows,
        )
        request_rows.append(result)

    nonce_rows = []
    for nid in sorted(ds.nonces.keys()):
        n = ds.nonces[nid]
        init_c = n["initially_consumed_by_request_id_or_null"]
        final_c = nonce_consumed[nid]
        nonce_rows.append(
            {
                "nonce_id": nid,
                "device_id": n["device_id"],
                "issued_at": n["issued_at"],
                "expires_at": n["expires_at"],
                "initial_status": "consumed" if init_c is not None else "available",
                "final_status": "consumed" if final_c is not None else "available",
                "consumed_by_request_id_or_null": final_c,
            }
        )

    request_rows.sort(key=lambda r: r["request_id"])
    quote_rows.sort(key=lambda r: r["request_id"])
    event_rows.sort(key=lambda r: (r["request_id"], r["event_seq"]))
    pcr_rows.sort(key=lambda r: (r["request_id"], r["pcr_index"]))
    reference_match_rows.sort(key=lambda r: (r["request_id"], r["rule_id"]))
    counter_rows.sort(key=lambda r: r["request_id"])
    conflict_rows.sort(
        key=lambda r: (r["request_id"], r["conflict_type"], r["subject"], r["reason_code"])
    )

    summary = {
        "request_count": len(request_rows),
        "accepted_request_count": sum(1 for r in request_rows if r["status"] == "accepted"),
        "rejected_request_count": sum(1 for r in request_rows if r["status"] == "rejected"),
        "quote_row_count": len(quote_rows),
        "event_row_count": len(event_rows),
        "pcr_row_count": len(pcr_rows),
        "reference_match_row_count": len(reference_match_rows),
        "matched_rule_count": sum(r["matched_rule_count"] for r in request_rows),
        "failed_rule_count": sum(r["failed_rule_count"] for r in request_rows),
        "initially_consumed_nonce_count": sum(
            1 for r in nonce_rows if r["initial_status"] == "consumed"
        ),
        "finally_consumed_nonce_count": sum(
            1 for r in nonce_rows if r["final_status"] == "consumed"
        ),
        "counter_commit_count": sum(1 for r in counter_rows if r["committed"]),
        "conflict_count": len(conflict_rows),
    }

    return {
        "request_rows": request_rows,
        "quote_rows": quote_rows,
        "event_rows": event_rows,
        "pcr_rows": pcr_rows,
        "reference_match_rows": reference_match_rows,
        "counter_rows": counter_rows,
        "nonce_rows": nonce_rows,
        "conflict_rows": conflict_rows,
        "summary": summary,
    }


def _reject_row(
    req: dict,
    reason: str,
    *,
    nonce_consumed: bool = False,
    counter_committed: bool = False,
    selected_pcr_count: int = 0,
    replayed_event_count: int = 0,
    matched_rule_count: int = 0,
    failed_rule_count: int = 0,
) -> dict:
    return {
        "request_id": req["request_id"],
        "received_at": req["received_at"],
        "device_id": req["device_id"],
        "status": "rejected",
        "reason_or_null": reason,
        "nonce_consumed_by_this_request": nonce_consumed,
        "selected_pcr_count": selected_pcr_count,
        "replayed_event_count": replayed_event_count,
        "matched_rule_count": matched_rule_count,
        "failed_rule_count": failed_rule_count,
        "counter_committed": counter_committed,
    }


def _process_one(
    ds: Dataset,
    req: dict,
    device_state: dict,
    nonce_consumed: dict,
    quote_rows: list,
    event_rows: list,
    pcr_rows: list,
    reference_match_rows: list,
    counter_rows: list,
    conflict_rows: list,
) -> dict:
    rid = req["request_id"]

    # 1 device
    if req["device_id"] not in ds.devices:
        conflict_rows.append(
            _conflict(rid, "identity", req["device_id"], "device_unknown", [req["device_id"]])
        )
        return _reject_row(req, "device_unknown")

    # 2 key
    if req["attestation_key_id"] not in ds.keys:
        conflict_rows.append(
            _conflict(
                rid,
                "identity",
                req["attestation_key_id"],
                "attestation_key_unknown",
                [req["attestation_key_id"]],
            )
        )
        return _reject_row(req, "attestation_key_unknown")

    # 3 nonce
    if req["nonce_id"] not in ds.nonces:
        conflict_rows.append(
            _conflict(rid, "nonce", req["nonce_id"], "nonce_unknown", [req["nonce_id"]])
        )
        return _reject_row(req, "nonce_unknown")

    # 4 policy
    if req["policy_id"] not in ds.policies:
        conflict_rows.append(
            _conflict(
                rid,
                "identity",
                req["policy_id"],
                "reference_policy_unknown",
                [req["policy_id"]],
            )
        )
        return _reject_row(req, "reference_policy_unknown")

    # 5 event log
    if req["event_log_id"] not in ds.event_logs:
        conflict_rows.append(
            _conflict(
                rid,
                "identity",
                req["event_log_id"],
                "event_log_unknown",
                [req["event_log_id"]],
            )
        )
        return _reject_row(req, "event_log_unknown")

    device = ds.devices[req["device_id"]]
    key = ds.keys[req["attestation_key_id"]]
    nonce = ds.nonces[req["nonce_id"]]
    policy = ds.policies[req["policy_id"]]
    elog = ds.event_logs[req["event_log_id"]]

    # 6 key belongs to device
    if key["device_id"] != req["device_id"]:
        conflict_rows.append(
            _conflict(
                rid,
                "identity",
                req["attestation_key_id"],
                "attestation_key_device_mismatch",
                [key["device_id"], req["device_id"]],
            )
        )
        return _reject_row(req, "attestation_key_device_mismatch")

    # 7 device class allowed
    if device["device_class"] not in policy["allowed_device_classes"]:
        conflict_rows.append(
            _conflict(
                rid,
                "identity",
                device["device_class"],
                "device_class_not_allowed",
                [device["device_class"], req["policy_id"]],
            )
        )
        return _reject_row(req, "device_class_not_allowed")

    # 8 quote parse
    try:
        quote = parse_quote(req["quote_bytes"])
    except ValueError:
        return _reject_row(req, "quote_malformed")

    # quote parsed — emit counter row scaffolding later; prepare quote row fields
    fp = sha256_hex(key["public_key_sec1"])

    # 9 signature parse
    try:
        sig = parse_signature(req["signature_bytes"])
    except ValueError:
        # quote parsed successfully → still emit quote_row with not_checked sig?
        # Spec: quote_rows emit when quote parsed successfully.
        quote_rows.append(
            {
                "request_id": rid,
                "attestation_key_id": key["attestation_key_id"],
                "attestation_key_fingerprint": fp,
                "magic_hex": magic_hex(quote.magic),
                "attestation_type": "quote",
                "qualified_signer_hex": encode_lower_hex(quote.qualified_signer),
                "extra_data_hex": encode_lower_hex(quote.extra_data),
                "clock": quote.clock,
                "reset_count": quote.reset_count,
                "restart_count": quote.restart_count,
                "safe": quote.safe,
                "firmware_version": quote.firmware_version,
                "selected_pcrs": list(quote.selected_pcrs),
                "quoted_pcr_digest": encode_lower_hex(quote.pcr_digest),
                "computed_pcr_digest_or_null": None,
                "signature_status": "not_checked",
                "pcr_digest_status": "not_checked",
            }
        )
        prior = device_state[req["device_id"]]
        counter_rows.append(
            {
                "request_id": rid,
                "device_id": req["device_id"],
                "prior_reset_count": prior["reset_count"],
                "prior_restart_count": prior["restart_count"],
                "prior_clock": prior["clock"],
                "quoted_reset_count": quote.reset_count,
                "quoted_restart_count": quote.restart_count,
                "quoted_clock": quote.clock,
                "safe": quote.safe,
                "status": "not_checked",
                "committed": False,
            }
        )
        return _reject_row(req, "signature_malformed")

    # 10 magic
    if quote.magic != MAGIC:
        quote_rows.append(_quote_row(rid, key, fp, quote, "not_checked", "not_checked", None))
        _counter_not_checked(counter_rows, rid, req, device_state, quote)
        conflict_rows.append(
            _conflict(
                rid,
                "identity",
                magic_hex(quote.magic),
                "quote_magic_invalid",
                [magic_hex(quote.magic)],
            )
        )
        return _reject_row(req, "quote_magic_invalid")

    # 11 type
    if quote.attestation_type != ATTEST_QUOTE:
        quote_rows.append(_quote_row(rid, key, fp, quote, "not_checked", "not_checked", None))
        _counter_not_checked(counter_rows, rid, req, device_state, quote)
        conflict_rows.append(
            _conflict(
                rid,
                "identity",
                f"0x{quote.attestation_type:04x}",
                "quote_type_invalid",
                [f"0x{quote.attestation_type:04x}"],
            )
        )
        return _reject_row(req, "quote_type_invalid")

    # 12 qualified signer
    if quote.qualified_signer != key["qualified_name"]:
        quote_rows.append(_quote_row(rid, key, fp, quote, "not_checked", "not_checked", None))
        _counter_not_checked(counter_rows, rid, req, device_state, quote)
        conflict_rows.append(
            _conflict(
                rid,
                "identity",
                key["attestation_key_id"],
                "qualified_signer_mismatch",
                [encode_lower_hex(quote.qualified_signer), key["qualified_name_hex"]],
            )
        )
        return _reject_row(req, "qualified_signer_mismatch")

    # 13 key validity
    if not (key["valid_from"] <= req["received_at"] <= key["valid_until"]):
        quote_rows.append(_quote_row(rid, key, fp, quote, "not_checked", "not_checked", None))
        _counter_not_checked(counter_rows, rid, req, device_state, quote)
        conflict_rows.append(
            _conflict(
                rid,
                "identity",
                key["attestation_key_id"],
                "attestation_key_not_valid",
                [str(req["received_at"]), str(key["valid_from"]), str(key["valid_until"])],
            )
        )
        return _reject_row(req, "attestation_key_not_valid")

    # 14 signature verify
    sig_ok = verify_ecdsa_p256_sha256(key["public_key_sec1"], quote.raw, sig.r, sig.s)
    if not sig_ok:
        quote_rows.append(_quote_row(rid, key, fp, quote, "invalid", "not_checked", None))
        _counter_not_checked(counter_rows, rid, req, device_state, quote)
        conflict_rows.append(
            _conflict(
                rid,
                "identity",
                key["attestation_key_id"],
                "quote_signature_invalid",
                [key["attestation_key_id"]],
            )
        )
        return _reject_row(req, "quote_signature_invalid")

    # 15 nonce device
    if nonce["device_id"] != req["device_id"]:
        quote_rows.append(_quote_row(rid, key, fp, quote, "valid", "not_checked", None))
        _counter_not_checked(counter_rows, rid, req, device_state, quote)
        conflict_rows.append(
            _conflict(
                rid,
                "nonce",
                nonce["nonce_id"],
                "nonce_device_mismatch",
                [nonce["device_id"], req["device_id"]],
            )
        )
        return _reject_row(req, "nonce_device_mismatch")

    # 16 not yet valid
    if req["received_at"] < nonce["issued_at"]:
        quote_rows.append(_quote_row(rid, key, fp, quote, "valid", "not_checked", None))
        _counter_not_checked(counter_rows, rid, req, device_state, quote)
        conflict_rows.append(
            _conflict(
                rid,
                "nonce",
                nonce["nonce_id"],
                "nonce_not_yet_valid",
                [str(req["received_at"]), str(nonce["issued_at"])],
            )
        )
        return _reject_row(req, "nonce_not_yet_valid")

    # 17 expired
    if req["received_at"] > nonce["expires_at"]:
        quote_rows.append(_quote_row(rid, key, fp, quote, "valid", "not_checked", None))
        _counter_not_checked(counter_rows, rid, req, device_state, quote)
        conflict_rows.append(
            _conflict(
                rid,
                "nonce",
                nonce["nonce_id"],
                "nonce_expired",
                [str(req["received_at"]), str(nonce["expires_at"])],
            )
        )
        return _reject_row(req, "nonce_expired")

    # 18 consumed
    if nonce_consumed[nonce["nonce_id"]] is not None:
        quote_rows.append(_quote_row(rid, key, fp, quote, "valid", "not_checked", None))
        _counter_not_checked(counter_rows, rid, req, device_state, quote)
        conflict_rows.append(
            _conflict(
                rid,
                "nonce",
                nonce["nonce_id"],
                "nonce_consumed",
                [str(nonce_consumed[nonce["nonce_id"]])],
            )
        )
        return _reject_row(req, "nonce_consumed")

    # 19 extra_data match
    if quote.extra_data != nonce["nonce_bytes"]:
        quote_rows.append(_quote_row(rid, key, fp, quote, "valid", "not_checked", None))
        _counter_not_checked(counter_rows, rid, req, device_state, quote)
        conflict_rows.append(
            _conflict(
                rid,
                "nonce",
                nonce["nonce_id"],
                "nonce_mismatch",
                [encode_lower_hex(quote.extra_data), nonce["nonce_hex"]],
            )
        )
        return _reject_row(req, "nonce_mismatch")

    # CONSUME NONCE
    nonce_consumed[nonce["nonce_id"]] = rid

    # 20 PCR selection vs policy
    if list(quote.selected_pcrs) != list(policy["required_pcrs"]):
        quote_rows.append(_quote_row(rid, key, fp, quote, "valid", "not_checked", None))
        _counter_not_checked(counter_rows, rid, req, device_state, quote)
        conflict_rows.append(
            _conflict(
                rid,
                "pcr",
                req["policy_id"],
                "quote_pcr_selection_invalid",
                [
                    ",".join(map(str, quote.selected_pcrs)),
                    ",".join(map(str, policy["required_pcrs"])),
                ],
            )
        )
        return _reject_row(req, "quote_pcr_selection_invalid", nonce_consumed=True)

    # 21 event log device
    if elog["device_id"] != req["device_id"]:
        quote_rows.append(_quote_row(rid, key, fp, quote, "valid", "not_checked", None))
        _counter_not_checked(counter_rows, rid, req, device_state, quote)
        conflict_rows.append(
            _conflict(
                rid,
                "pcr",
                elog["event_log_id"],
                "event_log_device_mismatch",
                [elog["device_id"], req["device_id"]],
            )
        )
        return _reject_row(req, "event_log_device_mismatch", nonce_consumed=True)

    # Replay PCRs
    pcrs = replay_events(elog["events"])
    computed = selected_pcr_digest(pcrs, quote.selected_pcrs)
    computed_hex = encode_lower_hex(computed)
    replayed_event_count = len(elog["events"])
    selected_pcr_count = len(quote.selected_pcrs)

    # Emit event rows (policy status filled later or not_evaluated)
    # Emit PCR rows
    for pcr_index in (0, 2, 4, 7):
        pcr_rows.append(
            {
                "request_id": rid,
                "pcr_index": pcr_index,
                "selected": pcr_index in quote.selected_pcrs,
                "policy_required": pcr_index in policy["required_pcrs"],
                "replayed_value": encode_lower_hex(pcrs[pcr_index]),
            }
        )

    # 22 digest match
    if computed != quote.pcr_digest:
        quote_rows.append(_quote_row(rid, key, fp, quote, "valid", "mismatched", computed_hex))
        for ev in sorted(elog["events"], key=lambda e: e["event_seq"]):
            event_rows.append(
                {
                    "request_id": rid,
                    "event_log_id": elog["event_log_id"],
                    "event_seq": ev["event_seq"],
                    "pcr_index": ev["pcr_index"],
                    "event_type": ev["event_type"],
                    "component": ev["component"],
                    "version": ev["version"],
                    "measurement_digest": ev["measurement_digest"],
                    "policy_status": "not_evaluated",
                    "matched_rule_id_or_null": None,
                }
            )
        _counter_not_checked(counter_rows, rid, req, device_state, quote)
        conflict_rows.append(
            _conflict(
                rid,
                "pcr",
                elog["event_log_id"],
                "pcr_digest_mismatch",
                [encode_lower_hex(quote.pcr_digest), computed_hex],
            )
        )
        return _reject_row(
            req,
            "pcr_digest_mismatch",
            nonce_consumed=True,
            selected_pcr_count=selected_pcr_count,
            replayed_event_count=replayed_event_count,
        )

    # 23 safe clock
    prior = device_state[req["device_id"]]
    if policy["require_safe"] and quote.safe != 1:
        quote_rows.append(_quote_row(rid, key, fp, quote, "valid", "matched", computed_hex))
        for ev in sorted(elog["events"], key=lambda e: e["event_seq"]):
            event_rows.append(
                {
                    "request_id": rid,
                    "event_log_id": elog["event_log_id"],
                    "event_seq": ev["event_seq"],
                    "pcr_index": ev["pcr_index"],
                    "event_type": ev["event_type"],
                    "component": ev["component"],
                    "version": ev["version"],
                    "measurement_digest": ev["measurement_digest"],
                    "policy_status": "not_evaluated",
                    "matched_rule_id_or_null": None,
                }
            )
        counter_rows.append(
            {
                "request_id": rid,
                "device_id": req["device_id"],
                "prior_reset_count": prior["reset_count"],
                "prior_restart_count": prior["restart_count"],
                "prior_clock": prior["clock"],
                "quoted_reset_count": quote.reset_count,
                "quoted_restart_count": quote.restart_count,
                "quoted_clock": quote.clock,
                "safe": quote.safe,
                "status": "unsafe",
                "committed": False,
            }
        )
        conflict_rows.append(
            _conflict(rid, "counter", req["device_id"], "clock_unsafe", [str(quote.safe)])
        )
        return _reject_row(
            req,
            "clock_unsafe",
            nonce_consumed=True,
            selected_pcr_count=selected_pcr_count,
            replayed_event_count=replayed_event_count,
        )

    # 24 counter monotonicity
    rollback = False
    if quote.reset_count < prior["reset_count"]:
        rollback = True
    elif quote.reset_count == prior["reset_count"] and quote.restart_count < prior["restart_count"]:
        rollback = True
    elif (
        quote.reset_count == prior["reset_count"]
        and quote.restart_count == prior["restart_count"]
        and quote.clock < prior["clock"]
    ):
        rollback = True

    if rollback:
        quote_rows.append(_quote_row(rid, key, fp, quote, "valid", "matched", computed_hex))
        for ev in sorted(elog["events"], key=lambda e: e["event_seq"]):
            event_rows.append(
                {
                    "request_id": rid,
                    "event_log_id": elog["event_log_id"],
                    "event_seq": ev["event_seq"],
                    "pcr_index": ev["pcr_index"],
                    "event_type": ev["event_type"],
                    "component": ev["component"],
                    "version": ev["version"],
                    "measurement_digest": ev["measurement_digest"],
                    "policy_status": "not_evaluated",
                    "matched_rule_id_or_null": None,
                }
            )
        counter_rows.append(
            {
                "request_id": rid,
                "device_id": req["device_id"],
                "prior_reset_count": prior["reset_count"],
                "prior_restart_count": prior["restart_count"],
                "prior_clock": prior["clock"],
                "quoted_reset_count": quote.reset_count,
                "quoted_restart_count": quote.restart_count,
                "quoted_clock": quote.clock,
                "safe": quote.safe,
                "status": "rollback",
                "committed": False,
            }
        )
        conflict_rows.append(
            _conflict(
                rid,
                "counter",
                req["device_id"],
                "counter_rollback",
                [
                    str(prior["reset_count"]),
                    str(prior["restart_count"]),
                    str(prior["clock"]),
                    str(quote.reset_count),
                    str(quote.restart_count),
                    str(quote.clock),
                ],
            )
        )
        return _reject_row(
            req,
            "counter_rollback",
            nonce_consumed=True,
            selected_pcr_count=selected_pcr_count,
            replayed_event_count=replayed_event_count,
        )

    # COMMIT COUNTERS
    device_state[req["device_id"]] = {
        "reset_count": quote.reset_count,
        "restart_count": quote.restart_count,
        "clock": quote.clock,
    }

    # 25 firmware
    if quote.firmware_version not in policy["allowed_firmware_versions"]:
        quote_rows.append(_quote_row(rid, key, fp, quote, "valid", "matched", computed_hex))
        for ev in sorted(elog["events"], key=lambda e: e["event_seq"]):
            event_rows.append(
                {
                    "request_id": rid,
                    "event_log_id": elog["event_log_id"],
                    "event_seq": ev["event_seq"],
                    "pcr_index": ev["pcr_index"],
                    "event_type": ev["event_type"],
                    "component": ev["component"],
                    "version": ev["version"],
                    "measurement_digest": ev["measurement_digest"],
                    "policy_status": "not_evaluated",
                    "matched_rule_id_or_null": None,
                }
            )
        counter_rows.append(
            {
                "request_id": rid,
                "device_id": req["device_id"],
                "prior_reset_count": prior["reset_count"],
                "prior_restart_count": prior["restart_count"],
                "prior_clock": prior["clock"],
                "quoted_reset_count": quote.reset_count,
                "quoted_restart_count": quote.restart_count,
                "quoted_clock": quote.clock,
                "safe": quote.safe,
                "status": "accepted",
                "committed": True,
            }
        )
        conflict_rows.append(
            _conflict(
                rid,
                "firmware",
                str(quote.firmware_version),
                "firmware_not_allowed",
                [str(quote.firmware_version)],
            )
        )
        return _reject_row(
            req,
            "firmware_not_allowed",
            nonce_consumed=True,
            counter_committed=True,
            selected_pcr_count=selected_pcr_count,
            replayed_event_count=replayed_event_count,
        )

    # Reference appraisal
    appraisal = appraise(policy, elog["events"])
    for rr in appraisal.rule_results:
        reference_match_rows.append(
            {
                "request_id": rid,
                "policy_id": policy["policy_id"],
                "rule_id": rr.rule_id,
                "rule_kind": rr.rule_kind,
                "matched_event_sequences": rr.matched_event_sequences,
                "status": rr.status,
                "reason_or_null": rr.reason_or_null,
            }
        )

    for ev in sorted(elog["events"], key=lambda e: e["event_seq"]):
        st, mrid = appraisal.event_policy_status.get(ev["event_seq"], ("not_evaluated", None))
        event_rows.append(
            {
                "request_id": rid,
                "event_log_id": elog["event_log_id"],
                "event_seq": ev["event_seq"],
                "pcr_index": ev["pcr_index"],
                "event_type": ev["event_type"],
                "component": ev["component"],
                "version": ev["version"],
                "measurement_digest": ev["measurement_digest"],
                "policy_status": st,
                "matched_rule_id_or_null": mrid,
            }
        )

    quote_rows.append(_quote_row(rid, key, fp, quote, "valid", "matched", computed_hex))
    counter_rows.append(
        {
            "request_id": rid,
            "device_id": req["device_id"],
            "prior_reset_count": prior["reset_count"],
            "prior_restart_count": prior["restart_count"],
            "prior_clock": prior["clock"],
            "quoted_reset_count": quote.reset_count,
            "quoted_restart_count": quote.restart_count,
            "quoted_clock": quote.clock,
            "safe": quote.safe,
            "status": "accepted",
            "committed": True,
        }
    )

    if appraisal.reject_reason is not None:
        ctype = (
            "event_order" if appraisal.reject_reason == "event_order_violation" else "measurement"
        )
        subject = req["policy_id"]
        related = [req["policy_id"]]
        if appraisal.order_failed:
            subject = f"{appraisal.order_failed[0]}->{appraisal.order_failed[1]}"
            related = list(appraisal.order_failed)
        conflict_rows.append(_conflict(rid, ctype, subject, appraisal.reject_reason, related))
        return _reject_row(
            req,
            appraisal.reject_reason,
            nonce_consumed=True,
            counter_committed=True,
            selected_pcr_count=selected_pcr_count,
            replayed_event_count=replayed_event_count,
            matched_rule_count=appraisal.matched_rule_count,
            failed_rule_count=appraisal.failed_rule_count,
        )

    return {
        "request_id": rid,
        "received_at": req["received_at"],
        "device_id": req["device_id"],
        "status": "accepted",
        "reason_or_null": None,
        "nonce_consumed_by_this_request": True,
        "selected_pcr_count": selected_pcr_count,
        "replayed_event_count": replayed_event_count,
        "matched_rule_count": appraisal.matched_rule_count,
        "failed_rule_count": appraisal.failed_rule_count,
        "counter_committed": True,
    }


def _quote_row(rid, key, fp, quote, sig_status, pcr_status, computed_hex):
    return {
        "request_id": rid,
        "attestation_key_id": key["attestation_key_id"],
        "attestation_key_fingerprint": fp,
        "magic_hex": magic_hex(quote.magic),
        "attestation_type": "quote",
        "qualified_signer_hex": encode_lower_hex(quote.qualified_signer),
        "extra_data_hex": encode_lower_hex(quote.extra_data),
        "clock": quote.clock,
        "reset_count": quote.reset_count,
        "restart_count": quote.restart_count,
        "safe": quote.safe,
        "firmware_version": quote.firmware_version,
        "selected_pcrs": list(quote.selected_pcrs),
        "quoted_pcr_digest": encode_lower_hex(quote.pcr_digest),
        "computed_pcr_digest_or_null": computed_hex,
        "signature_status": sig_status,
        "pcr_digest_status": pcr_status,
    }


def _counter_not_checked(counter_rows, rid, req, device_state, quote):
    prior = device_state[req["device_id"]]
    counter_rows.append(
        {
            "request_id": rid,
            "device_id": req["device_id"],
            "prior_reset_count": prior["reset_count"],
            "prior_restart_count": prior["restart_count"],
            "prior_clock": prior["clock"],
            "quoted_reset_count": quote.reset_count,
            "quoted_restart_count": quote.restart_count,
            "quoted_clock": quote.clock,
            "safe": quote.safe,
            "status": "not_checked",
            "committed": False,
        }
    )


def verify_from_protected(snapshot: ProtectedInputSnapshot) -> dict[str, Any]:
    ds = load_dataset(snapshot)
    return verify_dataset(ds)

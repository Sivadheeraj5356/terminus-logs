"""Verifier for the stateful depot admission trace contract."""

from __future__ import annotations

import hashlib
import hmac
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

APP = Path("/app")
ENV = APP / "environment"
OUT = APP / "output" / "admission_trace.json"
DEPOT = ENV / "bin" / "depot"
PACKS = ENV / "data" / "packs"
CATALOG = ENV / "data" / "tickets" / "catalog.json"
RUNTIME = ENV / "data" / "runtime"
FLOOR = RUNTIME / "epoch_floor.json"
LEDGER = RUNTIME / "revoke_ledger.json"
STATE = RUNTIME / "session_state.json"

MAC_KEY = b"depot-capability-v1-key-material-32b!!"
ROW_KEYS = {
    "index",
    "row_id",
    "session_seq",
    "pass_index",
    "seen_seq",
    "principal",
    "subject_id",
    "ticket_id",
    "parent_id",
    "ticket_epoch",
    "scope_mask",
    "action_mask",
    "effective_scope",
    "decision",
    "reason",
    "mac_ok",
    "revoke_hit",
    "scope_ok",
    "epoch_ok",
    "issuer_audit_hex",
    "gate_audit_hex",
}


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _rebuild() -> None:
    clean = _run(["make", "-C", str(ENV), "clean"])
    assert clean.returncode == 0, clean.stderr or clean.stdout
    build = _run(["make", "-C", str(ENV), "-j2"])
    assert build.returncode == 0, build.stderr or build.stdout


@pytest.fixture(scope="module", autouse=True)
def built_env() -> None:
    _clean_runtime()
    _rebuild()


def _clean_runtime() -> None:
    if OUT.parent.exists():
        shutil.rmtree(OUT.parent)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    PACKS.mkdir(parents=True, exist_ok=True)
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    STATE.unlink(missing_ok=True)


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _mac(subject_id: str, ticket_id: str, parent_id: str, epoch: int, scope: int) -> str:
    msg = f"{subject_id}|{ticket_id}|{parent_id}|{epoch}|{scope}".encode()
    return hmac.new(MAC_KEY, msg, hashlib.sha256).hexdigest()


def _ticket(
    row_id: str,
    principal: str,
    ticket_id: str,
    parent_id: str,
    epoch: int,
    scope: int,
    action: int,
    seen_seq: int,
    *,
    subject: str | None = None,
    bad_mac: bool = False,
) -> dict[str, Any]:
    subject_id = subject or principal
    ticket_hex = _mac(subject_id, ticket_id, parent_id, epoch, scope)
    if bad_mac:
        ticket_hex = "0" * 64
    return {
        "row_id": row_id,
        "principal": principal,
        "ticket_id": ticket_id,
        "parent_id": parent_id,
        "ticket_epoch": epoch,
        "scope_mask": scope,
        "action_mask": action,
        "seen_seq": seen_seq,
        "ticket_hex": ticket_hex,
    }


def _install_case(
    *,
    floor_epoch: int,
    catalog: list[dict[str, Any]],
    broadcasts: list[dict[str, Any]],
    packs: dict[str, dict[str, Any]],
) -> None:
    _clean_runtime()
    _write_json(FLOOR, {"floor_epoch": floor_epoch})
    _write_json(CATALOG, {"tickets": catalog})
    _write_json(LEDGER, {"broadcasts": broadcasts})
    for name, pack in packs.items():
        _write_json(PACKS / f"{name}.json", pack)


def _audit(pack: str, *, wipe_output: bool = True) -> dict[str, Any]:
    if wipe_output:
        OUT.unlink(missing_ok=True)
    proc = _run([str(DEPOT), "audit", "--pack", pack])
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert OUT.exists(), f"missing admission trace for {pack}"
    return json.loads(OUT.read_text(encoding="utf-8"))


def _catalog_map() -> dict[str, dict[str, Any]]:
    return {row["ticket_id"]: row for row in json.loads(CATALOG.read_text(encoding="utf-8"))["tickets"]}


def _pack(name: str) -> dict[str, Any]:
    return json.loads((PACKS / f"{name}.json").read_text(encoding="utf-8"))


def _ancestors(ticket_id: str, parent_id: str) -> list[str]:
    catalog = _catalog_map()
    chain = [ticket_id]
    cur = parent_id
    while cur:
        chain.append(cur)
        cur = catalog[cur].get("parent_id", "")
    return chain


def _subject(ticket_id: str) -> str:
    return _catalog_map()[ticket_id]["subject_id"]


def _effective_scope(ticket: dict[str, Any]) -> int:
    catalog = _catalog_map()
    eff = int(ticket["scope_mask"])
    cur = ticket["parent_id"]
    while cur:
        eff &= int(catalog[cur]["scope_mask"])
        cur = catalog[cur].get("parent_id", "")
    return eff


def _active_revocations(seen_seq: int) -> dict[tuple[str, str], bool]:
    latest: dict[tuple[str, str], tuple[int, bool]] = {}
    for event in json.loads(LEDGER.read_text(encoding="utf-8")).get("broadcasts", []):
        seq = int(event["seq"])
        if seq > seen_seq:
            continue
        key = (event["kind"], event["value"])
        old = latest.get(key)
        if old is None or seq >= old[0]:
            latest[key] = (seq, bool(event["active"]))
    return {key: active for key, (_, active) in latest.items()}


def _expected_for(ticket: dict[str, Any], session_id: str, session_seq: int, pass_index: int) -> dict[str, Any]:
    floor_epoch = int(json.loads(FLOOR.read_text(encoding="utf-8"))["floor_epoch"])
    subject = _subject(ticket["ticket_id"])
    eff = _effective_scope(ticket)
    expect_hex = _mac(subject, ticket["ticket_id"], ticket["parent_id"], ticket["ticket_epoch"], ticket["scope_mask"])
    mac_ok = hmac.compare_digest(ticket["ticket_hex"].lower(), expect_hex)
    active = _active_revocations(int(ticket["seen_seq"]))
    revoked_ids = {value for (kind, value), is_active in active.items() if kind == "ticket" and is_active}
    revoked_subjects = {value for (kind, value), is_active in active.items() if kind == "subject" and is_active}
    revoke_hit = subject in revoked_subjects or bool(set(_ancestors(ticket["ticket_id"], ticket["parent_id"])) & revoked_ids)
    scope_ok = (int(ticket["action_mask"]) & eff) == int(ticket["action_mask"])
    epoch_ok = int(ticket["ticket_epoch"]) >= floor_epoch
    if not mac_ok:
        decision, reason = "deny", "mac_fail"
    elif revoke_hit:
        decision, reason = "deny", "revoked"
    elif not epoch_ok:
        decision, reason = "deny", "stale_epoch"
    elif not scope_ok:
        decision, reason = "deny", "scope_exceed"
    else:
        decision, reason = "admit", "ok"
    issuer = _sha(
        f"issuer|{session_id}|{ticket['row_id']}|{subject}|{ticket['ticket_id']}|"
        f"{decision}|{floor_epoch}|{int(revoke_hit)}"
    )
    gate = _sha(
        f"gate|{session_id}|{ticket['row_id']}|{subject}|{ticket['ticket_id']}|"
        f"{decision}|{ticket['seen_seq']}|{floor_epoch}|{int(revoke_hit)}|"
        f"{int(mac_ok)}|{int(scope_ok)}|{int(epoch_ok)}|{eff}"
    )
    return {
        "row_id": ticket["row_id"],
        "session_seq": session_seq,
        "pass_index": pass_index,
        "seen_seq": ticket["seen_seq"],
        "subject_id": subject,
        "effective_scope": eff,
        "mac_ok": mac_ok,
        "revoke_hit": revoke_hit,
        "scope_ok": scope_ok,
        "epoch_ok": epoch_ok,
        "decision": decision,
        "reason": reason,
        "issuer_audit_hex": issuer,
        "gate_audit_hex": gate,
    }


def _assert_row(ticket: dict[str, Any], row: dict[str, Any], session_id: str, session_seq: int, pass_index: int) -> None:
    assert set(row) == ROW_KEYS
    expected = _expected_for(ticket, session_id, session_seq, pass_index)
    for key in ["principal", "ticket_id", "parent_id", "ticket_epoch", "scope_mask", "action_mask"]:
        assert row[key] == ticket[key]
    for key, value in expected.items():
        assert row[key] == value, f"{ticket['row_id']} {key}"


def _fold(profile: str, session_id: str, rows: list[dict[str, Any]]) -> str:
    parts = ["fold", profile, session_id, str(len(rows))]
    for row in sorted(rows, key=lambda item: item["row_id"]):
        parts.extend([row["row_id"], row["ticket_id"], row["decision"], row["reason"], row["gate_audit_hex"]])
    return _sha("|".join(parts))


def _base_catalog() -> list[dict[str, Any]]:
    return [
        {"ticket_id": "root-alpha", "parent_id": "", "subject_id": "acct:alpha", "scope_mask": 7},
        {"ticket_id": "child-beta", "parent_id": "root-alpha", "subject_id": "acct:alpha", "scope_mask": 3},
        {"ticket_id": "grand-beta", "parent_id": "child-beta", "subject_id": "acct:alpha", "scope_mask": 6},
        {"ticket_id": "root-delta", "parent_id": "", "subject_id": "acct:delta", "scope_mask": 7},
        {"ticket_id": "child-delta", "parent_id": "root-delta", "subject_id": "acct:delta", "scope_mask": 5},
        {"ticket_id": "root-gamma", "parent_id": "", "subject_id": "acct:gamma", "scope_mask": 7},
        {"ticket_id": "child-gamma", "parent_id": "root-gamma", "subject_id": "acct:gamma", "scope_mask": 6},
    ]


def test_session_history_survives_rebuild_and_output_reconstruction() -> None:
    """Same-session rows append across invocations and rebuild from persisted state."""
    pack_a = {
        "pack_id": "p-session-a",
        "profile": "session",
        "session_id": "sess-red",
        "reset_session": True,
        "tickets": [
            _ticket("r01", "acct:alpha", "root-alpha", "", 9, 7, 1, 1),
            _ticket("r02", "acct:alpha", "child-beta", "root-alpha", 9, 3, 2, 1),
        ],
    }
    pack_b = {
        "pack_id": "p-session-b",
        "profile": "session",
        "session_id": "sess-red",
        "tickets": [_ticket("r03", "acct:alpha", "grand-beta", "child-beta", 9, 6, 2, 2)],
    }
    _install_case(floor_epoch=5, catalog=_base_catalog(), broadcasts=[], packs={"pack_a": pack_a, "pack_b": pack_b})
    first = _audit("pack_a")
    _rebuild()
    second = _audit("pack_b")
    assert first["row_count"] == 2
    assert second["row_count"] == 3
    assert second["run_count"] == 2
    for ticket, row, seq in zip(pack_a["tickets"] + pack_b["tickets"], second["rows"], [1, 2, 3], strict=True):
        _assert_row(ticket, row, "sess-red", seq, 1 if seq < 3 else 2)
    for key in ["principal", "subject_id", "ticket_id", "decision", "reason", "gate_audit_hex"]:
        assert second[key] == second["rows"][0][key]
    assert second["fold_audit_hex"] == _fold(pack_b["profile"], pack_b["session_id"], second["rows"])


def test_broadcast_clear_is_sequence_scoped_and_session_reset_is_local() -> None:
    """Later broadcast clears affect later rows without leaking across sessions."""
    broadcasts = [
        {"seq": 4, "kind": "subject", "value": "acct:delta", "active": True},
        {"seq": 8, "kind": "subject", "value": "acct:delta", "active": False},
        {"seq": 9, "kind": "ticket", "value": "root-gamma", "active": True},
    ]
    delta_first = _ticket("d-before", "acct:delta", "child-delta", "root-delta", 9, 5, 1, 6, subject="acct:delta")
    delta_after = _ticket("d-after", "acct:delta", "child-delta", "root-delta", 9, 5, 1, 10, subject="acct:delta")
    gamma = _ticket("g-child", "acct:gamma", "child-gamma", "root-gamma", 9, 6, 2, 10, subject="acct:gamma")
    pack = {
        "pack_id": "p-broadcast",
        "profile": "broadcast",
        "session_id": "sess-broadcast",
        "reset_session": True,
        "tickets": [delta_first, delta_after, gamma],
    }
    other = {
        "pack_id": "p-other",
        "profile": "broadcast",
        "session_id": "sess-other",
        "reset_session": True,
        "tickets": [delta_after],
    }
    _install_case(floor_epoch=5, catalog=_base_catalog(), broadcasts=broadcasts, packs={"pack_broadcast": pack, "pack_other": other})
    doc = _audit("pack_broadcast")
    by_row = {row["row_id"]: row for row in doc["rows"]}
    before = by_row[delta_first["row_id"]]
    after = by_row[delta_after["row_id"]]
    gamma_row = by_row[gamma["row_id"]]
    assert before["revoke_hit"] is True
    assert before["reason"] == "revoked"
    assert after["revoke_hit"] is False
    assert after["decision"] == "admit"
    assert gamma_row["revoke_hit"] is True
    assert gamma_row["reason"] == "revoked"
    other_doc = _audit("pack_other")
    assert other_doc["session_id"] == other["session_id"]
    assert other_doc["row_count"] == 1


def test_alias_presented_ticket_uses_canonical_subject_for_mac_and_revoke() -> None:
    """Presented aliases do not replace the catalog subject for binding or revocation."""
    broadcasts = [{"seq": 3, "kind": "subject", "value": "acct:alpha", "active": True}]
    alias_ticket = _ticket("alias-row", "acct-alpha-legacy", "child-beta", "root-alpha", 7, 3, 1, 4, subject="acct:alpha")
    pack = {
        "pack_id": "p-alias",
        "profile": "alias",
        "session_id": "sess-alias",
        "reset_session": True,
        "tickets": [alias_ticket],
    }
    _install_case(floor_epoch=5, catalog=_base_catalog(), broadcasts=broadcasts, packs={"pack_alias": pack})
    row = _audit("pack_alias")["rows"][0]
    _assert_row(alias_ticket, row, "sess-alias", 1, 1)
    assert row["principal"] == alias_ticket["principal"]
    assert row["subject_id"] == _subject(alias_ticket["ticket_id"])
    assert row["mac_ok"] is True
    assert row["revoke_hit"] is True
    assert row["reason"] == "revoked"


def test_scope_epoch_and_reason_priority_are_derived_after_full_ancestry() -> None:
    """Scope, epoch, and priority interact instead of being independent row flags."""
    stale_scope = _ticket("scope-row", "acct:alpha", "grand-beta", "child-beta", 4, 6, 4, 1, subject="acct:alpha")
    bad_mac = _ticket("bad-row", "acct:gamma", "child-gamma", "root-gamma", 3, 6, 4, 12, subject="acct:gamma", bad_mac=True)
    pack = {
        "pack_id": "p-policy",
        "profile": "policy",
        "session_id": "sess-policy",
        "reset_session": True,
        "tickets": [stale_scope, bad_mac],
    }
    broadcasts = [{"seq": 10, "kind": "ticket", "value": "root-gamma", "active": True}]
    _install_case(floor_epoch=5, catalog=_base_catalog(), broadcasts=broadcasts, packs={"pack_policy": pack})
    rows = _audit("pack_policy")["rows"]
    _assert_row(stale_scope, rows[0], "sess-policy", 1, 1)
    _assert_row(bad_mac, rows[1], "sess-policy", 2, 1)
    assert rows[0]["effective_scope"] == 2
    assert rows[0]["scope_ok"] is False
    assert rows[0]["epoch_ok"] is False
    assert rows[0]["reason"] == "stale_epoch"
    assert rows[1]["mac_ok"] is False
    assert rows[1]["revoke_hit"] is True
    assert rows[1]["epoch_ok"] is False
    assert rows[1]["reason"] == "mac_fail"


def test_fold_digest_is_stable_for_equivalent_row_sets_in_different_order() -> None:
    """Equivalent sessions fold the same way even when pack row order changes."""
    rows = [
        _ticket("ord-a", "acct:alpha", "root-alpha", "", 8, 7, 1, 2, subject="acct:alpha"),
        _ticket("ord-b", "acct:alpha", "child-beta", "root-alpha", 8, 3, 2, 2, subject="acct:alpha"),
        _ticket("ord-c", "acct:alpha", "grand-beta", "child-beta", 8, 6, 2, 2, subject="acct:alpha"),
    ]
    pack_a = {
        "pack_id": "p-order-a",
        "profile": "order",
        "session_id": "sess-order",
        "reset_session": True,
        "tickets": rows,
    }
    pack_b = {
        "pack_id": "p-order-b",
        "profile": "order",
        "session_id": "sess-order",
        "reset_session": True,
        "tickets": list(reversed(rows)),
    }
    _install_case(floor_epoch=5, catalog=_base_catalog(), broadcasts=[], packs={"pack_order_a": pack_a, "pack_order_b": pack_b})
    doc_a = _audit("pack_order_a")
    doc_b = _audit("pack_order_b")
    assert [row["row_id"] for row in doc_a["rows"]] != [row["row_id"] for row in doc_b["rows"]]
    assert doc_a["fold_audit_hex"] == doc_b["fold_audit_hex"]
    assert doc_a["fold_audit_hex"] == _fold(pack_a["profile"], pack_a["session_id"], doc_a["rows"])
    assert doc_b["fold_audit_hex"] == _fold(pack_b["profile"], pack_b["session_id"], doc_b["rows"])


def test_repeated_audit_after_reset_is_byte_stable() -> None:
    """A reset pack produces identical bytes when repeated from the same fixtures."""
    pack = {
        "pack_id": "p-repeat",
        "profile": "repeat",
        "session_id": "sess-repeat",
        "reset_session": True,
        "tickets": [
            _ticket("repeat-a", "acct:alpha", "root-alpha", "", 6, 7, 1, 1, subject="acct:alpha"),
            _ticket("repeat-b", "acct:alpha", "child-beta", "root-alpha", 6, 3, 2, 1, subject="acct:alpha"),
        ],
    }
    _install_case(floor_epoch=5, catalog=_base_catalog(), broadcasts=[], packs={"pack_repeat": pack})
    _audit("pack_repeat")
    first_bytes = OUT.read_bytes()
    _rebuild()
    _audit("pack_repeat")
    assert OUT.read_bytes() == first_bytes

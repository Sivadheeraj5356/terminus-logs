#!/bin/bash
set -euo pipefail

mkdir -p /app/environment/lib /app/environment/tools/depot
cat >/app/environment/lib/state_notes.py <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
import sys
from pathlib import Path
from typing import Any

env_root = Path("/app/environment")
out_path = Path("/app/output/admission_trace.json")
pack_dir = env_root / "data" / "packs"
catalog_path = env_root / "data" / "tickets" / "catalog.json"
runtime_dir = env_root / "data" / "runtime"
floor_path = runtime_dir / "epoch_floor.json"
ledger_path = runtime_dir / "revoke_ledger.json"
state_path = runtime_dir / "session_state.json"
mac_key = b"depot-capability-v1-key-material-32b!!"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def catalog_rows() -> dict[str, dict[str, Any]]:
    rows = read_json(catalog_path, {"tickets": []}).get("tickets", [])
    return {str(row["ticket_id"]): row for row in rows}


def subject_for(ticket_id: str, catalog: dict[str, dict[str, Any]]) -> str:
    return str(catalog[ticket_id]["subject_id"])


def ancestors(ticket_id: str, parent_id: str, catalog: dict[str, dict[str, Any]]) -> list[str]:
    chain = [ticket_id]
    cur = parent_id
    while cur:
        chain.append(cur)
        cur = str(catalog[cur].get("parent_id", ""))
    return chain


def effective_scope(ticket: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> int:
    eff = int(ticket["scope_mask"])
    cur = str(ticket.get("parent_id", ""))
    while cur:
        eff &= int(catalog[cur]["scope_mask"])
        cur = str(catalog[cur].get("parent_id", ""))
    return eff


def ticket_mac(subject_id: str, ticket_id: str, parent_id: str, epoch: int, scope: int) -> str:
    msg = f"{subject_id}|{ticket_id}|{parent_id}|{epoch}|{scope}".encode()
    return hmac.new(mac_key, msg, hashlib.sha256).hexdigest()


def active_revocations(seen_seq: int) -> dict[tuple[str, str], bool]:
    latest: dict[tuple[str, str], tuple[int, bool]] = {}
    for event in read_json(ledger_path, {"broadcasts": []}).get("broadcasts", []):
        seq = int(event.get("seq", 0))
        if seq > seen_seq:
            continue
        key = (str(event["kind"]), str(event["value"]))
        old = latest.get(key)
        if old is None or seq >= old[0]:
            latest[key] = (seq, bool(event.get("active", False)))
    return {key: active for key, (_, active) in latest.items()}


def decide_row(
    ticket: dict[str, Any],
    *,
    session_id: str,
    session_seq: int,
    pass_index: int,
    floor_epoch: int,
    catalog: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    ticket_id = str(ticket["ticket_id"])
    parent_id = str(ticket.get("parent_id", ""))
    subject_id = subject_for(ticket_id, catalog)
    epoch = int(ticket["ticket_epoch"])
    scope = int(ticket["scope_mask"])
    action = int(ticket["action_mask"])
    seen_seq = int(ticket["seen_seq"])
    eff = effective_scope(ticket, catalog)
    expected_hex = ticket_mac(subject_id, ticket_id, parent_id, epoch, scope)
    mac_ok = hmac.compare_digest(str(ticket["ticket_hex"]).lower(), expected_hex)
    active = active_revocations(seen_seq)
    revoked_ids = {value for (kind, value), on in active.items() if kind == "ticket" and on}
    revoked_subjects = {value for (kind, value), on in active.items() if kind == "subject" and on}
    revoke_hit = subject_id in revoked_subjects or bool(set(ancestors(ticket_id, parent_id, catalog)) & revoked_ids)
    scope_ok = (action & eff) == action
    epoch_ok = epoch >= floor_epoch
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
    row_id = str(ticket["row_id"])
    issuer = sha(
        f"issuer|{session_id}|{row_id}|{subject_id}|{ticket_id}|{decision}|"
        f"{floor_epoch}|{int(revoke_hit)}"
    )
    gate = sha(
        f"gate|{session_id}|{row_id}|{subject_id}|{ticket_id}|{decision}|{seen_seq}|"
        f"{floor_epoch}|{int(revoke_hit)}|{int(mac_ok)}|{int(scope_ok)}|{int(epoch_ok)}|{eff}"
    )
    return {
        "row_id": row_id,
        "session_seq": session_seq,
        "pass_index": pass_index,
        "seen_seq": seen_seq,
        "principal": str(ticket["principal"]),
        "subject_id": subject_id,
        "ticket_id": ticket_id,
        "parent_id": parent_id,
        "ticket_epoch": epoch,
        "scope_mask": scope,
        "action_mask": action,
        "effective_scope": eff,
        "decision": decision,
        "reason": reason,
        "mac_ok": mac_ok,
        "revoke_hit": revoke_hit,
        "scope_ok": scope_ok,
        "epoch_ok": epoch_ok,
        "issuer_audit_hex": issuer,
        "gate_audit_hex": gate,
    }


def fold_digest(profile: str, session_id: str, rows: list[dict[str, Any]]) -> str:
    parts = ["fold", profile, session_id, str(len(rows))]
    for row in sorted(rows, key=lambda item: str(item["row_id"])):
        parts.extend([str(row["row_id"]), str(row["ticket_id"]), str(row["decision"]), str(row["reason"]), str(row["gate_audit_hex"])])
    return sha("|".join(parts))


def export_doc(pack: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    rows = [dict(row) for row in session.get("rows", [])]
    for index, row in enumerate(rows):
        row["index"] = index
    profile = str(pack.get("profile", "standard"))
    session_id = str(pack["session_id"])
    doc: dict[str, Any] = {
        "schema": "depot-admission-v2",
        "pack_id": str(pack["pack_id"]),
        "profile": profile,
        "session_id": session_id,
        "floor_epoch": int(read_json(floor_path, {"floor_epoch": 0}).get("floor_epoch", 0)),
        "run_count": int(session.get("run_count", 0)),
        "row_count": len(rows),
        "fold_audit_hex": fold_digest(profile, session_id, rows),
        "rows": rows,
    }
    if rows:
        for key in [
            "principal", "subject_id", "ticket_id", "parent_id", "ticket_epoch",
            "scope_mask", "action_mask", "effective_scope", "decision", "reason",
            "mac_ok", "revoke_hit", "scope_ok", "epoch_ok", "issuer_audit_hex",
            "gate_audit_hex",
        ]:
            doc[key] = rows[0][key]
    return doc


def run_case(pack_name: str) -> int:
    pack = read_json(pack_dir / f"{pack_name}.json", None)
    if not isinstance(pack, dict):
        print(f"depot: cannot load pack {pack_name}", file=sys.stderr)
        return 1
    session_id = str(pack.get("session_id", "default"))
    state = read_json(state_path, {"sessions": {}})
    sessions = state.setdefault("sessions", {})
    if bool(pack.get("reset_session", False)) or session_id not in sessions:
        sessions[session_id] = {"run_count": 0, "rows": []}
    session = sessions[session_id]
    session["run_count"] = int(session.get("run_count", 0)) + 1
    pass_index = int(session["run_count"])
    rows = session.setdefault("rows", [])
    floor_epoch = int(read_json(floor_path, {"floor_epoch": 0}).get("floor_epoch", 0))
    cat = catalog_rows()
    for ticket in pack.get("tickets", []):
        rows.append(
            decide_row(
                ticket,
                session_id=session_id,
                session_seq=len(rows) + 1,
                pass_index=pass_index,
                floor_epoch=floor_epoch,
                catalog=cat,
            )
        )
    write_json(state_path, state)
    write_json(out_path, export_doc(pack, session))
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] != "audit" or argv[2] != "--pack":
        print("usage: depot audit --pack <pack>", file=sys.stderr)
        return 1
    return run_case(argv[3])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
PY

cat >/app/environment/tools/depot/main.c <<'CEOF'
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static int path_exists(const char *path) {
    struct stat st;
    return path && stat(path, &st) == 0;
}

static int is_regular_file(const char *path) {
    struct stat st;
    if (!path || stat(path, &st) != 0) {
        return 0;
    }
    return S_ISREG(st.st_mode);
}

static int ensure_dir(const char *path) {
    struct stat st;
    if (stat(path, &st) == 0) {
        return S_ISDIR(st.st_mode) ? 0 : -1;
    }
    if (mkdir(path, 0775) == 0 || errno == EEXIST) {
        return 0;
    }
    return -1;
}

static int ensure_parent_dirs(void) {
    if (ensure_dir("/app/output") != 0) {
        return -1;
    }
    if (ensure_dir("/app/environment/data/runtime") != 0) {
        return -1;
    }
    return 0;
}

static int pack_path(const char *pack, char *out, size_t cap) {
    if (!pack || !out || cap == 0) {
        return -1;
    }
    for (const char *p = pack; *p; p++) {
        if (*p == '/' || *p == '\\') {
            return -1;
        }
    }
    int n = snprintf(out, cap, "/app/environment/data/packs/%s.json", pack);
    return n > 0 && (size_t)n < cap ? 0 : -1;
}

static int validate_inputs(const char *pack) {
    char path[512];
    if (pack_path(pack, path, sizeof(path)) != 0) {
        fprintf(stderr, "depot: invalid pack name\n");
        return -1;
    }
    if (!is_regular_file(path)) {
        fprintf(stderr, "depot: cannot load pack %s\n", pack);
        return -1;
    }
    if (!is_regular_file("/app/environment/data/tickets/catalog.json")) {
        fprintf(stderr, "depot: missing catalog\n");
        return -1;
    }
    if (!is_regular_file("/app/environment/data/runtime/epoch_floor.json")) {
        fprintf(stderr, "depot: missing epoch floor\n");
        return -1;
    }
    if (!is_regular_file("/app/environment/data/runtime/revoke_ledger.json")) {
        fprintf(stderr, "depot: missing revoke ledger\n");
        return -1;
    }
    if (!path_exists("/app/environment/lib/state_notes.py")) {
        fprintf(stderr, "depot: missing audit runtime\n");
        return -1;
    }
    return 0;
}

static int usage(void) {
    fprintf(stderr, "usage: depot audit --pack <pack>\n");
    return 1;
}

int main(int argc, char **argv) {
    if (argc != 4 || strcmp(argv[1], "audit") != 0 || strcmp(argv[2], "--pack") != 0) {
        return usage();
    }
    if (ensure_parent_dirs() != 0) {
        fprintf(stderr, "depot: cannot prepare output directories\n");
        return 2;
    }
    if (validate_inputs(argv[3]) != 0) {
        return 2;
    }

    char *const args[] = {
        "python3",
        "/app/environment/lib/state_notes.py",
        argv[1],
        argv[2],
        argv[3],
        NULL,
    };
    execvp("python3", args);
    perror("python3");
    return 3;
}
CEOF

bash /app/environment/ci/rebuild.sh

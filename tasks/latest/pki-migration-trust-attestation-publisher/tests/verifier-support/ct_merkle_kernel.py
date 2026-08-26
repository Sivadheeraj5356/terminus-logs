"""Independent CT disposition reference math shipped under /app for contract parity."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _parse_rfc3339(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def merkle_parent(left: str, right: str) -> str:
    return hashlib.sha256(bytes.fromhex(left) + bytes.fromhex(right)).hexdigest()


def verify_merkle_path(leaf_hash: str, leaf_index: int, path: list[str], root_hash: str) -> bool:
    cur = leaf_hash
    idx = leaf_index
    for sibling in path:
        if idx % 2 == 0:
            cur = merkle_parent(cur, sibling)
        else:
            cur = merkle_parent(sibling, cur)
        idx //= 2
    return cur == root_hash


def trust_score(disposition: str, reason: str) -> int:
    if disposition == "trusted":
        return 100
    if disposition == "needs_review":
        return 50
    mapping = {
        "revoked": 0,
        "wrong_tree_size": 12,
        "duplicate_serial": 8,
        "stale_sth": 18,
        "untrusted_root": 22,
        "invalid_chain": 15,
    }
    return mapping.get(reason, 0)


def trusted_roots(bundle: Path) -> set[str]:
    p = bundle / "trusted_roots.json"
    if p.is_file():
        data = json.loads(p.read_text(encoding="utf-8"))
        return set(data.get("trusted_roots", []))
    return {"ROOT-TRUST-01"}


def load_certs(bundle: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in sorted((bundle / "certificates").iterdir()):
        if path.suffix == ".json":
            cert = json.loads(path.read_text(encoding="utf-8"))
            cert.setdefault("filename", path.name)
            out[path.name] = cert
    return out


def load_proofs(bundle: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    proofs_dir = bundle / "ct_logs/proofs"
    if not proofs_dir.is_dir():
        return out
    for path in proofs_dir.glob("*.json"):
        proof = json.loads(path.read_text(encoding="utf-8"))
        key = f"{proof['serial']}:{proof['leaf_index']}"
        out[key] = proof
    return out


def duplicate_losers(bundle: Path) -> set[str]:
    data = json.loads((bundle / "issuance.json").read_text(encoding="utf-8"))
    by_serial: dict[str, list[dict[str, Any]]] = {}
    for row in data.get("issuance", []):
        by_serial.setdefault(row["serial"], []).append(row)
    losers: set[str] = set()
    for rows in by_serial.values():
        if len(rows) < 2:
            continue
        winner = max(rows, key=lambda r: r["issued_at"])
        for row in rows:
            if row["filename"] != winner["filename"]:
                losers.add(row["filename"])
    return losers


def snapshot_from_bundle(bundle: Path) -> dict[str, Any]:
    meta = json.loads((bundle / "bundle_meta.json").read_text(encoding="utf-8"))
    issuance = json.loads((bundle / "issuance.json").read_text(encoding="utf-8")).get("issuance", [])
    by_serial: dict[str, list[dict[str, Any]]] = {}
    for row in issuance:
        by_serial.setdefault(row["serial"], []).append(row)
    for serial in by_serial:
        by_serial[serial] = sorted(by_serial[serial], key=lambda r: r["issued_at"], reverse=True)
    seen: dict[str, int] = {}
    rows = []
    for entry in load_jsonl(bundle / "ct_logs/b161aa7f_entries.jsonl"):
        serial = entry["serial"]
        options = by_serial.get(serial, [])
        if len(options) == 1:
            fname = options[0]["filename"]
        elif options:
            idx = seen.get(serial, 0)
            fname = options[idx]["filename"]
            seen[serial] = idx + 1
        else:
            fname = f"{serial}.json"
        rows.append(
            {
                "serial": serial,
                "filename": fname,
                "leaf_index": entry["leaf_index"],
                "leaf_hash": entry["leaf_hash"],
            }
        )
    return {"bundle_id": meta["bundle_id"], "rows": rows}


def disposition_rows(bundle: Path, snap: dict[str, Any]) -> list[dict[str, Any]]:
    certs = load_certs(bundle)
    entries = {f"{e['serial']}:{e['leaf_index']}": e for e in load_jsonl(bundle / "ct_logs/b161aa7f_entries.jsonl")}
    sth = json.loads((bundle / "ct_logs/sth.json").read_text(encoding="utf-8"))
    proofs = load_proofs(bundle)
    rev_data = json.loads((bundle / "revocations.json").read_text(encoding="utf-8"))
    revoked = {r["serial"] for r in rev_data.get("revocations", [])}
    dup_losers = duplicate_losers(bundle)
    roots = trusted_roots(bundle)
    rows: list[dict[str, Any]] = []
    for srow in snap["rows"]:
        cert = certs.get(srow["filename"], {})
        entry = entries[f"{srow['serial']}:{srow['leaf_index']}"]
        disp = "rejected"
        reason = "unknown"
        if srow["serial"] in revoked:
            reason = "revoked"
        elif srow["filename"] in dup_losers:
            reason = "duplicate_serial"
        elif not cert.get("signature_ok", False) or not cert.get("issuer_serial"):
            reason = "invalid_chain"
        elif cert.get("issuer_serial") not in roots:
            reason = "untrusted_root"
        else:
            key = f"{srow['serial']}:{srow['leaf_index']}"
            if key not in proofs:
                disp = "needs_review"
                reason = "missing_proof"
            elif _parse_rfc3339(sth["timestamp"]) < _parse_rfc3339(entry["timestamp"]):
                reason = "stale_sth"
            else:
                proof = proofs[key]
                if proof["tree_size"] != sth["tree_size"]:
                    reason = "wrong_tree_size"
                elif not verify_merkle_path(entry["leaf_hash"], entry["leaf_index"], proof["path"], sth["root_hash"]):
                    reason = "wrong_tree_size"
                else:
                    disp = "trusted"
                    reason = "ok"
        rows.append(
            {
                "serial": srow["serial"],
                "disposition": disp,
                "reason": reason,
                "trust_score": trust_score(disp, reason),
            }
        )
    return rows


def snapshot_row_digest(snap: dict[str, Any]) -> str:
    parts = [f"{row['serial']}|{row['leaf_index']}" for row in snap["rows"]]
    return hashlib.sha256(",".join(parts).encode("utf-8")).hexdigest()


def trusted_ledger(bundle_id: str, rows: list[dict[str, Any]], snap: dict[str, Any], epoch: int = 1) -> dict[str, Any]:
    trusted = sorted(r["serial"] for r in rows if r["disposition"] == "trusted")
    review = sorted(r["serial"] for r in rows if r["disposition"] == "needs_review")
    lineage = snapshot_row_digest(snap)
    combined = hashlib.sha256(f"{'|'.join(trusted)}|{lineage}".encode("utf-8")).hexdigest()
    return {
        "bundle_id": bundle_id,
        "trusted_serials": trusted,
        "needs_review_serials": review,
        "trusted_count": len(trusted),
        "combined_digest": combined,
        "publish_epoch": epoch,
    }


def reference_evaluate_snapshot(bundle: Path, snap: dict[str, Any]) -> dict[str, Any]:
    rows = disposition_rows(bundle, snap)
    ledger_block = trusted_ledger(snap["bundle_id"], rows, snap)
    return {"bundle_id": snap["bundle_id"], "rows": rows, "ledger_block": ledger_block}


def reference_evaluate_bundle(bundle: Path) -> dict[str, Any]:
    snap = snapshot_from_bundle(bundle)
    return reference_evaluate_snapshot(bundle, snap)


def reference_merkle_path(leaf_hash: str, leaf_index: int, path: list[str], root_hash: str) -> bool:
    return verify_merkle_path(leaf_hash, leaf_index, path, root_hash)


def reference_trust_score(disposition: str, reason: str) -> int:
    return trust_score(disposition, reason)

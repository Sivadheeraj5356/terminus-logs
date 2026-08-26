#!/usr/bin/env python3
"""Reference oracle: recomputes expected Go module integrity gate from manifest + live proxy/sumdb."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import urllib.request
from pathlib import Path

WAIVER_ROW = re.compile(r"module=(\S+)\s+token=(\S+)\s+scope=(\S+)")


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(root: Path, declared: str) -> Path:
    p = Path(declared)
    return p if p.is_absolute() else root / p


def _batch_root(manifest_path: Path) -> Path:
    return manifest_path.resolve().parent.parent


def _encode_module(module_path: str) -> str:
    out = []
    for ch in module_path:
        if "A" <= ch <= "Z":
            out.append("!")
            out.append(ch.lower())
        else:
            out.append(ch)
    return "".join(out)


def _helper_match(bin_path: Path, *args: str) -> bool:
    proc = subprocess.run(
        [str(bin_path), *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return proc.returncode == 0 and proc.stdout.strip() == "match"


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read()


def _parse_retract_specs(mod_text: str) -> list[str]:
    specs: list[str] = []
    in_block = False
    for raw in mod_text.splitlines():
        line = raw.strip()
        if "//" in line:
            line = line.split("//", 1)[0].strip()
        if not line:
            continue
        if line.startswith("retract"):
            rest = line[len("retract") :].strip()
            if rest in ("", "("):
                in_block = True
                continue
            if rest.startswith("(") and rest.endswith(")"):
                inner = rest[1:-1].strip()
                if inner:
                    specs.append(inner)
                continue
            specs.append(rest)
            continue
        if in_block:
            if line == ")":
                in_block = False
                continue
            specs.append(line)
    return specs


def _live_retracted(proxy_base: str, match_bin: Path, module_path: str, version: str) -> bool:
    base = proxy_base if proxy_base.endswith("/") else proxy_base + "/"
    enc = _encode_module(module_path)
    try:
        latest = json.loads(_http_get(f"{base}{enc}/@latest").decode())["Version"]
        mod_text = _http_get(f"{base}{enc}/@v/{latest}.mod").decode()
    except Exception:
        return False
    for spec in _parse_retract_specs(mod_text):
        if _helper_match(match_bin, version, spec):
            return True
    return False


def _live_zip_hash(sum_base: str, module_path: str, version: str) -> str:
    base = sum_base if sum_base.endswith("/") else sum_base + "/"
    enc = _encode_module(module_path)
    try:
        body = _http_get(f"{base}lookup/{enc}@{version}").decode()
    except Exception:
        return ""
    prefix = f"{module_path} {version} h1:"
    for line in body.splitlines():
        line = line.strip()
        if line.startswith(prefix) and "/go.mod " not in line:
            parts = line.split()
            if len(parts) >= 3:
                return parts[2]
    return ""


def _read_pack(path: Path) -> str:
    if path.is_dir():
        parts = []
        for child in sorted(path.glob("*.txt")):
            parts.append(child.read_text(encoding="utf-8"))
        return "\n".join(parts)
    return path.read_text(encoding="utf-8")


def _in_scope_waiver(annex_text: str, module_path: str, batch_id: str) -> bool:
    for match in WAIVER_ROW.finditer(annex_text):
        mod, token, scope = match.group(1), match.group(2), match.group(3)
        if mod == module_path and scope == batch_id and token in annex_text:
            return True
    return False


def conflict_preds(manifest_path: Path) -> dict[str, dict[str, bool]]:
    root = _batch_root(manifest_path)
    manifest = _load_json(manifest_path)
    report = _load_json(_resolve(root, manifest["conflict_report_path"]))
    out: dict[str, dict[str, bool]] = {}
    for row in report["conflicts"]:
        reasons = row.get("reasons") or ([row["reason"]] if "reason" in row else [])
        out[row["mod_id"]] = {
            "refresh_retract": "retract_refresh" in reasons,
            "refresh_sum": "checksumdb_drift" in reasons,
        }
    return out


def conflict_ids(manifest_path: Path) -> set[str]:
    return set(conflict_preds(manifest_path))


def _bool(v: bool) -> str:
    return "true" if v else "false"


def compute_chain_digest(rows: list[dict]) -> str:
    hasher = hashlib.sha256()
    for row in rows:
        hasher.update(row["mod_id"].encode())
        hasher.update(row["member"].encode())
        hasher.update(row["linkage"].encode())
        hasher.update(_bool(row["retracted"]).encode())
        hasher.update(_bool(row["checksum_ok"]).encode())
        hasher.update(_bool(row["go_floor_ok"]).encode())
        hasher.update(_bool(row["excluded"]).encode())
        hasher.update(row["gate_action"].encode())
        hasher.update(row["policy_basis"].encode())
    return hasher.hexdigest()


def compute_row_digest(row: dict) -> str:
    hasher = hashlib.sha256()
    hasher.update(row["mod_id"].encode())
    hasher.update(row["member"].encode())
    hasher.update(row["linkage"].encode())
    hasher.update(_bool(row["retracted"]).encode())
    hasher.update(_bool(row["checksum_ok"]).encode())
    hasher.update(_bool(row["go_floor_ok"]).encode())
    hasher.update(row["gate_action"].encode())
    hasher.update(row["policy_basis"].encode())
    hasher.update(row["live_hash"].encode())
    return hasher.hexdigest()


def compute_export_digest(rows: list[dict]) -> tuple[str, list[dict]]:
    pin_digests = []
    hasher = hashlib.sha256()
    for row in rows:
        rd = compute_row_digest(row)
        pin_digests.append({"mod_id": row["mod_id"], "row_digest": rd})
        hasher.update(rd.encode())
    return hasher.hexdigest(), pin_digests


def _member_rollups(rows: list[dict]) -> list[dict]:
    by: dict[str, list[dict]] = {}
    for row in rows:
        by.setdefault(row["member"], []).append(row)
    out = []
    for member in sorted(by):
        pins = by[member]
        status = "pass"
        for row in pins:
            if row["gate_action"] == "block":
                status = "block"
                break
            if row["gate_action"] == "warn" and status == "pass":
                status = "warn"
        out.append({"member": member, "pin_count": len(pins), "gate_status": status})
    return out


def expected_integrity(manifest_path: Path) -> tuple[list[dict], dict, dict]:
    root = _batch_root(manifest_path)
    manifest = _load_json(manifest_path)
    lock = _load_json(_resolve(root, manifest["module_lock_path"]))
    snap = _load_json(_resolve(root, manifest["snapshot_path"]))["entries"]
    preds = conflict_preds(manifest_path)
    excludes = set(_load_json(_resolve(root, manifest["exclude_overlay_path"]))["modules"])
    annex_text = _read_pack(_resolve(root, manifest["corpus_annex_path"]))
    match_bin = _resolve(root, manifest["retractmatch_bin"])
    floor_bin = _resolve(root, manifest["gofloor_bin"])
    proxy_base = manifest["proxy_api_base"]
    sum_base = manifest["sumdb_api_base"]
    batch_id = manifest["module_batch_id"]
    toolchain = manifest["toolchain_declared"]

    rows: list[dict] = []
    live_refreshes = 0
    waiver_hits = 0
    stale_overrides = 0
    retract_hits = 0
    checksum_failures = 0
    toolchain_blocks = 0
    exclude_skips = 0
    transitive_warns = 0

    for pin in lock["pins"]:
        mod_id = pin["mod_id"]
        pred = preds.get(mod_id, {"refresh_retract": False, "refresh_sum": False})
        is_conflict = pred["refresh_retract"] or pred["refresh_sum"]
        source = "proxy_live" if is_conflict else "snapshot"
        if is_conflict:
            live_refreshes += 1

        se = snap.get(mod_id, {"retracted": False, "zip_hash": ""})
        if pred["refresh_retract"]:
            retracted = _live_retracted(proxy_base, match_bin, pin["module_path"], pin["version"])
        else:
            retracted = bool(se.get("retracted", False))

        if pred["refresh_sum"]:
            live_hash = _live_zip_hash(sum_base, pin["module_path"], pin["version"])
        else:
            live_hash = se.get("zip_hash", "")
        checksum_ok = bool(live_hash) and pin["declared_hash"] == live_hash
        go_floor_ok = _helper_match(floor_bin, toolchain, pin["go_floor"])
        excluded = pin["module_path"] in excludes

        if is_conflict:
            snap_floor = _helper_match(floor_bin, toolchain, pin["go_floor"])
            snap_viol = (
                bool(se.get("retracted", False))
                or pin["declared_hash"] != se.get("zip_hash", "")
                or not snap_floor
            )
            live_viol = (not excluded) and (retracted or not checksum_ok or not go_floor_ok)
            if snap_viol != live_viol:
                stale_overrides += 1

        waived = _in_scope_waiver(annex_text, pin["module_path"], batch_id)
        if waived:
            waiver_hits += 1

        if excluded:
            viol = False
            gate = "pass"
            basis = "exclude_skip"
            reason = ""
        else:
            viol = retracted or not checksum_ok or not go_floor_ok
            if viol:
                if retracted:
                    reason = "retract_notice"
                elif not checksum_ok:
                    reason = "checksum_mismatch"
                else:
                    reason = "toolchain_floor"
            else:
                reason = ""

            if waived:
                basis = "waiver_digest"
                gate = "warn"
            elif retracted and pin["linkage"] == "direct":
                basis = "retract_block"
                gate = "block"
            elif retracted and pin["linkage"] == "transitive":
                basis = "retract_warn_transitive"
                gate = "warn"
            elif not checksum_ok:
                basis = "checksum_block"
                gate = "block"
            elif not go_floor_ok:
                basis = "toolchain_block"
                gate = "block"
            elif is_conflict:
                basis = "live_refresh"
                gate = "pass"
            else:
                basis = "snapshot_carry"
                gate = "pass"

        if retracted:
            retract_hits += 1
        if not checksum_ok:
            checksum_failures += 1
        if basis == "toolchain_block":
            toolchain_blocks += 1
        if basis == "exclude_skip":
            exclude_skips += 1
        if basis == "retract_warn_transitive":
            transitive_warns += 1

        rows.append(
            {
                "mod_id": mod_id,
                "module_path": pin["module_path"],
                "version": pin["version"],
                "member": pin["member"],
                "linkage": pin["linkage"],
                "retracted": retracted,
                "checksum_ok": checksum_ok,
                "go_floor_ok": go_floor_ok,
                "excluded": excluded,
                "effective_violation": viol,
                "gate_action": gate,
                "policy_basis": basis,
                "resolve_source": source,
                "block_reason": reason,
                "declared_hash": pin["declared_hash"],
                "live_hash": live_hash,
                "refresh_retract": pred["refresh_retract"],
                "refresh_sum": pred["refresh_sum"],
            }
        )

    rows.sort(key=lambda r: r["mod_id"])
    export_digest, pin_digests = compute_export_digest(rows)

    gate_status = "pass"
    for row in rows:
        if row["gate_action"] == "block":
            gate_status = "block"
            break
        if row["gate_action"] == "warn" and gate_status == "pass":
            gate_status = "warn"

    cert = {
        "status": "MODGATE_OK",
        "module_batch_id": batch_id,
        "policy_track": manifest["policy_track"],
        "toolchain_declared": toolchain,
        "gate_status": gate_status,
        "record_count": len(rows),
        "live_refreshes": live_refreshes,
        "waiver_hits": waiver_hits,
        "stale_overrides": stale_overrides,
        "retract_hits": retract_hits,
        "checksum_failures": checksum_failures,
        "toolchain_blocks": toolchain_blocks,
        "exclude_skips": exclude_skips,
        "transitive_warns": transitive_warns,
        "chain_digest": compute_chain_digest(rows),
        "export_digest": export_digest,
        "member_rollups": _member_rollups(rows),
        "resolutions": [
            {
                "mod_id": r["mod_id"],
                "policy_basis": r["policy_basis"],
                "resolve_source": r["resolve_source"],
                "gate_action": r["gate_action"],
            }
            for r in rows
        ],
    }
    repro = {
        "module_batch_id": batch_id,
        "export_digest": export_digest,
        "pin_digests": pin_digests,
    }
    return rows, cert, repro
